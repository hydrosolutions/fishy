"""derive_intake_schedule : DownstreamNeeds × IntakeRelationships → IntakePrescription.

assess_swiss_delivery : SuppliedDuty × DeliveredFlows × FlowProofs → SwissDeliveryAssessment.
Pure Swiss Arts. 35–36 calculations; supplied relationships are not a general routing solver.
"""

from dataclasses import dataclass, replace
from enum import StrEnum
from fractions import Fraction
from hashlib import sha256

from fishy.duties import (
    ComparisonKind,
    Delivery,
    DutyApplicability,
    DutyAssessment,
    Obligation,
    SuppliedDuty,
    assess_duty,
)
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    ProductionMethod,
    Provenance,
    permitted_use,
)
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, check_flow_intervals, interval_use
from fishy.quantities import Flow, FlowBounds, Volume
from fishy.spatial import Location
from fishy.swiss_balancing import BalancingAssessment, assess_balancing
from fishy.swiss_safeguards import assess_safeguard_candidate
from fishy.time import Interval


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("attribution requires nonempty text")


def _identity(left: Provenance, right: Provenance) -> None:
    if any(
        getattr(left, key) != getattr(right, key)
        for key in (
            "scenario",
            "reference_member",
            "reference_kind",
            "configuration_version",
        )
    ):
        raise ValueError("incompatible scenario/member/reference/configuration identity")


def _support(sample: FlowSample, name: str) -> Check:
    supported = (
        sample.presence is Presence.PRESENT
        and sample.coverage is Coverage.COMPLETE
        and interval_use(sample) is IntervalUse.ELIGIBLE
    )
    return Check(
        name,
        CheckFinding.PASS if supported else CheckFinding.UNKNOWN,
        sample.reasons if supported else (*sample.reasons, "unsupported, incomplete or excluded flow"),
    )


def delivery_scope(sample: FlowSample, intended_use: str, *, intake: Location | None = None) -> EvidenceScope:
    """Bind evidence to the full immutable sample and, for routing, the selected intake.

    Rebuild findings after any physical/source/data/version/value change. The digest
    is an identity binding, not evidence authentication or a scientific judgement.
    """
    if not isinstance(sample, FlowSample) or (intake is not None and not isinstance(intake, Location)):
        raise TypeError("delivery scope requires FlowSample and optional Location")
    _text(intended_use)
    digest = sha256(repr((sample, intake)).encode()).hexdigest()
    return EvidenceScope(
        f"swiss-delivery:{digest}",
        sample.location.reach.identifier,
        sample.provenance.reference_member,
        sample.interval,
        intended_use,
    )


def specialist_scope(
    location: Location, interval: Interval, provenance: Provenance, intended_use: str, subject: tuple[str, str]
) -> EvidenceScope:
    """Bind a named measure or condition result to its full spatial and source identity."""
    if (
        not isinstance(location, Location)
        or not isinstance(interval, Interval)
        or not isinstance(provenance, Provenance)
    ):
        raise TypeError("specialist scope requires typed location, interval and provenance")
    if not isinstance(subject, tuple) or len(subject) != 2:
        raise TypeError("subject requires a pair: identifier/description or indicator/result")
    for item in (*subject, intended_use):
        _text(item)
    digest = sha256(repr((location, interval, provenance, subject)).encode()).hexdigest()
    return EvidenceScope(
        f"swiss-specialist:{digest}", location.reach.identifier, provenance.reference_member, interval, intended_use
    )


def _evidence(findings: EvidenceFindings, sample: FlowSample, use: str, *, intake: Location | None = None) -> Check:
    _identity(findings.provenance, sample.provenance)
    expected = delivery_scope(sample, use, intake=intake)
    if findings.scope != expected or findings.provenance != sample.provenance:
        raise ValueError("evidence must match exact subject/source/physical versions/intended use")
    return permitted_use(findings, expected)


@dataclass(frozen=True)
class WaterBalance:
    """Supplied physical account in volumes, including storage and a declared tolerance."""

    initial: Volume
    incoming: Volume
    outgoing: Volume
    final: Volume
    tolerance: Volume
    source: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(v, Volume) for v in (self.initial, self.incoming, self.outgoing, self.final, self.tolerance)
        ):
            raise TypeError("balance quantities require Volume")
        _text(self.source)

    @property
    def check(self) -> Check:
        residual = self.initial.value + self.incoming.value - self.outgoing.value - self.final.value
        return Check(
            "water_balance",
            CheckFinding.PASS if abs(residual) <= self.tolerance.value else CheckFinding.FAIL,
            (self.source, f"signed residual {residual} m3; tolerance {self.tolerance.value} m3"),
        )


