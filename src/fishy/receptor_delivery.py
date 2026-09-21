"""storage_arrival : StorageBalance → ArrivalResidual.

assess_delivery : tuple[DeliveryStep] × (Interval | None) → DeliveryAssessment.

Exact interval-volume accounting for accepted storage and fixed-delay pathways.
No state inversion, pathway allocation, ecological certification or duty issuance.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from fractions import Fraction
from hashlib import sha256

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    Provenance,
    permitted_use,
    warmup_restrictions,
)
from fishy.quantities import Flow, Volume
from fishy.receptor_states import Compartment, ReceptorDomain, ReceptorVariable, StateStatistic
from fishy.spatial import Location
from fishy.time import Interval


def _text(*values: str) -> None:
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError("identities and physical meaning require nonempty text")


def _tuple(values: tuple, kind: type) -> None:
    if not isinstance(values, tuple) or any(not isinstance(v, kind) for v in values):
        raise TypeError(f"immutable tuple of {kind.__name__} required")


@dataclass(frozen=True)
class DeliveryContext:
    receptor: Location
    period: Interval
    candidate: str
    domain: str
    provenance: Provenance

    def __post_init__(self) -> None:
        _text(self.candidate, self.domain)
        for value, kind in ((self.receptor, Location), (self.period, Interval), (self.provenance, Provenance)):
            if not isinstance(value, kind):
                raise TypeError(f"delivery context requires {kind.__name__}")


def delivery_scope(context: DeliveryContext, subject: object) -> EvidenceScope:
    """Bind acceptance to the exact supplied physical/target record, not a generic flag."""
    digest = sha256(repr((context, subject)).encode()).hexdigest()
    return EvidenceScope(
        f"receptor-delivery:{digest}",
        context.receptor.reach.identifier,
        context.provenance.reference_member,
        context.period,
        "receptor_delivery",
    )


def _support(context: DeliveryContext, subject: object, evidence: EvidenceFindings | None) -> tuple[str, ...]:
    if evidence is None:
        return ("missing accepted relation or target evidence",)
    if (evidence.provenance.scenario, evidence.provenance.reference_member) != (
        context.provenance.scenario,
        context.provenance.reference_member,
    ):
        raise ValueError("incompatible evidence scenario/reference")
    check = permitted_use(evidence, delivery_scope(context, subject))
    reasons = warmup_restrictions(evidence.provenance, context.period)
    if check.finding is not CheckFinding.PASS:
        reasons += check.reasons
    return reasons


class ExchangeDirection(StrEnum):
    INFLOW = "inflow"
    OUTFLOW = "outflow"


@dataclass(frozen=True)
class WaterExchange:
    """An identified carrier crosses this receptor boundary exactly once."""

    carrier: str
    context: DeliveryContext
    direction: ExchangeDirection
    amount: Volume
    other_location: Location

    def __post_init__(self) -> None:
        _text(self.carrier)
        for value, kind in (
            (self.context, DeliveryContext),
            (self.direction, ExchangeDirection),
            (self.amount, Volume),
            (self.other_location, Location),
        ):
            if not isinstance(value, kind):
                raise TypeError(f"exchange requires {kind.__name__}")


@dataclass(frozen=True)
class StorageBalance:
    context: DeliveryContext
    initial: Volume
    target: Volume | None
    exchanges: tuple[WaterExchange, ...]
    relation: str
    uncertainty: str

    def __post_init__(self) -> None:
        _text(self.relation, self.uncertainty)
        if not isinstance(self.context, DeliveryContext) or not isinstance(self.initial, Volume):
            raise TypeError("storage balance requires context and Volume")
        if self.target is not None and not isinstance(self.target, Volume):
            raise TypeError("storage target requires Volume")
        _tuple(self.exchanges, WaterExchange)
        if len({x.carrier for x in self.exchanges}) != len(self.exchanges):
            raise ValueError("duplicate water carrier")
        if any(x.context != self.context for x in self.exchanges):
            raise ValueError("incompatible exchange scenario, time, location or domain")


@dataclass(frozen=True)
class ArrivalResidual:
    balance: StorageBalance
    evidence: EvidenceFindings | None
    signed_residual_m3: Fraction | None
    arrival: Volume | None
    surplus: Volume | None
    reasons: tuple[str, ...]


def storage_arrival(balance: StorageBalance, evidence: EvidenceFindings | None) -> ArrivalResidual:
    """Compute a selected storage target, not an ecological finding or pathway split."""
    reasons = _support(balance.context, balance, evidence)
    if balance.target is None:
        reasons += ("storage target missing; non-storage states require an accepted physical representation",)
    if reasons:
        return ArrivalResidual(balance, evidence, None, None, None, reasons)
    assert balance.target is not None
    net = sum(
        (x.amount.value * (1 if x.direction is ExchangeDirection.OUTFLOW else -1) for x in balance.exchanges),
        Fraction(),
    )
    residual = balance.target.value - balance.initial.value + net
    return ArrivalResidual(
        balance,
        evidence,
        residual,
        Volume(max(residual, 0)),
        Volume(max(-residual, 0)),
        ("surplus requires an operating response; target satisfaction not established",) if residual < 0 else (),
    )


@dataclass(frozen=True)
class Pathway:
    """Fixed interval account: arrival = release + initial - final - losses.

    Storage includes delayed exchanges/in-transit inventory. Losses retain named
    destinations. Valid release domain and separate ramp bounds are supplied.
    Ramps concern adjacent interval means, not unseen instantaneous changes.
    """

    identifier: str
    context: DeliveryContext
    control: Location
    release_period: Interval
    travel_time: timedelta
    initial_storage: Volume
    final_storage: Volume
    losses: tuple[WaterExchange, ...]
    minimum_release: Flow
    capacity: Flow
    predecessor: Flow
    predecessor_period: Interval
    rise_m3_s2: Fraction
    fall_m3_s2: Fraction
    relation: str
    boundary_conditions: str
    uncertainty: str

    def __post_init__(self) -> None:
        _text(self.identifier, self.relation, self.boundary_conditions, self.uncertainty)
        for value, kind in (
            (self.context, DeliveryContext),
            (self.control, Location),
            (self.release_period, Interval),
            (self.predecessor_period, Interval),
            (self.initial_storage, Volume),
            (self.final_storage, Volume),
            (self.minimum_release, Flow),
            (self.capacity, Flow),
            (self.predecessor, Flow),
        ):
            if not isinstance(value, kind):
                raise TypeError(f"pathway requires {kind.__name__}")
        if not isinstance(self.travel_time, timedelta) or self.travel_time < timedelta():
            raise ValueError("travel time must be a nonnegative timedelta")
        if (
            self.release_period.start + self.travel_time != self.context.period.start
            or self.release_period.end + self.travel_time != self.context.period.end
        ):
            raise ValueError("arrival and control periods must match the explicit delay")
        if self.predecessor_period.end != self.release_period.start:
            raise ValueError("ramping requires an adjacent supplied predecessor")
        if self.minimum_release.value > self.capacity.value:
            raise ValueError("release domain is reversed")
        for rate in (self.rise_m3_s2, self.fall_m3_s2):
            if not isinstance(rate, Fraction) or rate < 0:
                raise ValueError("ramp magnitudes require nonnegative exact fractions in m3/s2")
        _tuple(self.losses, WaterExchange)
        if len({x.carrier for x in self.losses}) != len(self.losses):
            raise ValueError("duplicate loss carrier")
        if any(x.context != self.context or x.direction is not ExchangeDirection.OUTFLOW for x in self.losses):
            raise ValueError("pathway losses require matching context and named outflow destinations")


@dataclass(frozen=True)
class PathwayRelease:
    pathway: Pathway
    release: Volume
    evidence: EvidenceFindings | None

    def __post_init__(self) -> None:
        if not isinstance(self.pathway, Pathway) or not isinstance(self.release, Volume):
            raise TypeError("selected release requires Pathway and Volume")


@dataclass(frozen=True)
class PathwayResult:
    selected: PathwayRelease
    arrival: Volume | None
    control_flow: Flow
    ramp_m3_s2: Fraction
    checks: CheckSummary


def map_arrival(pathway: Pathway, arrival: Volume) -> Volume | None:
    """Algebraic control candidate only. assess_delivery must recheck it.

    A negative release residual is unresolved storage/outflow operation, not a
    negative or clipped prescribed delivery.
    """
    release = arrival.value + pathway.final_storage.value - pathway.initial_storage.value
    release += sum((x.amount.value for x in pathway.losses), Fraction())
    return Volume(release) if release >= 0 else None


def _path_result(selected: PathwayRelease) -> PathwayResult:
    p = selected.pathway
    reasons = _support(p.context, p, selected.evidence)
    if selected.evidence is not None:
        reasons += warmup_restrictions(selected.evidence.provenance, p.release_period)
        reasons += warmup_restrictions(selected.evidence.provenance, p.predecessor_period)
    flow = Flow(selected.release.value / p.release_period.seconds)
    # Declared statistic is the difference between adjacent interval means,
    # assigned to their interval-end timestamps.
    dt = p.release_period.seconds
    rate = (flow.value - p.predecessor.value) / dt
    arrival = selected.release.value + p.initial_storage.value - p.final_storage.value
    arrival -= sum((x.amount.value for x in p.losses), Fraction())
    checks = []
    for name, passed in (
        ("capacity", p.minimum_release.value <= flow.value <= p.capacity.value),
        ("ramping", -p.fall_m3_s2 <= rate <= p.rise_m3_s2),
        ("water_balance", arrival >= 0),
    ):
        checks.append(
            Check(
                name,
                CheckFinding.UNKNOWN if reasons else CheckFinding.PASS if passed else CheckFinding.FAIL,
                reasons or (() if passed else (f"{name} infeasible; requirement is not reduced",)),
            )
        )
    return PathwayResult(selected, Volume(arrival) if arrival >= 0 else None, flow, rate, CheckSummary(tuple(checks)))


@dataclass(frozen=True)
class ProcessTest:
    """Scoped imported state value/criterion; never an unqualified pass flag."""

    identifier: str
    context: DeliveryContext
    variable: str
    units: str
    reference: str
    value: Fraction | None
    lower: Fraction | None
    upper: Fraction | None
    boundary: "BoundInclusion"
    source: str

    def __post_init__(self) -> None:
        _text(self.identifier, self.variable, self.units, self.reference, self.source)
        if not isinstance(self.context, DeliveryContext) or not isinstance(self.boundary, BoundInclusion):
            raise TypeError("process tests require context and bound inclusion")
        for v in (self.value, self.lower, self.upper):
            if v is not None and not isinstance(v, Fraction):
                raise ValueError("process quantities require finite exact fractions in declared units")
        if self.lower is None and self.upper is None:
            raise ValueError("process criterion requires a bound")
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValueError("process bounds reversed")


class BoundInclusion(StrEnum):
    INCLUSIVE = "inclusive"
    STRICT = "strict"


@dataclass(frozen=True)
class SupportedProcessTest:
    test: ProcessTest
    evidence: EvidenceFindings | None


class SalinitySupport(StrEnum):
    COUPLED_MODEL = "coupled_model"
    INDEPENDENT_IMPORT = "independent_import"


@dataclass(frozen=True)
class CoupledStateObjective:
    """Imported non-storage quantity response to the exact selected schedule.

    The final inventory is an independently supplied accounting observation, not
    a storage target. Relation acceptance binds it and the state test to the
    selected pathway releases. No storage inversion is asserted.
    """

    quantity: SupportedProcessTest
    final_inventory: Volume
    relation: str
    boundary_conditions: str
    uncertainty: str
    temporal_support: StateStatistic
    required_temporal_support: StateStatistic
    expected_intervals: tuple[Interval, ...]
    required_salinity: str
    salinity_domain: ReceptorDomain
    salinity_support: SalinitySupport

    def __post_init__(self) -> None:
        if not isinstance(self.quantity, SupportedProcessTest) or not isinstance(self.quantity.test, ProcessTest):
            raise TypeError("coupled objective requires an attributable numeric quantity test")
        if not isinstance(self.final_inventory, Volume):
            raise TypeError("coupled final inventory requires Volume, not a target")
        _text(self.relation, self.boundary_conditions, self.uncertainty, self.required_salinity)
        if (
            not isinstance(self.salinity_domain, ReceptorDomain)
            or self.salinity_domain.variable is not ReceptorVariable.SALINITY
        ):
            raise TypeError("salinity requires a typed chemical and compartment domain")
        if self.salinity_domain.compartment is Compartment.INCOMING_WATER:
            raise ValueError("incoming water cannot substitute for receptor salinity")
        if not isinstance(self.salinity_support, SalinitySupport):
            raise TypeError("salinity support must identify coupled-model or independent-import dependence")
        if self.required_salinity == self.quantity.test.identifier:
            raise ValueError("quantity and salinity require distinct criterion identities")
        for temporal in (self.temporal_support, self.required_temporal_support):
            if not isinstance(temporal, StateStatistic):
                raise TypeError("explicit state statistic required")
        test = self.quantity.test
        units = {"wet_area": "m2", "groundwater_head": "m", "level": "m", "hydroperiod": "s"}
        if test.variable not in units or test.units != units[test.variable]:
            raise ValueError("non-storage quantity requires supported variable/unit; discharge is not receptor state")
        if test.variable in ("wet_area", "hydroperiod") and any(
            value is not None and value < 0 for value in (test.value, test.lower, test.upper)
        ):
            raise ValueError("wet area and hydroperiod cannot be negative")
        if test.variable == "hydroperiod" and any(
            value is not None and value > test.context.period.seconds for value in (test.value, test.lower, test.upper)
        ):
            raise ValueError("hydroperiod cannot exceed its assessed interval")
        _tuple(self.expected_intervals, Interval)
        if not self.expected_intervals or test.context.period not in self.expected_intervals:
            raise ValueError("quantity period must occur in the explicit expected trajectory")
        if any(a.end != b.start for a, b in zip(self.expected_intervals, self.expected_intervals[1:], strict=False)):
            raise ValueError("expected trajectory must contain adjacent ordered intervals")


@dataclass(frozen=True)
class DeliveryStep:
    balance: StorageBalance
    evidence: EvidenceFindings | None
    pathways: tuple[PathwayRelease, ...]
    required_pathways: tuple[str, ...]
    required_processes: tuple[str, ...]
    processes: tuple[SupportedProcessTest, ...]
    checking_evidence: EvidenceFindings | None
    state_objective: CoupledStateObjective | None = None
    coupled_evidence: EvidenceFindings | None = None

    def __post_init__(self) -> None:
        _tuple(self.pathways, PathwayRelease)
        _tuple(self.processes, SupportedProcessTest)
        if self.state_objective is not None:
            if not isinstance(self.state_objective, CoupledStateObjective):
                raise TypeError("explicit CoupledStateObjective required")
            if self.balance.target is not None:
                raise ValueError("non-storage objective cannot also declare a storage target")
            if self.state_objective.quantity.test.context != self.balance.context:
                raise ValueError("incompatible coupled quantity candidate, domain, receptor or period")
            if self.state_objective.quantity.test.identifier in self.required_processes:
                raise ValueError("quantity objective must not be duplicated as a process test")
        elif self.coupled_evidence is not None:
            raise ValueError("coupled evidence requires an explicit non-storage objective")
        for ids in (self.required_pathways, self.required_processes):
            _tuple(ids, str)
            _text(*ids)
            if len(set(ids)) != len(ids):
                raise ValueError("duplicate required component")
        ids = tuple(p.pathway.identifier for p in self.pathways)
        test_ids = tuple(p.test.identifier for p in self.processes)
        if len(set(ids)) != len(ids) or len(set(test_ids)) != len(test_ids):
            raise ValueError("duplicate pathway or process")
        if set(ids) - set(self.required_pathways) or set(test_ids) - set(self.required_processes):
            raise ValueError("undeclared pathway or process")
        if any(p.pathway.context != self.balance.context for p in self.pathways) or any(
            p.test.context != self.balance.context for p in self.processes
        ):
            raise ValueError("incompatible candidate, receptor, time, scenario or domain")
        carriers = [x.carrier for x in self.balance.exchanges]
        carriers += [p.pathway.identifier for p in self.pathways]
        carriers += [x.carrier for p in self.pathways for x in p.pathway.losses]
        if len(set(carriers)) != len(carriers):
            raise ValueError("duplicate carrier across receptor/pathway accounts")

    @property
    def checking_subject(self) -> tuple:
        return (
            self.balance,
            tuple((p.pathway, p.release) for p in self.pathways),
            self.required_pathways,
            self.required_processes,
            tuple(p.test for p in self.processes),
            self.state_objective,
        )

    @property
    def salinity_subject(self) -> tuple:
        """Exact chemical/compartment basis for independently supported salinity."""
        if self.state_objective is None:
            raise ValueError("salinity subject requires coupled-state objective")
        test = next(
            (p.test for p in self.processes if p.test.identifier == self.state_objective.required_salinity), None
        )
        return (self.state_objective.salinity_domain, test)

    @property
    def coupled_subject(self) -> tuple:
        """Exact physical input/output pair accepted by the coupled study."""
        return self.checking_subject


@dataclass(frozen=True)
class DeliveryStepResult:
    step: DeliveryStep
    residual: ArrivalResidual
    pathways: tuple[PathwayResult, ...]
    final_storage: Volume | None
    target_residual_m3: Fraction | None
    checks: CheckSummary


def _process_check(
    identifier: str, supplied: SupportedProcessTest | None, support_subject: object | None = None
) -> Check:
    if supplied is None:
        return Check(identifier, CheckFinding.UNKNOWN, ("required process or quality evidence missing",))
    test = supplied.test
    reasons = _support(test.context, test if support_subject is None else support_subject, supplied.evidence)
    if reasons or test.value is None:
        return Check(
            identifier, CheckFinding.UNKNOWN, reasons + (("process state missing",) if test.value is None else ())
        )
    strict = test.boundary is BoundInclusion.STRICT
    passed = (test.lower is None or (test.value > test.lower if strict else test.value >= test.lower)) and (
        test.upper is None or (test.value < test.upper if strict else test.value <= test.upper)
    )
    return Check(identifier, CheckFinding.PASS if passed else CheckFinding.FAIL)


def _assess_step(step: DeliveryStep) -> DeliveryStepResult:
    b = step.balance
    residual = storage_arrival(b, step.evidence)
    paths = tuple(_path_result(p) for p in step.pathways)
    checks = [
        Check(f"{p.selected.pathway.identifier}:{c.check_id}", c.finding, c.reasons)
        for p in paths
        for c in p.checks.checks
    ]
    complete = bool(step.required_pathways) and set(step.required_pathways) == {
        p.pathway.identifier for p in step.pathways
    }
    checks.append(
        Check(
            "allocation",
            CheckFinding.PASS if complete else CheckFinding.UNKNOWN,
            () if complete else ("responsible operating selection missing; no inferred shares",),
        )
    )
    reasons = _support(b.context, b, step.evidence)
    state = None
    difference = None
    if (
        complete
        and not reasons
        and all(p.arrival is not None and p.checks.finding is not CheckFinding.UNKNOWN for p in paths)
    ):
        net = sum(
            (x.amount.value * (1 if x.direction is ExchangeDirection.INFLOW else -1) for x in b.exchanges), Fraction()
        )
        final = b.initial.value + net + sum((p.arrival.value for p in paths if p.arrival is not None), Fraction())
        if final >= 0:
            state = Volume(final)
        if b.target is not None:
            difference = final - b.target.value
    if step.state_objective is None:
        checks.append(
            Check(
                "storage_target",
                CheckFinding.UNKNOWN
                if difference is None
                else CheckFinding.PASS
                if difference == 0
                else CheckFinding.FAIL,
                ("selected endpoint storage target; no intervening state inferred",),
            )
        )
    else:
        objective = step.state_objective
        coupled_reasons = _support(b.context, step.coupled_subject, step.coupled_evidence)
        if objective.temporal_support is not objective.required_temporal_support:
            coupled_reasons += ("coupled quantity statistic does not cover the required temporal statistic",)
        checks.append(
            Check("coupled_relation", CheckFinding.UNKNOWN if coupled_reasons else CheckFinding.PASS, coupled_reasons)
        )
        inventory_finding = CheckFinding.UNKNOWN
        if (
            not reasons
            and complete
            and all(p.arrival is not None and p.checks.finding is not CheckFinding.UNKNOWN for p in paths)
        ):
            inventory_finding = CheckFinding.PASS if state == objective.final_inventory else CheckFinding.FAIL
        checks.append(
            Check(
                "coupled_water_balance",
                inventory_finding,
                ("recomputed final water inventory must equal supplied physical inventory",),
            )
        )
        quantity = _process_check("quantity:" + objective.quantity.test.identifier, objective.quantity)
        # Unsupported physical representation cannot produce a supported state finding.
        if coupled_reasons or inventory_finding is not CheckFinding.PASS:
            quantity = Check(
                quantity.check_id,
                CheckFinding.UNKNOWN,
                coupled_reasons + ("quantity finding requires supported closed physical representation",),
            )
        checks.append(quantity)
    if not step.required_processes:
        checks.append(
            Check("process_profile", CheckFinding.UNKNOWN, ("required process/quality target profile missing",))
        )
    process_by_id = {p.test.identifier: p for p in step.processes}
    for identifier in step.required_processes:
        supplied = process_by_id.get(identifier)
        objective = step.state_objective
        if objective is not None and identifier == objective.required_salinity:
            role_reasons = ()
            if supplied is None:
                role_reasons = ("required receptor salinity criterion missing",)
            elif (
                supplied.test.variable != "salinity"
                or supplied.test.units != objective.salinity_domain.unit
                or supplied.test.reference != objective.salinity_domain.basis
            ):
                role_reasons = (
                    "salinity variable, units or chemical/compartment basis do not match the declared domain",
                )
            subject = None
            if objective.salinity_support is SalinitySupport.COUPLED_MODEL:
                role_reasons += _support(b.context, step.coupled_subject, step.coupled_evidence)
                if objective.temporal_support is not objective.required_temporal_support:
                    role_reasons += ("coupled salinity does not cover the required temporal statistic",)
                if state != objective.final_inventory:
                    role_reasons += ("coupled salinity lacks a closed physical inventory",)
            else:
                subject = step.salinity_subject
            checks.append(
                Check("process:" + identifier, CheckFinding.UNKNOWN, role_reasons)
                if role_reasons
                else _process_check("process:" + identifier, supplied, subject)
            )
        else:
            checks.append(_process_check("process:" + identifier, supplied))
    if step.state_objective is not None and step.state_objective.required_salinity not in step.required_processes:
        checks.append(
            Check("salinity_profile", CheckFinding.UNKNOWN, ("required receptor salinity criterion missing",))
        )
    why = _support(b.context, step.checking_subject, step.checking_evidence)
    if (
        step.checking_evidence is not None
        and step.evidence is not None
        and (step.checking_evidence.provenance.source == step.evidence.provenance.source)
    ):
        why += ("independent checking source missing",)
    if step.state_objective is not None and step.checking_evidence is not None:
        model_sources = tuple(
            e.provenance.source
            for e in (step.coupled_evidence, step.state_objective.quantity.evidence)
            if e is not None
        )
        if step.checking_evidence.provenance.source in model_sources:
            why += ("independent checking source duplicates coupled model/state source",)
    checks.append(Check("independent_check", CheckFinding.UNKNOWN if why else CheckFinding.PASS, why))
    return DeliveryStepResult(step, residual, paths, state, difference, CheckSummary(tuple(checks)))


@dataclass(frozen=True)
class DeliveryAssessment:
    steps: tuple[DeliveryStepResult, ...]
    checks: CheckSummary
    period: Interval | None


def assess_delivery(steps: tuple[DeliveryStep, ...], *, period: Interval | None = None) -> DeliveryAssessment:
    """Recheck every supplied discrete trajectory step; never fill a missing slot.

    Continuous exposure/quality remains a required supported process test where
    applicable. Endpoint accounting cannot certify unseen intermediate states.
    """
    _tuple(steps, DeliveryStep)
    if period is not None and not isinstance(period, Interval):
        raise TypeError("assessment period requires Interval")
    if period is None and steps:
        period = Interval(steps[0].balance.context.period.start, steps[-1].balance.context.period.end)
    results = []
    checks = []
    if steps and period is not None:
        if any(
            s.balance.context.period.start < period.start or s.balance.context.period.end > period.end for s in steps
        ):
            raise ValueError("step outside declared assessment period")
        covered = (
            steps[0].balance.context.period.start == period.start and steps[-1].balance.context.period.end == period.end
        )
        checks.append(
            Check(
                "period_coverage",
                CheckFinding.PASS if covered else CheckFinding.UNKNOWN,
                () if covered else ("missing assessment boundary intervals",),
            )
        )
    objectives = tuple(s.state_objective for s in steps if s.state_objective is not None)
    if objectives:
        expected = objectives[0].expected_intervals
        if any(o.expected_intervals != expected for o in objectives):
            raise ValueError("coupled objectives must share one fixed expected trajectory")
        actual = tuple(s.balance.context.period for s in steps)
        covered = actual == expected and len(objectives) == len(steps)
        checks.append(
            Check(
                "coupled_trajectory",
                CheckFinding.PASS if covered else CheckFinding.UNKNOWN,
                () if covered else ("complete expected coupled-state trajectory is not supplied",),
            )
        )
    for index, step in enumerate(steps):
        if index:
            previous = steps[index - 1].balance.context
            current = step.balance.context
            if (previous.receptor, previous.candidate, previous.domain, previous.provenance) != (
                current.receptor,
                current.candidate,
                current.domain,
                current.provenance,
            ) or previous.period.end != current.period.start:
                raise ValueError("trajectory identity mismatch or nonadjacent intervals")
            preceding = results[-1].final_storage
            checks.append(
                Check(
                    f"{index}:storage_continuity",
                    CheckFinding.UNKNOWN
                    if preceding is None
                    else CheckFinding.PASS
                    if preceding == step.balance.initial
                    else CheckFinding.FAIL,
                )
            )
            prev_paths = {p.pathway.identifier: p for p in steps[index - 1].pathways}
            for selected in step.pathways:
                p = selected.pathway
                if p.identifier in prev_paths:
                    old = prev_paths[p.identifier]
                    if (
                        p.initial_storage != old.pathway.final_storage
                        or p.predecessor_period != old.pathway.release_period
                        or p.predecessor != Flow(old.release.value / old.pathway.release_period.seconds)
                        or p.control != old.pathway.control
                    ):
                        raise ValueError("pathway storage, control or predecessor contradicts trajectory")
        result = _assess_step(step)
        results.append(result)
        checks.extend(Check(f"{index}:{c.check_id}", c.finding, c.reasons) for c in result.checks.checks)
    return DeliveryAssessment(tuple(results), CheckSummary(tuple(checks)), period)


class WaterRelationship(StrEnum):
    SAME_WATER = "same_water"
    LATERAL = "lateral"


@dataclass(frozen=True)
class ControlMapping:
    """A supported zero-loss, zero-delay mapping for downstream assembly.

    More complex mappings must first use the pathway account. This record does
    not activate quality, select an allocation or issue a duty.
    """

    context: DeliveryContext
    control: Location
    continuing_location: Location
    continuing: Flow
    receptor: Flow
    relationship: WaterRelationship
    source: str

    def __post_init__(self) -> None:
        _text(self.source)
        for v, k in (
            (self.context, DeliveryContext),
            (self.control, Location),
            (self.continuing_location, Location),
            (self.continuing, Flow),
            (self.receptor, Flow),
            (self.relationship, WaterRelationship),
        ):
            if not isinstance(v, k):
                raise TypeError(f"control mapping requires {k.__name__}")


@dataclass(frozen=True)
class ControlEquivalent:
    mapping: ControlMapping
    evidence: EvidenceFindings | None
    upstream: Flow | None
    reasons: tuple[str, ...]


def control_equivalent(mapping: ControlMapping, evidence: EvidenceFindings | None) -> ControlEquivalent:
    """Retain physical equivalence for final assembly, never sum unrelated needs."""
    reasons = _support(mapping.context, mapping, evidence)
    value = None
    if not reasons:
        value = Flow(
            max(mapping.continuing.value, mapping.receptor.value)
            if mapping.relationship is WaterRelationship.SAME_WATER
            else mapping.continuing.value + mapping.receptor.value
        )
    return ControlEquivalent(mapping, evidence, value, reasons)
