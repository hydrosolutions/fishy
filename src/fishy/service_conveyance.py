"""solve_service_conveyance : ServiceConveyanceRequest → ServiceConveyanceResult (pure).

Appendix A step 7 service balance. Supplied authentication is not legal verification.
Piecewise-linear interval accounting is not a hydraulic simulator or ecological claim.
"""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import CheckFinding, EvidenceFindings, EvidenceScope, permitted_use, warmup_restrictions
from fishy.quantities import Flow, Volume
from fishy.spatial import Location
from fishy.time import Interval


def _text(*values: str) -> None:
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError("nonempty identity, justification and provenance required")


def _typed(*pairs: tuple[object, type]) -> None:
    if any(not isinstance(value, cls) for value, cls in pairs):
        raise TypeError("physical inputs require named domain types")


class DutySource(StrEnum):
    OPERATING_RULE = "operating_rule"
    APPROVING_ACT = "approving_act"
    PERMIT = "permit"
    OBSERVED = "observed"


class Authentication(StrEnum):
    AUTHENTICATED = "authenticated"
    UNRESOLVED = "unresolved"


class ConveyanceStatus(StrEnum):
    SUPPORTED = "supported"
    MISSING = "missing"
    INFEASIBLE = "infeasible"
    UNSUPPORTED = "unsupported"
    NONCONVERGENT = "nonconvergent"


@dataclass(frozen=True)
class ServiceDuty:
    identifier: str
    location: Location
    interval: Interval
    volume: Volume
    source: DutySource
    authentication: Authentication
    evidence: EvidenceFindings
    capacity: Flow

    def __post_init__(self) -> None:
        _text(self.identifier)
        _typed(
            (self.location, Location),
            (self.interval, Interval),
            (self.volume, Volume),
            (self.evidence, EvidenceFindings),
            (self.capacity, Flow),
        )
        if not isinstance(self.source, DutySource) or not isinstance(self.authentication, Authentication):
            raise TypeError("duty source and authentication require enums")


@dataclass(frozen=True)
class ServiceInflow:
    identifier: str
    location: Location
    interval: Interval
    volume: Volume
    evidence: EvidenceFindings

    def __post_init__(self) -> None:
        _text(self.identifier)
        _typed(
            (self.location, Location),
            (self.interval, Interval),
            (self.volume, Volume),
            (self.evidence, EvidenceFindings),
        )


@dataclass(frozen=True)
class ConveyanceLoss:
    identifier: str
    destination: Location
    volume: Volume

    def __post_init__(self) -> None:
        _text(self.identifier)
        _typed((self.destination, Location), (self.volume, Volume))


@dataclass(frozen=True)
class ConveyanceState:
    flow: Flow
    final_storage: Volume
    losses: tuple[ConveyanceLoss, ...]

    def __post_init__(self) -> None:
        _typed((self.flow, Flow), (self.final_storage, Volume))
        if not isinstance(self.losses, tuple) or any(not isinstance(x, ConveyanceLoss) for x in self.losses):
            raise TypeError("losses require immutable named destinations")
        if len({x.identifier for x in self.losses}) != len(self.losses):
            raise ValueError("duplicate loss identifier")


@dataclass(frozen=True)
class ConveyanceRelation:
    identifier: str
    location: Location
    interval: Interval
    initial_storage: Volume
    storage_location: Location
    states: tuple[ConveyanceState, ...]
    geometry_version: str
    boundary_conditions: str
    uncertainty: str
    evidence: EvidenceFindings
    interpolation: str = "piecewise_linear"

    def __post_init__(self) -> None:
        _text(self.identifier, self.geometry_version, self.boundary_conditions, self.uncertainty)
        _typed(
            (self.location, Location),
            (self.interval, Interval),
            (self.initial_storage, Volume),
            (self.storage_location, Location),
            (self.evidence, EvidenceFindings),
        )
        if self.interpolation != "piecewise_linear":
            raise ValueError("only explicit piecewise_linear interpolation is supported")
        if (
            not isinstance(self.states, tuple)
            or len(self.states) < 2
            or any(not isinstance(s, ConveyanceState) for s in self.states)
        ):
            raise ValueError("at least two ordered relation states required")
        if any(a.flow.value >= b.flow.value for a, b in zip(self.states, self.states[1:], strict=False)):
            raise ValueError("relation trial flows must strictly increase")
        destinations = tuple((x.identifier, x.destination) for x in self.states[0].losses)
        if any(tuple((x.identifier, x.destination) for x in s.losses) != destinations for s in self.states):
            raise ValueError("each state must explicitly represent every loss destination, including zero")