class ExchangeRole(StrEnum):
    GAIN = "gain"
    LOSS = "loss"
    ABSTRACTION = "other_abstraction"


@dataclass(frozen=True)
class RoutingExchange:
    account: str
    role: ExchangeRole
    sample: FlowSample

    def __post_init__(self) -> None:
        _text(self.account)
        if not isinstance(self.role, ExchangeRole) or not isinstance(self.sample, FlowSample):
            raise TypeError("routing exchange requires typed role and flow sample")


def relationship_scope(
    intake: Location,
    downstream: FlowSample,
    transmission: Fraction,
    intake_domain: FlowBounds,
    exchanges: tuple[RoutingExchange, ...],
    balance: WaterBalance | None,
    relation_source: str,
) -> EvidenceScope:
    """Scope of the exact reviewed affine relationship, including all operands and accounts."""
    base = delivery_scope(downstream, "intake_prescription", intake=intake)
    digest = sha256(
        repr((intake, downstream, transmission, intake_domain, tuple(exchanges), balance, relation_source)).encode()
    ).hexdigest()
    return replace(base, product=f"swiss-intake-relationship:{digest}")


@dataclass(frozen=True)
class IntakeRelationship:
    """Supplied interval-specific affine relation: downstream = transmission * intake + gains - sinks.

    Applicable only inside intake_domain. Every account is caller-certified disjoint;
    explicit empty exchanges assert no gains/sinks. No topology implies this relation.
    """

    intake: Location
    downstream: FlowSample
    transmission: Fraction
    intake_domain: FlowBounds
    exchanges: tuple[RoutingExchange, ...]
    evidence: EvidenceFindings
    balance: WaterBalance | None
    relation_source: str

    def __post_init__(self) -> None:
        if not isinstance(self.intake, Location) or not isinstance(self.downstream, FlowSample):
            raise TypeError("relationship requires typed intake and downstream sample")
        if not isinstance(self.transmission, Fraction) or not 0 < self.transmission <= 1:
            raise ValueError("transmission requires exact Fraction in (0, 1]")
        if not isinstance(self.intake_domain, FlowBounds) or not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("relationship requires flow domain and scoped evidence")
        if self.balance is not None and not isinstance(self.balance, WaterBalance):
            raise TypeError("relationship balance requires WaterBalance")
        _text(self.relation_source)
        object.__setattr__(self, "exchanges", tuple(self.exchanges))
        if any(not isinstance(e, RoutingExchange) for e in self.exchanges):
            raise TypeError("exchanges require RoutingExchange")
        if len({e.account for e in self.exchanges}) != len(self.exchanges):
            raise ValueError("duplicate water account would double-count an exchange")
        for exchange in self.exchanges:
            _identity(exchange.sample.provenance, self.downstream.provenance)
            if exchange.sample.interval != self.downstream.interval:
                raise ValueError("routing exchange must have exact downstream interval")
            if exchange.sample.location.mapping_version != self.intake.mapping_version:
                raise ValueError("routing exchange has incompatible spatial mapping")
        if self.downstream.location.mapping_version != self.intake.mapping_version:
            raise ValueError("downstream has incompatible spatial mapping")
        if self.evidence.scope != self.scope or self.evidence.provenance != self.downstream.provenance:
            raise ValueError("relationship evidence must bind the exact reviewed subject")

    @property
    def scope(self) -> EvidenceScope:
        return relationship_scope(
            self.intake,
            self.downstream,
            self.transmission,
            self.intake_domain,
            self.exchanges,
            self.balance,
            self.relation_source,
        )


@dataclass(frozen=True)
class ProtectiveMeasure:
    identifier: str
    location: Location
    interval: Interval
    description: str
    evidence: EvidenceFindings

    def __post_init__(self) -> None:
        _text(self.identifier)
        _text(self.description)
        if not isinstance(self.location, Location) or not isinstance(self.interval, Interval):
            raise TypeError("measure requires typed location and interval")
        if not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("measure requires attributed evidence")
        expected = specialist_scope(
            self.location,
            self.interval,
            self.evidence.provenance,
            "protective_measure",
            (self.identifier, self.description),
        )
        if self.evidence.scope != expected:
            raise ValueError("measure evidence scope or intended use mismatch")


