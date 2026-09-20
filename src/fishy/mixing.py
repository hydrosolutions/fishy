"""solve_mixing : FixedBoundary × QualityTargets × FlowConstraints → MixingResult.

Exact point-case fixed-boundary screens, not process models or activated duties.
"""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import Provenance
from fishy.quality import (
    ChemicalBehavior,
    ChemicalIdentity,
    Comparison,
    GroupTarget,
    QualityTarget,
    QualityValue,
    RelativeTarget,
    UnresolvedTarget,
)
from fishy.quantities import Flow, Number, finite_number
from fishy.spatial import Location
from fishy.time import Interval

type MixingTarget = QualityTarget | GroupTarget | UnresolvedTarget


class Endpoint(StrEnum):
    CLOSED = "closed"
    OPEN = "open"


class Feasibility(StrEnum):
    FEASIBLE = "feasible"
    CAPACITY_LIMITED = "capacity-limited"
    SOURCE_WATER_INFEASIBLE = "source-water-infeasible"
    INDETERMINATE = "indeterminate"


class CheckOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, init=False)
class LoadRate:
    """Nonnegative constituent mass rate in kg/s."""

    value: Fraction

    def __init__(self, value: Number, unit: str = "kg/s") -> None:
        if unit != "kg/s":
            raise ValueError("load rate requires kg/s")
        amount = finite_number(value)
        if amount < 0:
            raise ValueError("load rate cannot be negative")
        object.__setattr__(self, "value", amount)


@dataclass(frozen=True)
class BoundarySupport:
    """Evidence for a fixed, completely mixed, conservative point-input boundary.

    Declaration must cover exclusion of arrival water/load from background,
    all other carriers and separate loads counted once, fixed inputs as arrival
    varies, and representative mixing. Limitations disable sizing support.
    """

    declaration: str
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.declaration, str) or not self.declaration.strip():
            raise ValueError("fixed-boundary support requires an evidence declaration")
        if not isinstance(self.limitations, tuple) or any(not isinstance(s, str) or not s for s in self.limitations):
            raise ValueError("support limitations require immutable nonempty reasons")


@dataclass(frozen=True)
class MixingConstituent:
    chemical: ChemicalIdentity
    background_load: LoadRate
    source_concentration: QualityValue

    def __post_init__(self) -> None:
        if not isinstance(self.chemical, ChemicalIdentity) or not isinstance(self.background_load, LoadRate):
            raise TypeError("mixing constituent requires chemical identity and LoadRate")
        if not isinstance(self.source_concentration, QualityValue) or self.source_concentration.unit != "kg/m3":
            raise ValueError("source concentration requires mass/volume units")


@dataclass(frozen=True)
class FixedBoundary:
    location: Location
    interval: Interval
    background: Flow
    constituents: tuple[MixingConstituent, ...]
    support: BoundarySupport
    provenance: Provenance

    def __post_init__(self) -> None:
        for value, kind in (
            (self.location, Location),
            (self.interval, Interval),
            (self.background, Flow),
            (self.support, BoundarySupport),
            (self.provenance, Provenance),
        ):
            if not isinstance(value, kind):
                raise TypeError("fixed boundary requires typed location, interval, flow and support")
        if not isinstance(self.constituents, tuple) or any(
            not isinstance(c, MixingConstituent) for c in self.constituents
        ):
            raise TypeError("constituents require an immutable tuple")
        names = [c.chemical.identifier for c in self.constituents]
        if len(names) != len(set(names)):
            raise ValueError("duplicate boundary constituent")


@dataclass(frozen=True)
class FlowConstraints:
    """Arrival bounds and matched section total; no upstream release inference."""

    location: Location
    interval: Interval
    minimum: Flow = Flow(0)
    maximum: Flow | None = None
    capacity: Flow | None = None
    ecological_total: Flow | None = None
    lower_endpoint: Endpoint = Endpoint.CLOSED
    upper_endpoint: Endpoint = Endpoint.CLOSED

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location) or not isinstance(self.interval, Interval):
            raise TypeError("flow constraints require typed section and interval")
        if not isinstance(self.minimum, Flow):
            raise TypeError("minimum requires Flow")
        for value in (self.maximum, self.capacity, self.ecological_total):
            if value is not None and not isinstance(value, Flow):
                raise TypeError("flow bounds require Flow")
        if not isinstance(self.lower_endpoint, Endpoint) or not isinstance(self.upper_endpoint, Endpoint):
            raise TypeError("bound endpoints require Endpoint")