@dataclass(frozen=True)
class ConvergenceRule:
    residual_tolerance: Volume
    iteration_limit: int
    justification: str

    def __post_init__(self) -> None:
        _text(self.justification)
        _typed((self.residual_tolerance, Volume))
        if type(self.iteration_limit) is not int or self.iteration_limit < 1:
            raise ValueError("positive integer iteration limit required")


@dataclass(frozen=True)
class ConveyanceRamp:
    """Inclusive directional change bounds on the declared transition interval.

    Bounds are discharge increments, not instantaneous derivatives. The interval
    provides actual elapsed seconds; derived rates are retained in the trace.
    """

    previous_flow: Flow
    transition: Interval
    rise: Flow
    fall: Flow
    evidence: EvidenceFindings

    def __post_init__(self) -> None:
        _typed(
            (self.previous_flow, Flow),
            (self.transition, Interval),
            (self.rise, Flow),
            (self.fall, Flow),
            (self.evidence, EvidenceFindings),
        )


@dataclass(frozen=True)
class ServiceConveyanceRequest:
    location: Location
    interval: Interval
    duties: tuple[ServiceDuty, ...]
    relation: ConveyanceRelation | None
    other_inflows: tuple[ServiceInflow, ...]
    initial_flow: Flow
    stopping: ConvergenceRule
    capacity: Flow | None
    ramp: ConveyanceRamp | None

    def __post_init__(self) -> None:
        _typed(
            (self.location, Location),
            (self.interval, Interval),
            (self.initial_flow, Flow),
            (self.stopping, ConvergenceRule),
        )
        for value, cls in ((self.relation, ConveyanceRelation), (self.capacity, Flow), (self.ramp, ConveyanceRamp)):
            if value is not None:
                _typed((value, cls))
        for values, cls in ((self.duties, ServiceDuty), (self.other_inflows, ServiceInflow)):
            if not isinstance(values, tuple) or any(not isinstance(v, cls) for v in values):
                raise TypeError("immutable typed service records required")
        ids = [x.identifier for x in (*self.duties, *self.other_inflows)]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate water carrier identifier")
        for x in (*self.duties, *self.other_inflows):
            if x.interval != self.interval:
                raise ValueError("exact service accounting interval required; no implicit resampling")
        if self.relation is not None and (
            self.relation.location != self.location or self.relation.interval != self.interval
        ):
            raise ValueError("relation location/interval mismatch")
        evidence = [x.evidence for x in (*self.duties, *self.other_inflows)]
        if self.relation is not None:
            evidence.append(self.relation.evidence)
        if self.ramp is not None:
            evidence.append(self.ramp.evidence)
            if self.ramp.transition.end != self.interval.start:
                raise ValueError("ramp transition must end at service interval start")
        identities = {(e.provenance.scenario, e.provenance.reference_member) for e in evidence}
        if len(identities) > 1:
            raise ValueError("incompatible scenario/reference member")


@dataclass(frozen=True)
class ConveyanceTrial:
    iteration: int
    flow: Flow
    state: ConveyanceState
    required_volume_m3: Fraction
    residual_m3: Fraction
    capacity_check: CheckFinding
    ramp_check: CheckFinding
    transition_rate_m3_s2: Fraction


@dataclass(frozen=True)
class ServiceConveyanceResult:
    request: ServiceConveyanceRequest
    status: ConveyanceStatus
    flow: Flow | None
    selected_duties: tuple[ServiceDuty, ...]
    trace: tuple[ConveyanceTrial, ...]
    reasons: tuple[str, ...]
    limitations: tuple[str, ...] = ("service balance only; no ecological adequacy or issued obligation",)


def _support_reasons(evidence: EvidenceFindings, product: str, location: Location, period: Interval) -> tuple[str, ...]:
    scope = EvidenceScope(
        product, location.reach.identifier, evidence.provenance.reference_member, period, "service_conveyance"
    )
    check = permitted_use(evidence, scope)
    return warmup_restrictions(evidence.provenance, period) + (
        check.reasons if check.finding is not CheckFinding.PASS else ()
    )


def _state(relation: ConveyanceRelation, flow: Flow) -> ConveyanceState | None:
    for left, right in zip(relation.states, relation.states[1:], strict=False):
        if left.flow.value <= flow.value <= right.flow.value:
            weight = (flow.value - left.flow.value) / (right.flow.value - left.flow.value)
            storage = left.final_storage.value + weight * (right.final_storage.value - left.final_storage.value)
            losses = tuple(
                ConveyanceLoss(
                    a.identifier, a.destination, Volume(a.volume.value + weight * (b.volume.value - a.volume.value))
                )
                for a, b in zip(left.losses, right.losses, strict=True)
            )
            return ConveyanceState(flow, Volume(storage), losses)
    return None