@dataclass(frozen=True)
class IntakePrescription:
    """Mathematical candidate, not an issued permission; missing intervals retain unsupported samples."""

    schedule: tuple[FlowSample, ...]
    intake_minima: tuple[FlowSample, ...]
    downstream_needs: tuple[FlowSample, ...]
    relationships: tuple[IntakeRelationship, ...]
    measures: tuple[ProtectiveMeasure, ...]
    summary: CheckSummary
    downstream_assessments: tuple[BalancingAssessment, ...]
    numerical_schedule: tuple[FlowSample, ...]
    projected_downstream: tuple[FlowSample, ...]


def derive_intake_schedule(
    intake_minima: tuple[FlowSample, ...],
    downstream_needs: tuple[FlowSample, ...],
    relationships: tuple[IntakeRelationship, ...],
    *,
    provenance: Provenance,
    upstream_checks: CheckSummary,
    measures: tuple[ProtectiveMeasure, ...] = (),
    downstream_assessments: tuple[BalancingAssessment, ...] = (),
) -> IntakePrescription:
    """Invert supplied relationships and retain Arts. 31–32 intake minima, without a deliverability cap.

    The caller supplies the complete required protection-point/interval set. Each
    shared intake release must satisfy every relationship, including points below a return.
    Unknown or failed mappings cannot yield a supported prescription.
    """
    intake_minima, downstream_needs, relationships, measures = map(
        tuple, (intake_minima, downstream_needs, relationships, measures)
    )
    check_flow_intervals(intake_minima)
    if provenance.production_method is ProductionMethod.OBSERVED:
        raise ValueError("calculated prescription cannot become an observation")
    intake = intake_minima[0].location
    by_period = {s.interval: s for s in intake_minima}
    keys = [(s.location, s.interval) for s in downstream_needs]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate downstream protection point/interval")
    mapping = {(r.downstream.location, r.downstream.interval): r for r in relationships}
    if len(mapping) != len(relationships) or set(mapping) - set(keys):
        raise ValueError("duplicate or undeclared intake relationship")
    for sample in (*intake_minima, *downstream_needs):
        _identity(provenance, sample.provenance)
        if sample.interval not in by_period:
            raise ValueError("downstream need must match an exact intake interval")
    for relation in relationships:
        if (
            relation.intake != intake
            or relation.downstream
            != downstream_needs[keys.index((relation.downstream.location, relation.downstream.interval))]
        ):
            raise ValueError("relationship must reference the exact supplied intake and downstream need")
    for measure in measures:
        _identity(provenance, measure.evidence.provenance)
        if measure.interval not in by_period:
            raise ValueError("measure period must match the prescription")
        if measure.location not in {intake, *(s.location for s in downstream_needs)}:
            raise ValueError("measure location outside the declared affected points")
    rows: list[FlowSample] = []
    if not isinstance(upstream_checks, CheckSummary):
        raise TypeError("upstream_checks requires CheckSummary")
    upstream = upstream_checks.checks or (Check("required", CheckFinding.UNKNOWN, ("upstream assessment missing",)),)
    checks: list[Check] = [replace(c, check_id=f"upstream:{c.check_id}") for c in upstream]
    for index, minimum in enumerate(intake_minima):
        local = [replace(_support(minimum, "minimum"), check_id=f"{index}:minimum")]
        local.extend(
            replace(permitted_use(m.evidence, m.evidence.scope), check_id=f"{index}:measure:{j}")
            for j, m in enumerate(measures)
            if m.interval == minimum.interval
        )
        candidates = [minimum.value.value] if minimum.value is not None else []
        needs = tuple(s for s in downstream_needs if s.interval == minimum.interval)
        if not needs:
            local.append(
                Check(
                    f"{index}:protection_points", CheckFinding.UNKNOWN, ("required affected-reach needs not supplied",)
                )
            )
        active: list[IntakeRelationship] = []
        for j, need in enumerate(needs):
            prefix = f"{index}:{j}"
            local.append(replace(_support(need, "need"), check_id=f"{prefix}:need"))
            relation = mapping.get((need.location, need.interval))
            if relation is None:
                local.append(
                    Check(
                        f"{prefix}:relationship", CheckFinding.UNKNOWN, ("no supported routing relationship supplied",)
                    )
                )
                continue
            active.append(relation)
            local.append(
                replace(
                    permitted_use(relation.evidence, relation.scope),
                    check_id=f"{prefix}:scientific_use",
                )
            )
            local.append(
                replace(relation.balance.check, check_id=f"{prefix}:balance")
                if relation.balance
                else Check(f"{prefix}:balance", CheckFinding.UNKNOWN, ("water balance missing",))
            )
            for k, exchange in enumerate(relation.exchanges):
                local.append(_support(exchange.sample, f"{prefix}:exchange:{k}"))
            operands = (need, *(e.sample for e in relation.exchanges))
            if all(_support(s, "operand").finding is CheckFinding.PASS for s in operands):
                assert need.value is not None
                net = _net_exchange(relation)
                candidates.append(
                    max(relation.intake_domain.lower.value, (need.value.value - net) / relation.transmission)
                )
        candidate = max(candidates) if candidates else Fraction()
        for j, relation in enumerate(active):
            local.append(
                Check(
                    f"{index}:{j}:domain",
                    CheckFinding.PASS
                    if relation.intake_domain.lower.value <= candidate <= relation.intake_domain.upper.value
                    else CheckFinding.FAIL,
                    (relation.relation_source, "shared release tested in supported relation domain"),
                )
            )
        supported = CheckSummary(tuple(local)).finding is CheckFinding.PASS
        rows.append(
            FlowSample(
                intake,
                minimum.interval,
                Flow(candidate) if supported else None,
                Presence.PRESENT if supported else Presence.UNSUPPORTED,
                provenance,
                reasons=(
                    "supplied affine relationships; mathematical candidate, not permission",
                    "uncertainty of inverse routing requires separate supported study",
                )
                if supported
                else ("required downstream mapping, input or balance failed/unresolved",),
                components=(minimum, *needs, *(e.sample for r in active for e in r.exchanges)),
            )
        )
        checks.extend(local)
    numerical_schedule = tuple(rows)
    downstream_checks, reviewed, projected = _assess_projected_needs(
        downstream_needs, relationships, tuple(rows), tuple(downstream_assessments), intake_minima
    )
    checks.extend(downstream_checks.checks)
    summary = CheckSummary(tuple(checks))
    if summary.finding is not CheckFinding.PASS:
        rows = [
            replace(
                row,
                value=None,
                presence=Presence.UNSUPPORTED,
                reasons=(*row.reasons, "actual projected downstream assessment failed or unresolved"),
            )
            for row in rows
        ]
    return IntakePrescription(
        tuple(rows),
        intake_minima,
        downstream_needs,
        relationships,
        measures,
        summary,
        reviewed,
        numerical_schedule,
        projected,
    )