@dataclass(frozen=True)
class LinearConstraint:
    """An exact a*x <= b (or < b), with attributable original test identity."""

    identifier: str
    coefficient: Fraction
    rhs: Fraction
    endpoint: Endpoint = Endpoint.CLOSED

    def __post_init__(self) -> None:
        if not isinstance(self.identifier, str) or not self.identifier:
            raise ValueError("constraint identity required")
        if not isinstance(self.coefficient, Fraction) or not isinstance(self.rhs, Fraction):
            raise TypeError("linear constraints require exact fractions")
        if not isinstance(self.endpoint, Endpoint):
            raise TypeError("constraint requires Endpoint")

    def accepts(self, value: Fraction) -> bool:
        product = self.coefficient * value
        return product <= self.rhs if self.endpoint is Endpoint.CLOSED else product < self.rhs


@dataclass(frozen=True)
class FeasibleInterval:
    lower: Fraction
    upper: Fraction | None
    lower_endpoint: Endpoint
    upper_endpoint: Endpoint
    lower_binding: tuple[str, ...]
    upper_binding: tuple[str, ...]
    contradictions: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return bool(self.contradictions) or (
            self.upper is not None
            and (
                self.lower > self.upper
                or (
                    self.lower == self.upper
                    and (self.lower_endpoint is Endpoint.OPEN or self.upper_endpoint is Endpoint.OPEN)
                )
            )
        )

    @property
    def minimum(self) -> Fraction | None:
        return self.lower if not self.empty and self.lower_endpoint is Endpoint.CLOSED else None

    @property
    def infimum(self) -> Fraction | None:
        return None if self.empty else self.lower

    def contains(self, value: Fraction) -> bool:
        return (
            not self.empty
            and (value > self.lower or (value == self.lower and self.lower_endpoint is Endpoint.CLOSED))
            and (
                self.upper is None
                or value < self.upper
                or (value == self.upper and self.upper_endpoint is Endpoint.CLOSED)
            )
        )


def intersect_constraints(constraints: tuple[LinearConstraint, ...]) -> FeasibleInterval:
    """Intersect constraints on a nonnegative scalar, without floating tolerances."""
    lo, hi = Fraction(0), None
    le, he = Endpoint.CLOSED, Endpoint.CLOSED
    lb, hb, impossible = ("nonnegative",), (), ()
    for c in constraints:
        a, b = c.coefficient, c.rhs
        if a == 0:
            if not c.accepts(Fraction(0)):
                impossible += (c.identifier,)
            continue
        edge = b / a
        if a < 0:
            if edge > lo:
                lo, le, lb = edge, c.endpoint, (c.identifier,)
            elif edge == lo:
                lb += (c.identifier,)
                if c.endpoint is Endpoint.OPEN:
                    le = Endpoint.OPEN
        elif hi is None or edge < hi:
            hi, he, hb = edge, c.endpoint, (c.identifier,)
        elif edge == hi:
            hb += (c.identifier,)
            if c.endpoint is Endpoint.OPEN:
                he = Endpoint.OPEN
    return FeasibleInterval(lo, hi, le, he, lb, hb, impossible)


@dataclass(frozen=True)
class CandidateCheck:
    identifier: str
    value: Fraction | None
    outcome: CheckOutcome
    reason: str = ""


@dataclass(frozen=True)
class MixingRecheck:
    arrival: Flow
    total: Flow
    predictions: tuple[tuple[ChemicalIdentity, QualityValue], ...]
    checks: tuple[CandidateCheck, ...]

    @property
    def outcome(self) -> CheckOutcome:
        if any(c.outcome is CheckOutcome.FAIL for c in self.checks):
            return CheckOutcome.FAIL
        if not self.checks or any(c.outcome is CheckOutcome.INDETERMINATE for c in self.checks):
            return CheckOutcome.INDETERMINATE
        return CheckOutcome.PASS


