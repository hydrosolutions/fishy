"""source_control : FixedDischarge × ControllableLoads × QualityTargets → LoadControlResult.

Diagnostic fixed-water load reduction, not permits or allocation among polluters.
"""

from dataclasses import dataclass
from fractions import Fraction

from fishy.evidence import Provenance, warmup_restrictions
from fishy.mixing import (
    BoundarySupport,
    CandidateCheck,
    CheckOutcome,
    FeasibleInterval,
    FixedBoundary,
    LinearConstraint,
    LoadRate,
    MixingConstituent,
    MixingTarget,
    _linear,
    _targets,
    _terms,
    intersect_constraints,
)
from fishy.quality import ChemicalIdentity, GroupTarget, QualityTarget, QualityValue, UnresolvedTarget
from fishy.quantities import Flow
from fishy.spatial import Location
from fishy.time import Interval


@dataclass(frozen=True)
class SingleLoadResult:
    allowance: LoadRate | None
    reduction: LoadRate | None
    outcome: CheckOutcome
    reason: str


def screen_single_load(
    discharge: Flow, limit: QualityValue, other_load: LoadRate, controlled_load: LoadRate
) -> SingleLoadResult:
    """Inclusive upper-limit screen at fixed discharge; no negative allowance."""
    if (
        not isinstance(discharge, Flow)
        or not isinstance(other_load, LoadRate)
        or not isinstance(controlled_load, LoadRate)
    ):
        raise TypeError("source control requires Flow and LoadRate")
    if not isinstance(limit, QualityValue) or limit.unit != "kg/m3":
        raise ValueError("source control limit requires mass concentration")
    if discharge.value == 0:
        return SingleLoadResult(None, None, CheckOutcome.INDETERMINATE, "zero discharge: concentration undefined")
    allowance = limit.value * discharge.value - other_load.value
    if allowance < 0:
        return SingleLoadResult(
            None, None, CheckOutcome.FAIL, "background alone exceeds limit; no permitted negative load"
        )
    return SingleLoadResult(
        LoadRate(allowance),
        LoadRate(max(Fraction(0), controlled_load.value - allowance)),
        CheckOutcome.PASS,
        "diagnostic maximum load, not a discharge permit",
    )


@dataclass(frozen=True)
class ControlledLoad:
    chemical: ChemicalIdentity
    other: LoadRate
    controlled: LoadRate

    def __post_init__(self) -> None:
        if (
            not isinstance(self.chemical, ChemicalIdentity)
            or not isinstance(self.other, LoadRate)
            or not isinstance(self.controlled, LoadRate)
        ):
            raise TypeError("controlled load requires chemical identity and exact load rates")


@dataclass(frozen=True)
class DrainBoundary:
    """All drain water stays fixed while one common factor scales its loads."""

    location: Location
    interval: Interval
    discharge: Flow
    loads: tuple[ControlledLoad, ...]
    support: BoundarySupport
    provenance: Provenance

    def __post_init__(self) -> None:
        if (
            not isinstance(self.location, Location)
            or not isinstance(self.interval, Interval)
            or not isinstance(self.discharge, Flow)
            or not isinstance(self.support, BoundarySupport)
            or not isinstance(self.provenance, Provenance)
        ):
            raise TypeError("drain boundary requires typed location, interval, discharge and support")
        if not isinstance(self.loads, tuple) or any(not isinstance(c, ControlledLoad) for c in self.loads):
            raise TypeError("drain loads require an immutable tuple")
        if len({c.chemical.identifier for c in self.loads}) != len(self.loads):
            raise ValueError("duplicate drain constituent")

    @property
    def limitations(self) -> tuple[str, ...]:
        return self.support.limitations + warmup_restrictions(self.provenance, self.interval)


@dataclass(frozen=True)
class DrainControlResult:
    boundary: DrainBoundary
    targets: tuple[MixingTarget, ...]
    factor_interval: FeasibleInterval
    outcome: CheckOutcome
    unresolved: tuple[str, ...]
    reasons: tuple[str, ...]


def _background(boundary: DrainBoundary) -> FixedBoundary:
    return FixedBoundary(
        boundary.location,
        boundary.interval,
        boundary.discharge,
        tuple(MixingConstituent(c.chemical, c.other, QualityValue(0, "kg/m3")) for c in boundary.loads),
        boundary.support,
        boundary.provenance,
    )


def _controlled(boundary: DrainBoundary, target: QualityTarget | GroupTarget) -> Fraction:
    members = (
        ((target.chemical, Fraction(1)),)
        if isinstance(target, QualityTarget)
        else tuple((m.chemical, m.denominator.value) for m in target.members)
    )
    return sum(
        (
            next(c.controlled.value for c in boundary.loads if c.chemical == chemical) / denominator
            for chemical, denominator in members
        ),
        Fraction(0),
    )


def solve_drain_control(boundary: DrainBoundary, targets: tuple[MixingTarget, ...]) -> DrainControlResult:
    _targets(targets)
    background = _background(boundary)
    constraints = [LinearConstraint("whole-drain-factor", Fraction(1), Fraction(1))]
    missing = list(boundary.limitations)
    if boundary.discharge.value == 0:
        missing.append("zero discharge: concentration undefined")
    for target in targets:
        terms = _terms(background, target)
        if isinstance(terms, str):
            missing.append(f"{target.identifier}: {terms}")
            continue
        assert not isinstance(target, UnresolvedTarget)
        load, _, limit = terms
        constraints.append(
            _linear(
                target.identifier,
                _controlled(boundary, target),
                limit * boundary.discharge.value - load,
                target.operator,
            )
        )
    interval = intersect_constraints(tuple(constraints))
    if boundary.limitations or boundary.discharge.value == 0:
        outcome = CheckOutcome.INDETERMINATE
    elif interval.empty:
        outcome = CheckOutcome.FAIL
    elif missing:
        outcome = CheckOutcome.INDETERMINATE
    else:
        outcome = CheckOutcome.PASS
    reasons = (
        ("known conflicting load constraints",)
        + interval.contradictions
        + interval.lower_binding
        + interval.upper_binding
        if interval.empty
        else ("fixed drain water; diagnostic screen, not a discharge permit",)
    )
    return DrainControlResult(boundary, targets, interval, outcome, tuple(missing), reasons)


def recheck_drain_control(
    boundary: DrainBoundary, targets: tuple[MixingTarget, ...], factor: Fraction
) -> tuple[CandidateCheck, ...]:
    """Recheck every original concentration test after an external factor choice."""
    _targets(targets)
    if not isinstance(factor, Fraction) or not 0 <= factor <= 1:
        raise ValueError("common drain factor must be an exact fraction in [0,1]")
    background = _background(boundary)
    checks = []
    for target in targets:
        terms = _terms(background, target)
        if boundary.limitations or boundary.discharge.value == 0 or isinstance(terms, str):
            reason = "; ".join(boundary.limitations) or (
                terms if isinstance(terms, str) else "zero discharge: concentration undefined"
            )
            checks.append(CandidateCheck(target.identifier, None, CheckOutcome.INDETERMINATE, reason))
            continue
        assert not isinstance(target, UnresolvedTarget)
        load, _, limit = terms
        value = (load + factor * _controlled(boundary, target)) / boundary.discharge.value
        accepted = _linear(target.identifier, Fraction(0), limit - value, target.operator).accepts(Fraction(0))
        checks.append(CandidateCheck(target.identifier, value, CheckOutcome.PASS if accepted else CheckOutcome.FAIL))
    return tuple(checks)