def _assess_projected_needs(
    needs: tuple[FlowSample, ...],
    relationships: tuple[IntakeRelationship, ...],
    intake_schedule: tuple[FlowSample, ...],
    assessments: tuple[BalancingAssessment, ...],
    intake_minima: tuple[FlowSample, ...],
) -> tuple[CheckSummary, tuple[BalancingAssessment, ...], tuple[FlowSample, ...]]:
    """Recompute decisions and recheck actual downstream quantities, never cached passes."""
    if any(not isinstance(a, BalancingAssessment) for a in assessments):
        raise TypeError("downstream_assessments requires actual BalancingAssessment records")
    required = {(s.location, s.interval): s for s in needs}
    declared = [(s.location, s.interval) for a in assessments for s in a.preceding_minimum]
    if len(set(declared)) != len(declared) or set(declared) - set(required):
        raise ValueError("duplicate or undeclared downstream assessment point/interval")
    relations = {(r.downstream.location, r.downstream.interval): r for r in relationships}
    schedule = {s.interval: s for s in intake_schedule}
    projected_by_key: dict[tuple[Location, Interval], FlowSample] = {}
    for key, need in required.items():
        relation = relations.get(key)
        intake = schedule[need.interval]
        supported = (
            relation is not None
            and _support(intake, "intake").finding is CheckFinding.PASS
            and all(_support(e.sample, "exchange").finding is CheckFinding.PASS for e in relation.exchanges)
        )
        value = None
        if supported and relation is not None and intake.value is not None:
            value = Flow(relation.transmission * intake.value.value + _net_exchange(relation))
        projected_by_key[key] = replace(
            need,
            value=value,
            uncertainty=None,
            presence=Presence.PRESENT if value is not None else Presence.UNSUPPORTED,
            reasons=(*need.reasons, "projected actual shared intake release at downstream protection point"),
            components=(need, intake),
            provenance=replace(need.provenance, production_method=ProductionMethod.RECONSTRUCTED),
        )
    checks: list[Check] = []
    reviewed: list[BalancingAssessment] = []
    for index, key in enumerate(required):
        if key not in declared:
            checks.append(
                Check(
                    f"downstream:{index}:assessment",
                    CheckFinding.UNKNOWN,
                    ("actual downstream balancing and safeguards/scoped exception not supplied",),
                )
            )
    for index, previous in enumerate(assessments):
        current = assess_balancing(
            previous.preceding_minimum,
            previous.preceding_summary,
            previous.decision,
            safeguards=previous.safeguards,
            exception=previous.exception,
        )
        reviewed.append(current)
        checks.extend(replace(c, check_id=f"downstream:{index}:original:{c.check_id}") for c in current.summary.checks)
        originals = {(s.location, s.interval): s for s in current.supported_final_total}
        projections: list[FlowSample] = []
        for j, minimum in enumerate(current.preceding_minimum):
            key = (minimum.location, minimum.interval)
            need = required[key]
            matched = originals.get(key) == need
            checks.append(
                Check(
                    f"downstream:{index}:{j}:reviewed_need",
                    CheckFinding.PASS if matched else CheckFinding.UNKNOWN,
                    ("need must equal the actual recomputed supported final total",),
                )
            )
            projected = projected_by_key[key]
            projections.append(projected)
            value = projected.value
            if current.exception is not None:
                minimum_flow = current.exception.applied_minimum
                finding = (
                    CheckFinding.UNKNOWN
                    if value is None or minimum_flow is None
                    else CheckFinding.PASS
                    if value.value >= minimum_flow.value
                    else CheckFinding.FAIL
                )
                checks.append(
                    Check(
                        f"downstream:{index}:{j}:exception_candidate",
                        finding,
                        ("actual downstream flow compared to recomputed exact-scoped exception minimum",),
                    )
                )
        if current.safeguards is not None:
            projected_checks = assess_safeguard_candidate(current.safeguards, tuple(projections))
            checks.extend(
                replace(c, check_id=f"downstream:{index}:projected:{c.check_id}") for c in projected_checks.checks
            )
    checks.extend(_known_lower_bound_conflicts(required, relations, tuple(reviewed), intake_minima))
    return CheckSummary(tuple(checks)), tuple(reviewed), tuple(projected_by_key.values())