@dataclass(frozen=True)
class MixingResult:
    boundary: FixedBoundary
    targets: tuple[MixingTarget, ...]
    bounds: FlowConstraints | None
    quality_interval: FeasibleInterval
    combined_interval: FeasibleInterval
    status: Feasibility
    reasons: tuple[str, ...]
    unresolved: tuple[str, ...]
    quality_total: Flow | None
    candidate: MixingRecheck | None
    capacity_check: MixingRecheck | None


def _targets(targets: tuple[MixingTarget, ...]) -> None:
    if not isinstance(targets, tuple) or not targets:
        raise ValueError("sizing requires a nonempty immutable required target set")
    if any(not isinstance(t, (QualityTarget, GroupTarget, UnresolvedTarget)) for t in targets):
        raise TypeError("unsupported mixing target type")
    if len({t.identifier for t in targets}) != len(targets):
        raise ValueError("duplicate target identity")


def _terms(boundary: FixedBoundary, target: MixingTarget) -> tuple[Fraction, Fraction, Fraction] | str:
    if isinstance(target, RelativeTarget):
        return "relative-reference targets require supplied process assessment, not absolute mixing sizing"
    if isinstance(target, UnresolvedTarget):
        return target.reason
    if target.operator is Comparison.UNRESOLVED_UPPER:
        return "source equality interpretation unresolved"
    members = (
        ((target.chemical, Fraction(1)),)
        if isinstance(target, QualityTarget)
        else tuple((m.chemical, m.denominator.value) for m in target.members)
    )
    load, source = Fraction(0), Fraction(0)
    for chemical, denominator in members:
        if chemical.behavior is ChemicalBehavior.PROCESS:
            return f"{chemical.identifier}: process output cannot size conservative mixing"
        entry = next((c for c in boundary.constituents if c.chemical.identifier == chemical.identifier), None)
        if entry is None:
            return f"{chemical.identifier}: missing boundary constituent"
        if entry.chemical != chemical:
            return f"{chemical.identifier}: chemical identity or reporting basis mismatch"
        if denominator <= 0:
            raise ValueError("group denominator must be positive")
        load += entry.background_load.value / denominator
        source += entry.source_concentration.value / denominator
    if isinstance(target, QualityTarget):
        if target.limit.unit != "kg/m3":
            return "conservative sizing requires mass concentration target"
        threshold = target.limit.value
    else:
        threshold = target.limit
    return load, source, threshold


def _linear(identifier: str, a: Fraction, b: Fraction, operator: Comparison) -> LinearConstraint:
    if operator in (Comparison.GE, Comparison.GT):
        a, b = -a, -b
    endpoint = Endpoint.OPEN if operator in (Comparison.LT, Comparison.GT) else Endpoint.CLOSED
    return LinearConstraint(identifier, a, b, endpoint)


def quality_constraints(
    boundary: FixedBoundary, targets: tuple[MixingTarget, ...]
) -> tuple[tuple[LinearConstraint, ...], tuple[str, ...]]:
    _targets(targets)
    constraints, missing = [], list(boundary.support.limitations)
    for target in targets:
        terms = _terms(boundary, target)
        if isinstance(terms, str):
            missing.append(f"{target.identifier}: {terms}")
        else:
            load, source, threshold = terms
            assert not isinstance(target, UnresolvedTarget)
            constraints.append(
                _linear(
                    target.identifier, source - threshold, threshold * boundary.background.value - load, target.operator
                )
            )
    return tuple(constraints), tuple(missing)


def _flow_constraints(
    boundary: FixedBoundary, bounds: FlowConstraints | None, *, include_capacity: bool = True
) -> tuple[LinearConstraint, ...]:
    if bounds is None:
        return ()
    if bounds.location != boundary.location or bounds.interval != boundary.interval:
        raise ValueError("operational/ecological bounds must match boundary section and interval")
    output = [LinearConstraint("operational-minimum", Fraction(-1), -bounds.minimum.value, bounds.lower_endpoint)]
    if bounds.maximum is not None:
        output.append(LinearConstraint("operational-maximum", Fraction(1), bounds.maximum.value, bounds.upper_endpoint))
    if bounds.ecological_total is not None:
        output.append(
            LinearConstraint(
                "ecological-total",
                Fraction(-1),
                -max(Fraction(0), bounds.ecological_total.value - boundary.background.value),
            )
        )
    if include_capacity and bounds.capacity is not None:
        output.append(LinearConstraint("capacity", Fraction(1), bounds.capacity.value))
    return tuple(output)


