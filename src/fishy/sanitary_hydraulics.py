"""sanitary_hydraulics : HydraulicScope × AttributedHydraulicEvidence → Check (pure).

A sanitary import boundary and a single supplied discrete-rate operator, not a
hydraulic solver. No numeric criterion is inferred from SanPiN 3907-85 §4.4.
"""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    Completeness,
    Computability,
    EvidenceFindings,
    NumericalValidity,
    permitted_use,
    warmup_restrictions,
)
from fishy.spatial import Location
from fishy.time import Interval


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("hydraulic identities and evidence must be nonempty text")


class HydraulicVariable(StrEnum):
    RELEASE_DISCHARGE = "release_discharge"
    STAGE = "stage"
    DEPTH = "depth"
    DIRECTIONAL_VELOCITY = "directional_local_velocity"
    SPEED = "speed_magnitude"

    @property
    def units(self) -> str:
        if self is HydraulicVariable.RELEASE_DISCHARGE:
            return "m3/s"
        if self in (HydraulicVariable.STAGE, HydraulicVariable.DEPTH):
            return "m"
        return "m/s"


class TemporalSupport(StrEnum):
    ENDPOINTS = "discrete_endpoints"
    INTERVAL_MEANS = "interval_means"
    DAILY_MEANS = "daily_means"
    WITHIN_DAY = "supported_within_day"


@dataclass(frozen=True)
class HydraulicScope:
    component: str
    location: Location
    domain: str
    candidate: str
    scenario: str
    variable: HydraulicVariable
    period: Interval
    reference: str
    temporal_support: TemporalSupport

    def __post_init__(self) -> None:
        for value in (self.component, self.domain, self.candidate, self.scenario, self.reference):
            _text(value)
        for value, kind in (
            (self.location, Location),
            (self.variable, HydraulicVariable),
            (self.period, Interval),
            (self.temporal_support, TemporalSupport),
        ):
            if not isinstance(value, kind):
                raise TypeError(f"scope requires {kind.__name__}")

    @property
    def units(self) -> str:
        return self.variable.units