def _known_lower_bound_conflicts(
    required: dict[tuple[Location, Interval], FlowSample],
    relations: dict[tuple[Location, Interval], IntakeRelationship],
    reviewed: tuple[BalancingAssessment, ...],
    intake_minima: tuple[FlowSample, ...],
) -> tuple[Check, ...]:
    """Retain guaranteed contradictions without pretending a partial schedule is complete.

    Positive transmission makes each accepted downstream requirement a lower bound
    on shared intake flow. An additional unknown requirement can only raise that
    bound, so it cannot repair a known upper-domain violation at another point.
    """
    supported_relations = {
        key: relation
        for key, relation in relations.items()
        if relation.balance is not None
        and relation.balance.check.finding is CheckFinding.PASS
        and permitted_use(relation.evidence, relation.scope).finding is CheckFinding.PASS
        and all(
            _support(sample, "operand").finding is CheckFinding.PASS
            for sample in (relation.downstream, *(e.sample for e in relation.exchanges))
        )
    }
    lower_bounds: dict[Interval, Flow] = {
        sample.interval: sample.value
        for sample in intake_minima
        if sample.value is not None and _support(sample, "minimum").finding is CheckFinding.PASS
    }
    for assessment in reviewed:
        for need in assessment.supported_final_total:
            key = (need.location, need.interval)
            relation = supported_relations.get(key)
            if required.get(key) != need or relation is None or need.value is None:
                continue
            bound = max(
                relation.intake_domain.lower.value, (need.value.value - _net_exchange(relation)) / relation.transmission
            )
            prior = lower_bounds.get(need.interval)
            lower_bounds[need.interval] = Flow(max(bound, prior.value if prior is not None else Fraction()))
    checks: list[Check] = []
    for index, assessment in enumerate(reviewed):
        if assessment.safeguards is None:
            continue
        bounds_at_sites: dict[tuple[Location, Interval], FlowSample] = {}
        for row in assessment.safeguards.sites:
            site_sample = row.site.starting_minimum
            key = (site_sample.location, site_sample.interval)
            relation = supported_relations.get(key)
            bound = lower_bounds.get(site_sample.interval)
            if relation is None or bound is None:
                continue
            if bound.value > relation.intake_domain.upper.value:
                checks.append(
                    Check(
                        f"downstream:{index}:lower_bound:{row.site.identifier}:routing_domain",
                        CheckFinding.FAIL,
                        (f"required intake lower bound {bound.value} m3/s exceeds supported routing domain",),
                    )
                )
                continue
            projected_bound = relation.transmission * max(
                bound.value, relation.intake_domain.lower.value
            ) + _net_exchange(relation)
            if projected_bound < 0:
                # A negative affine lower bound cannot violate a nonnegative upper domain.
                continue
            value = Flow(projected_bound)
            bounds_at_sites[key] = replace(
                required[key],
                value=value,
                uncertainty=None,
                presence=Presence.PRESENT,
                provenance=replace(site_sample.provenance, production_method=ProductionMethod.RECONSTRUCTED),
                reasons=(
                    *site_sample.reasons,
                    "mathematical downstream lower bound only, not a completed projected flow",
                ),
            )
        bound_checks = assess_safeguard_candidate(assessment.safeguards, tuple(bounds_at_sites.values()))
        findings = {check.check_id: check for check in bound_checks.checks}
        for row in assessment.safeguards.sites:
            key = (row.site.starting_minimum.location, row.site.starting_minimum.interval)
            sample = bounds_at_sites.get(key)
            if sample is None or sample.value is None:
                continue
            for study in row.studies:
                need = study.flow_need
                check = findings.get(row.site.identifier + ":candidate:" + study.safeguard.value)
                if (
                    need is not None
                    and sample.value.value > need.domain_upper.value
                    and check is not None
                    and check.finding is CheckFinding.FAIL
                ):
                    checks.append(
                        Check(
                            f"downstream:{index}:lower_bound:{check.check_id}",
                            CheckFinding.FAIL,
                            (
                                *check.reasons,
                                f"required downstream lower bound {sample.value.value} m3/s exceeds upper domain "
                                f"{need.domain_upper.value} m3/s; unknown additional needs cannot repair this contradiction",
                            ),
                        )
                    )
    return tuple(checks)