def recheck_mixing(
    boundary: FixedBoundary, targets: tuple[MixingTarget, ...], arrival: Flow, bounds: FlowConstraints | None = None
) -> MixingRecheck:
    """Substitute an external/final arrival into the original concentration tests."""
    _targets(targets)
    if not isinstance(arrival, Flow):
        raise TypeError("arrival requires Flow")
    total = Flow(boundary.background.value + arrival.value)
    predictions = (
        tuple(
            (
                c.chemical,
                QualityValue(
                    (c.background_load.value + arrival.value * c.source_concentration.value) / total.value, "kg/m3"
                ),
            )
            for c in boundary.constituents
            if c.chemical.behavior is not ChemicalBehavior.PROCESS
        )
        if total.value
        else ()
    )
    checks = []
    for target in targets:
        terms = _terms(boundary, target)
        if boundary.support.limitations or isinstance(terms, str) or total.value == 0:
            reason = "; ".join(boundary.support.limitations) or (
                terms if isinstance(terms, str) else "zero total flow: concentration undefined"
            )
            checks.append(CandidateCheck(target.identifier, None, CheckOutcome.INDETERMINATE, reason))
            continue
        load, source, threshold = terms
        value = (load + arrival.value * source) / total.value
        assert not isinstance(target, UnresolvedTarget)
        accepted = _linear(target.identifier, Fraction(0), threshold - value, target.operator).accepts(Fraction(0))
        checks.append(CandidateCheck(target.identifier, value, CheckOutcome.PASS if accepted else CheckOutcome.FAIL))
    for constraint in _flow_constraints(boundary, bounds):
        checks.append(
            CandidateCheck(
                constraint.identifier,
                arrival.value,
                CheckOutcome.PASS if constraint.accepts(arrival.value) else CheckOutcome.FAIL,
            )
        )
    return MixingRecheck(arrival, total, predictions, tuple(checks))


def solve_mixing(
    boundary: FixedBoundary, targets: tuple[MixingTarget, ...], bounds: FlowConstraints | None = None
) -> MixingResult:
    constraints, missing = quality_constraints(boundary, targets)
    physical = (LinearConstraint("positive-total-water", Fraction(-1), boundary.background.value, Endpoint.OPEN),)
    raw = intersect_constraints(physical + constraints)
    compatible = intersect_constraints(
        physical + constraints + _flow_constraints(boundary, bounds, include_capacity=False)
    )
    combined = intersect_constraints(physical + constraints + _flow_constraints(boundary, bounds))
    reasons = ()
    if boundary.support.limitations:
        status, reasons = Feasibility.INDETERMINATE, ("unsupported fixed-boundary assumptions",)
    elif raw.empty:
        individually_impossible = any(intersect_constraints(physical + (c,)).empty for c in constraints)
        status = Feasibility.SOURCE_WATER_INFEASIBLE if individually_impossible else Feasibility.INDETERMINATE
        reasons = (
            (
                "known source-water impossibility"
                if individually_impossible
                else "known conflicting quality constraints",
            )
            + raw.contradictions
            + raw.lower_binding
            + raw.upper_binding
        )
    elif compatible.empty:
        status, reasons = (
            Feasibility.INDETERMINATE,
            ("known conflicting ecological/operational and quality constraints",)
            + compatible.lower_binding
            + compatible.upper_binding,
        )
    elif combined.empty:
        status, reasons = Feasibility.CAPACITY_LIMITED, ("compatible interval exceeds available capacity",)
    elif missing:
        status, reasons = Feasibility.INDETERMINATE, ("required quality evidence incomplete",)
    else:
        status = Feasibility.FEASIBLE
    quality_total = Flow(boundary.background.value + raw.minimum) if raw.minimum is not None and not missing else None
    candidate = (
        recheck_mixing(boundary, targets, Flow(combined.minimum), bounds)
        if combined.minimum is not None and not missing
        else None
    )
    capacity_check = (
        recheck_mixing(boundary, targets, bounds.capacity, bounds)
        if bounds is not None and bounds.capacity is not None
        else None
    )
    return MixingResult(
        boundary, targets, bounds, raw, combined, status, reasons, missing, quality_total, candidate, capacity_check
    )