def solve_service_conveyance(request: ServiceConveyanceRequest) -> ServiceConveyanceResult:
    """Solve fixed-point interval balance; no extrapolation or accepted failed iterate.

    Evidence products equal record identifiers; ramp evidence product is
    ``conveyance_ramp``. All evidence uses ``service_conveyance`` at exact scopes.
    Empty loss tuples explicitly mean accepted zero losses, never missing losses.
    Missing loss knowledge must be represented by an absent/unsupported relation.
    """
    selected: list[ServiceDuty] = []
    trace: list[ConveyanceTrial] = []

    def result(status: ConveyanceStatus, *reasons: str, flow: Flow | None = None) -> ServiceConveyanceResult:
        return ServiceConveyanceResult(request, status, flow, tuple(selected), tuple(trace), reasons)

    for location in dict.fromkeys(d.location for d in request.duties):
        candidates = [
            d
            for d in request.duties
            if d.location == location
            and d.authentication is Authentication.AUTHENTICATED
            and d.source is not DutySource.OBSERVED
        ]
        primary = [d for d in candidates if d.source in (DutySource.OPERATING_RULE, DutySource.APPROVING_ACT)]
        candidates = primary or [d for d in candidates if d.source is DutySource.PERMIT]
        if not candidates:
            return result(ConveyanceStatus.MISSING, "authenticated duty missing; observations are not duties")
        if len(candidates) != 1:
            raise ValueError("contradictory duplicate duties at same named service point")
        duty = candidates[0]
        selected.append(duty)
        if reasons := _support_reasons(duty.evidence, duty.identifier, duty.location, duty.interval):
            return result(ConveyanceStatus.UNSUPPORTED, "selected duty evidence unsupported", *reasons)
        if duty.volume.value > duty.capacity.value * request.interval.seconds:
            return result(ConveyanceStatus.INFEASIBLE, "service point capacity exceeded")
    if not selected:
        return result(ConveyanceStatus.MISSING, "no authenticated service duty")
    relation, ramp = request.relation, request.ramp
    if relation is None:
        return result(ConveyanceStatus.MISSING, "accepted storage/loss relation missing; unknown losses are not zero")
    if request.capacity is None or ramp is None:
        return result(ConveyanceStatus.MISSING, "capacity/ramping evidence missing")
    if reasons := _support_reasons(relation.evidence, relation.identifier, relation.location, relation.interval):
        return result(ConveyanceStatus.UNSUPPORTED, "conveyance relation unsupported", *reasons)
    if reasons := _support_reasons(ramp.evidence, "conveyance_ramp", request.location, ramp.transition):
        return result(ConveyanceStatus.UNSUPPORTED, "ramping evidence unsupported", *reasons)
    for inflow in request.other_inflows:
        if reasons := _support_reasons(inflow.evidence, inflow.identifier, inflow.location, inflow.interval):
            return result(ConveyanceStatus.UNSUPPORTED, "other inflow timing/location evidence unsupported", *reasons)
    fixed = sum(d.volume.value for d in selected) - sum(i.volume.value for i in request.other_inflows)
    flow = request.initial_flow
    for iteration in range(1, request.stopping.iteration_limit + 1):
        state = _state(relation, flow)
        if state is None:
            return result(ConveyanceStatus.UNSUPPORTED, "trial outside accepted relation domain")
        required = (
            fixed
            + state.final_storage.value
            - relation.initial_storage.value
            + sum(x.volume.value for x in state.losses)
        )
        residual = flow.value * request.interval.seconds - required
        capacity = CheckFinding.PASS if flow.value <= request.capacity.value else CheckFinding.FAIL
        delta = flow.value - ramp.previous_flow.value
        ramp_check = CheckFinding.PASS if -ramp.fall.value <= delta <= ramp.rise.value else CheckFinding.FAIL
        trace.append(
            ConveyanceTrial(
                iteration, flow, state, required, residual, capacity, ramp_check, delta / ramp.transition.seconds
            )
        )
        if required < 0:
            return result(
                ConveyanceStatus.UNSUPPORTED, "unsupported reversal: accepted inflows/storage exceed service balance"
            )
        if abs(residual) <= request.stopping.residual_tolerance.value:
            if capacity is CheckFinding.FAIL or ramp_check is CheckFinding.FAIL:
                return result(ConveyanceStatus.INFEASIBLE, "converged candidate fails capacity/ramping checks")
            if flow.value == 0:
                return result(ConveyanceStatus.UNSUPPORTED, "zero requires separate approved service determination")
            return result(
                ConveyanceStatus.SUPPORTED, "balance converged within predeclared volume tolerance", flow=flow
            )
        flow = Flow(required / request.interval.seconds)
    return result(ConveyanceStatus.NONCONVERGENT, "iteration limit reached; last trial is not an accepted answer")