class RelationDomain(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported_no_extrapolation"


@dataclass(frozen=True)
class HydraulicRelationEvidence:
    """Metadata for supplied relation-derived states; no relation is evaluated here."""

    identity: str
    geometry_version: str
    boundary_conditions: str
    supported_domain: str
    interpolation: str
    uncertainty: str
    intended_use_acceptance: str
    domain_state: RelationDomain

    def __post_init__(self) -> None:
        for value in (
            self.identity,
            self.geometry_version,
            self.boundary_conditions,
            self.supported_domain,
            self.interpolation,
            self.uncertainty,
            self.intended_use_acceptance,
        ):
            _text(value)
        if not isinstance(self.domain_state, RelationDomain):
            raise TypeError("relation domain state requires RelationDomain")


def _relation_reasons(relation: HydraulicRelationEvidence | None) -> tuple[str, ...]:
    if relation is not None and not isinstance(relation, HydraulicRelationEvidence):
        raise TypeError("relation requires HydraulicRelationEvidence")
    if relation is not None and relation.domain_state is RelationDomain.UNSUPPORTED:
        return ("outside supported relation domain; no extrapolation",)
    return ()


@dataclass(frozen=True)
class ImportedHydraulicFinding:
    """Specialist judgement, not a native calculation or generic pass flag.

    Reference names the stage datum, depth bed reference, velocity direction or
    explicit speed magnitude convention. Domain names the assessed spatial domain.
    """

    scope: HydraulicScope
    study: str
    criterion_source: str
    evidence: EvidenceFindings
    finding: CheckFinding
    reasons: tuple[str, ...]
    relation: HydraulicRelationEvidence | None = None

    def __post_init__(self) -> None:
        _attributed(self.scope, self.evidence)
        _relation_reasons(self.relation)
        _text(self.study)
        _text(self.criterion_source)
        if not isinstance(self.finding, CheckFinding):
            raise TypeError("finding requires CheckFinding")
        if not isinstance(self.reasons, tuple) or not self.reasons:
            raise ValueError("specialist finding needs immutable attributable reasons")
        for reason in self.reasons:
            _text(reason)

    @property
    def permission(self) -> Check:
        """Imported numeric findings do not establish scientific intended-use permission."""
        return permitted_use(self.evidence, self.evidence.scope)


def _attributed(scope: HydraulicScope, evidence: EvidenceFindings) -> None:
    if not isinstance(scope, HydraulicScope) or not isinstance(evidence, EvidenceFindings):
        raise TypeError("typed hydraulic scope and evidence required")
    if (
        evidence.scope.product != scope.candidate
        or evidence.scope.reach != scope.location.reach.identifier
        or evidence.scope.period != scope.period
        or evidence.scope.intended_use != scope.component
        or evidence.provenance.scenario != scope.scenario
    ):
        raise ValueError("evidence must identify the hydraulic candidate, reach, period, use and scenario")


def _unsupported(evidence: EvidenceFindings, scope: HydraulicScope) -> tuple[str, ...]:
    reasons = warmup_restrictions(evidence.provenance, scope.period)
    if (
        evidence.computability is not Computability.COMPUTABLE
        or evidence.numerical_validity is not NumericalValidity.VALID
    ):
        reasons += ("numeric evidence unsupported", *evidence.reasons)
    return reasons


def assess_imported_hydraulics(required: HydraulicScope, supplied: ImportedHydraulicFinding) -> Check:
    """Preserve imported identity; exact scope and supported intended use required."""
    if not isinstance(required, HydraulicScope) or not isinstance(supplied, ImportedHydraulicFinding):
        raise TypeError("typed hydraulic scope and specialist finding required")
    if required != supplied.scope:
        return Check(
            required.component,
            CheckFinding.UNKNOWN,
            ("hydraulic scope mismatch; no variable or temporal substitution",),
        )
    unsupported = _unsupported(supplied.evidence, supplied.scope) + _relation_reasons(supplied.relation)
    if unsupported:
        return Check(required.component, CheckFinding.UNKNOWN, unsupported)
    return Check(
        required.component,
        supplied.finding,
        (f"imported study: {supplied.study}; criterion: {supplied.criterion_source}", *supplied.reasons),
    )


class BoundState(StrEnum):
    SUPPLIED = "supplied"
    INTENTIONALLY_ABSENT = "intentionally_absent"
    MISSING = "missing_required"


class Comparison(StrEnum):
    INCLUSIVE = "inclusive"
    STRICT = "strict"


@dataclass(frozen=True)
class RateBound:
    """Nonnegative magnitude in the criterion's explicit variable-units per hour."""

    state: BoundState
    magnitude: Fraction | None
    comparison: Comparison = Comparison.INCLUSIVE

    def __post_init__(self) -> None:
        if not isinstance(self.state, BoundState) or not isinstance(self.comparison, Comparison):
            raise TypeError("typed bound state and comparison required")
        if self.state is BoundState.SUPPLIED:
            if not isinstance(self.magnitude, Fraction) or self.magnitude < 0:
                raise ValueError("rate magnitude requires a finite nonnegative Fraction")
        elif self.magnitude is not None:
            raise ValueError("absent/missing bound cannot carry a magnitude")


@dataclass(frozen=True)
class StateBounds:
    """Supported closed bounds in the scoped variable units, not confidence limits."""

    lower: Fraction
    upper: Fraction

    def __post_init__(self) -> None:
        if not isinstance(self.lower, Fraction) or not isinstance(self.upper, Fraction):
            raise TypeError("finite exact Fraction bounds required")
        if self.lower > self.upper:
            raise ValueError("reversed state bounds")


class TransitionCoverage(StrEnum):
    ADJACENT = "no_expected_sample_missing"
    GAP = "expected_sample_gap"
    MISSING_PREDECESSOR = "missing_predecessor"


class CriterionApplicability(StrEnum):
    APPLICABLE = "applicable_to_whole_transition"
    UNRESOLVED = "season_boundary_unresolved"


class CriterionStatus(StrEnum):
    SUPPLIED = "supplied"
    HYPOTHETICAL = "hypothetical"


@dataclass(frozen=True)
class RateCriterion:
    scope: HydraulicScope
    source: str
    status: CriterionStatus
    rise: RateBound
    fall: RateBound
    applicability: CriterionApplicability

    def __post_init__(self) -> None:
        _text(self.source)
        for value, kind in (
            (self.scope, HydraulicScope),
            (self.status, CriterionStatus),
            (self.rise, RateBound),
            (self.fall, RateBound),
            (self.applicability, CriterionApplicability),
        ):
            if not isinstance(value, kind):
                raise TypeError(f"criterion requires {kind.__name__}")

    @property
    def units(self) -> str:
        return f"({self.scope.units})/hour"


@dataclass(frozen=True)
class HydraulicTransition:
    """The period bounds are the actual timestamps, never an assumed time step."""

    scope: HydraulicScope
    previous: StateBounds | None
    current: StateBounds | None
    coverage: TransitionCoverage
    evidence: EvidenceFindings
    joint_rate_bounds: StateBounds | None = None
    joint_evidence: str | None = None
    relation: HydraulicRelationEvidence | None = None

    def __post_init__(self) -> None:
        _attributed(self.scope, self.evidence)
        _relation_reasons(self.relation)
        if not isinstance(self.coverage, TransitionCoverage):
            raise TypeError("explicit expected-sample coverage required")
        for state in (self.previous, self.current, self.joint_rate_bounds):
            if state is not None and not isinstance(state, StateBounds):
                raise TypeError("typed state bounds required")
        if self.scope.variable in (
            HydraulicVariable.DEPTH,
            HydraulicVariable.SPEED,
            HydraulicVariable.RELEASE_DISCHARGE,
        ) and any(s is not None and s.lower < 0 for s in (self.previous, self.current)):
            raise ValueError("depth, speed and release discharge cannot be negative")
        if (self.joint_rate_bounds is None) != (self.joint_evidence is None):
            raise ValueError("joint bounds require their supporting joint evidence")
        if self.joint_evidence is not None:
            _text(self.joint_evidence)


@dataclass(frozen=True)
class RateAssessment:
    criterion: RateCriterion
    transition: HydraulicTransition
    check: Check
    change_bounds: StateBounds | None
    elapsed_hours: Fraction
    rate_bounds: StateBounds | None
    directional_checks: CheckSummary = CheckSummary(())

    @property
    def completeness(self) -> Completeness:
        """Missing bounds and indeterminate directions retain incomplete coverage."""
        return self.directional_checks.completeness

    @property
    def permission(self) -> Check:
        """Scientific intended-use permission remains separate from numerical findings."""
        return permitted_use(self.transition.evidence, self.transition.evidence.scope)


def assess_sanitary_rate(criterion: RateCriterion, transition: HydraulicTransition) -> RateAssessment:
    """Evaluate only the declared discrete statistic, never unseen peak rates."""
    if not isinstance(criterion, RateCriterion) or not isinstance(transition, HydraulicTransition):
        raise TypeError("typed criterion and transition required")
    hours = transition.scope.period.seconds / 3600
    reasons = []
    if criterion.scope != transition.scope:
        reasons.append("hydraulic scope mismatch")
    if criterion.scope.temporal_support is TemporalSupport.WITHIN_DAY:
        reasons.append("endpoint differences cannot certify within-day maxima; import a supported specialist finding")
    if transition.coverage is not TransitionCoverage.ADJACENT:
        reasons.append(transition.coverage.value)
    if transition.previous is None or transition.current is None:
        reasons.append("missing state or predecessor; no gap bridging")
    if criterion.applicability is CriterionApplicability.UNRESOLVED:
        reasons.append("season-boundary criterion unresolved")
    if all(bound.state is BoundState.INTENTIONALLY_ABSENT for bound in (criterion.rise, criterion.fall)):
        reasons.append("no directional criterion supplied; empty bounds cannot establish satisfaction")
    reasons.extend(_unsupported(transition.evidence, transition.scope))
    reasons.extend(_relation_reasons(transition.relation))
    if reasons:
        return RateAssessment(
            criterion,
            transition,
            Check(criterion.scope.component, CheckFinding.UNKNOWN, tuple(reasons)),
            None,
            hours,
            None,
        )
    assert transition.previous is not None and transition.current is not None
    change = StateBounds(
        transition.current.lower - transition.previous.upper, transition.current.upper - transition.previous.lower
    )
    rates = StateBounds(change.lower / hours, change.upper / hours)
    if transition.joint_rate_bounds is not None:
        joint = transition.joint_rate_bounds
        if joint.lower < rates.lower or joint.upper > rates.upper:
            raise ValueError("joint rate evidence must tighten conservative bounds")
        rates = joint
    directions = []
    for name, bound, low, high in (
        ("rise", criterion.rise, rates.lower, rates.upper),
        ("fall", criterion.fall, -rates.upper, -rates.lower),
    ):
        if bound.state is BoundState.INTENTIONALLY_ABSENT:
            continue
        if bound.state is BoundState.MISSING:
            directions.append(Check(name, CheckFinding.UNKNOWN, ("required directional bound missing",)))
            continue
        assert bound.magnitude is not None
        if bound.comparison is Comparison.INCLUSIVE:
            contained = high <= bound.magnitude
            disjoint = low > bound.magnitude
        else:
            contained = high < bound.magnitude
            disjoint = low >= bound.magnitude
        finding = CheckFinding.PASS if contained else CheckFinding.FAIL if disjoint else CheckFinding.UNKNOWN
        directions.append(Check(name, finding, (f"{bound.comparison.value} supplied directional bound",)))
    # Joint strict zero bounds can exclude every rate even when each marginal
    # direction overlaps the uncertainty interval.
    if criterion.rise.magnitude == criterion.fall.magnitude == 0 and Comparison.STRICT in (
        criterion.rise.comparison,
        criterion.fall.comparison,
    ):
        directions.append(Check("joint_bounds", CheckFinding.FAIL, ("empty admissible rate range",)))
    directional_checks = CheckSummary(tuple(directions))
    finding = directional_checks.finding
    notes = (
        f"{criterion.status.value} criterion: {criterion.source}",
        "discrete transition only; not instantaneous maxima or legal compliance",
        "interval overlap is indeterminate; bounds are not probabilistic confidence intervals",
    )
    notes += tuple(reason for check in directions if check.finding is CheckFinding.UNKNOWN for reason in check.reasons)
    return RateAssessment(
        criterion,
        transition,
        Check(criterion.scope.component, finding, notes),
        change,
        hours,
        rates,
        directional_checks,
    )


def rate_check(required: HydraulicScope, assessment: RateAssessment) -> Check:
    """Transfer complete native findings only; refuse loss of directional coverage.

    For incomplete evidence use the RateAssessment returned by
    assess_sanitary_rate and its directional_checks summary as the lossless result.
    """
    if required != assessment.criterion.scope:
        return Check(required.component, CheckFinding.UNKNOWN, ("rate assessment scope mismatch",))
    if assessment.completeness is Completeness.INCOMPLETE:
        raise ValueError(
            "incomplete rate assessment requires lossless inspection of RateAssessment.directional_checks; "
            "a scalar Check cannot preserve directional coverage"
        )
    return assessment.check