def _net_exchange(relation: IntakeRelationship) -> Fraction:
    return sum(
        (
            e.sample.value.value * (1 if e.role is ExchangeRole.GAIN else -1)
            for e in relation.exchanges
            if e.sample.value is not None
        ),
        Fraction(),
    )


class ProofMethod(StrEnum):
    MEASUREMENT = "measurement"
    WATER_BALANCE = "water_balance"


def proof_scope(
    sample: FlowSample,
    method: ProofMethod,
    intended_use: str,
    *,
    balance: WaterBalance | None = None,
    unreasonable_measurement: str | None = None,
) -> EvidenceScope:
    """Bind acceptance to the complete proof, including account tolerance and burden justification."""
    if not isinstance(method, ProofMethod):
        raise TypeError("proof scope requires ProofMethod")
    if balance is not None and not isinstance(balance, WaterBalance):
        raise TypeError("proof scope requires WaterBalance")
    if unreasonable_measurement is not None:
        _text(unreasonable_measurement)
    base = delivery_scope(sample, intended_use)
    digest = sha256(repr((sample, method, balance, unreasonable_measurement)).encode()).hexdigest()
    return replace(base, product=f"swiss-flow-proof:{digest}")


@dataclass(frozen=True)
class FlowProof:
    """Exact scoped evidence for an inflow or delivery, with independent official status."""

    sample: FlowSample
    method: ProofMethod
    evidence: EvidenceFindings
    balance: WaterBalance | None = None
    unreasonable_measurement: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.sample, FlowSample) or not isinstance(self.method, ProofMethod):
            raise TypeError("flow proof requires FlowSample and ProofMethod")
        if not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("flow proof requires EvidenceFindings")
        if self.balance is not None and not isinstance(self.balance, WaterBalance):
            raise TypeError("flow proof balance requires WaterBalance")
        if self.unreasonable_measurement is not None:
            _text(self.unreasonable_measurement)
        if self.method is ProofMethod.MEASUREMENT and self.balance is not None:
            raise ValueError("measurement proof cannot claim water-balance substitution")
        if self.evidence.scope != self.scope or self.evidence.provenance != self.sample.provenance:
            raise ValueError("proof evidence must bind the exact reviewed subject")

    @property
    def scope(self) -> EvidenceScope:
        return proof_scope(
            self.sample,
            self.method,
            self.evidence.scope.intended_use,
            balance=self.balance,
            unreasonable_measurement=self.unreasonable_measurement,
        )


def _proof_checks(proof: FlowProof, use: str) -> CheckSummary:
    expected = proof_scope(
        proof.sample, proof.method, use, balance=proof.balance, unreasonable_measurement=proof.unreasonable_measurement
    )
    if proof.evidence.scope != expected:
        raise ValueError("proof evidence intended use does not match the assessment")
    checks = [
        _support(proof.sample, "flow"),
        replace(permitted_use(proof.evidence, expected), check_id="evidence"),
    ]
    if proof.method is ProofMethod.MEASUREMENT:
        method = proof.sample.provenance.production_method
        checks.append(
            Check(
                "measurement_source",
                CheckFinding.PASS
                if method in (ProductionMethod.OBSERVED, ProductionMethod.ILLUSTRATIVE)
                else CheckFinding.FAIL,
                (
                    "illustrative measurement witness, not observed proof"
                    if method is ProductionMethod.ILLUSTRATIVE
                    else "measurement requires observed data, not simulation or unclassified import",
                ),
            )
        )
    if proof.method is ProofMethod.WATER_BALANCE:
        if proof.balance is not None and proof.sample.value is not None:
            volume = proof.balance.incoming if use == "inflow_proof" else proof.balance.outgoing
            expected = proof.sample.value.value * proof.sample.interval.seconds
            checks.append(
                Check(
                    "balance_flow_binding",
                    CheckFinding.PASS if volume.value == expected else CheckFinding.FAIL,
                    (f"account volume {volume.value} m3; exact flow interval volume {expected} m3",),
                )
            )
        checks.append(
            proof.balance.check
            if proof.balance
            else Check("water_balance", CheckFinding.UNKNOWN, ("water balance not supplied",))
        )
        checks.append(
            Check(
                "measurement_burden",
                CheckFinding.PASS if proof.unreasonable_measurement else CheckFinding.UNKNOWN,
                (proof.unreasonable_measurement or "unreasonable measurement burden not justified",),
            )
        )
    return CheckSummary(tuple(checks))


@dataclass(frozen=True)
class ConditionFinding:
    """Supplied specialist result; never a flow uplift or a release-compliance verdict."""

    location: Location
    interval: Interval
    indicator: str
    result: str
    evidence: EvidenceFindings

    def __post_init__(self) -> None:
        _text(self.indicator)
        _text(self.result)
        if not isinstance(self.location, Location) or not isinstance(self.interval, Interval):
            raise TypeError("condition requires typed location and interval")
        if not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("condition requires attributed evidence")
        expected = specialist_scope(
            self.location,
            self.interval,
            self.evidence.provenance,
            "specialist_condition",
            (self.indicator, self.result),
        )
        if self.evidence.scope != expected:
            raise ValueError("condition evidence scope mismatch")


@dataclass(frozen=True)
class InflowAdjustment:
    nominal: Obligation
    inflow_proof: FlowProof | None
    justified: Obligation
    proof_summary: CheckSummary


@dataclass(frozen=True)
class SwissDeliveryAssessment:
    nominal_duty: SuppliedDuty
    adjustments: tuple[InflowAdjustment, ...]
    delivery: DutyAssessment
    control_evidence: CheckSummary
    conditions: tuple[ConditionFinding, ...]
    delivery_proofs: tuple[FlowProof, ...]


def assess_swiss_delivery(
    duty: SuppliedDuty,
    deliveries: tuple[Delivery, ...],
    *,
    inflow_proofs: tuple[FlowProof, ...] = (),
    delivery_proofs: tuple[FlowProof, ...] = (),
    conditions: tuple[ConditionFinding, ...] = (),
    component_checks: tuple[Check, ...] = (),
) -> SwissDeliveryAssessment:
    """Keep issued duty immutable; supported Art. 36 proof alone can establish all-inflow treatment.

    Arithmetic and Art. 36 control evidence are separate. Conditions link only to
    the same reach/scenario/period, and cannot alter discharge compliance.
    """
    deliveries, inflow_proofs, delivery_proofs, conditions = map(
        tuple, (deliveries, inflow_proofs, delivery_proofs, conditions)
    )
    prescribed = {o.sample.interval: o for o in duty.schedule}
    actual = {d.sample.interval: d for d in deliveries}
    for delivered in deliveries:
        if delivered.sample.interval not in prescribed:
            raise ValueError("delivery outside exact prescribed interval")
        _identity(prescribed[delivered.sample.interval].sample.provenance, delivered.sample.provenance)
    for proofs in (inflow_proofs, delivery_proofs):
        if len({p.sample.interval for p in proofs}) != len(proofs):
            raise ValueError("duplicate flow proof interval")
        for proof in proofs:
            nominal = prescribed.get(proof.sample.interval)
            if nominal is None or nominal.sample.location != proof.sample.location:
                raise ValueError("proof outside exact intake location/interval")
            _identity(nominal.sample.provenance, proof.sample.provenance)
    for condition in conditions:
        nominal = prescribed.get(condition.interval)
        if nominal is None or condition.location.reach != nominal.sample.location.reach:
            raise ValueError("condition must link to same prescribed reach and exact period")
        if condition.location.mapping_version != nominal.sample.location.mapping_version:
            raise ValueError("condition spatial mapping mismatch")
        _identity(nominal.sample.provenance, condition.evidence.provenance)
        if condition.evidence.scope.member != nominal.sample.provenance.reference_member:
            raise ValueError("condition member mismatch")
    inflows = {p.sample.interval: p for p in inflow_proofs}
    adjustments: list[InflowAdjustment] = []
    for nominal in duty.schedule:
        proof = inflows.get(nominal.sample.interval)
        justified = nominal
        summary = (
            _proof_checks(proof, "inflow_proof")
            if proof
            else CheckSummary(
                (
                    Check(
                        "inflow_proof", CheckFinding.UNKNOWN, ("no supported low-inflow proof; nominal duty retained",)
                    ),
                )
            )
        )
        if (
            proof is not None
            and duty.applicability is not DutyApplicability.HYPOTHETICAL
            and proof.sample.provenance.production_method is not ProductionMethod.OBSERVED
        ):
            summary = CheckSummary(
                (
                    *summary.checks,
                    Check(
                        "observed_inflow",
                        CheckFinding.UNKNOWN,
                        ("scenario evidence cannot justify observed compliance or relief against authenticated duty",),
                    ),
                )
            )
        if (
            proof
            and summary.finding is CheckFinding.PASS
            and _support(nominal.sample, "nominal").finding is CheckFinding.PASS
        ):
            assert proof.sample.value is not None and nominal.sample.value is not None
            bounds = proof.sample.uncertainty
            if bounds is not None and bounds.lower != bounds.upper:
                summary = CheckSummary(
                    (
                        *summary.checks,
                        Check(
                            "exact_inflow",
                            CheckFinding.UNKNOWN,
                            ("nondegenerate inflow bounds do not establish an exact substituted duty",),
                        ),
                    )
                )
            elif proof.sample.value.value < nominal.sample.value.value:
                justified = Obligation(
                    replace(
                        nominal.sample,
                        value=proof.sample.value,
                        uncertainty=proof.sample.uncertainty,
                        reasons=(*nominal.sample.reasons, "Art. 36(2) time-specific all-inflow treatment"),
                        components=(nominal.sample, proof.sample),
                    ),
                    nominal.version,
                )
        adjustments.append(InflowAdjustment(nominal, proof, justified, summary))
    justified_duty = replace(duty, schedule=tuple(a.justified for a in adjustments))
    assessment = assess_duty(justified_duty, deliveries, component_checks=component_checks)
    if duty.applicability is DutyApplicability.HYPOTHETICAL or any(
        a.justified != a.nominal
        and a.inflow_proof is not None
        and a.inflow_proof.sample.provenance.production_method is not ProductionMethod.OBSERVED
        for a in adjustments
    ):
        assessment = replace(assessment, interpretation=ComparisonKind.PREDICTION)
    controls: list[Check] = []
    delivery_by_period = {p.sample.interval: p for p in delivery_proofs}
    for i, nominal in enumerate(duty.schedule):
        proof = delivery_by_period.get(nominal.sample.interval)
        delivered = actual.get(nominal.sample.interval)
        if proof is None:
            controls.append(Check(f"{i}:delivery_proof", CheckFinding.UNKNOWN, ("Art. 36(1) delivery proof missing",)))
        else:
            if delivered is None or proof.sample != delivered.sample:
                raise ValueError("delivery proof must reference the exact supplied delivery")
            controls.extend(
                replace(c, check_id=f"{i}:{c.check_id}") for c in _proof_checks(proof, "delivery_proof").checks
            )
    return SwissDeliveryAssessment(
        duty, tuple(adjustments), assessment, CheckSummary(tuple(controls)), conditions, delivery_proofs
    )
