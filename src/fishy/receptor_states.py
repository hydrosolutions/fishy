"""assess_receptor : ReceptorTargets × ReceptorStates → JointTargetAssessment (pure).

Supported state imports retain compartment, time statistic and scientific permission.
No receptor solver, target selection, quality activation or legal verdict is inferred.
"""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    Completeness,
    EvidenceFindings,
    EvidenceScope,
    _text,
    _texts,
    permitted_use,
    warmup_restrictions,
)
from fishy.flows import Presence
from fishy.quality import ChemicalIdentity, Comparison, ProfileStatus, compare_bounds
from fishy.quantities import Number, finite_number
from fishy.spatial import Location
from fishy.time import Interval


class ReceptorVariable(StrEnum):
    STORAGE = "storage"
    LEVEL = "level"
    WET_AREA = "wet_area"
    GROUNDWATER_HEAD = "groundwater_head"
    SALINITY = "salinity"


class Compartment(StrEnum):
    RESIDENT_WATER = "resident_water"
    ROOT_ZONE = "root_zone"
    GROUNDWATER = "groundwater"
    INCOMING_WATER = "incoming_water"


class StateStatistic(StrEnum):
    INTERVAL_END = "interval_end"
    INTERVAL_MEAN = "interval_mean"
    WHOLE_INTERVAL = "whole_interval"


@dataclass(frozen=True)
class ReceptorDomain:
    variable: ReceptorVariable
    compartment: Compartment
    basis: str
    chemical: ChemicalIdentity | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.variable, ReceptorVariable) or not isinstance(self.compartment, Compartment):
            raise TypeError("explicit receptor variable and compartment required")
        _text(self.basis, "datum/bed reference or representative chemical basis")
        if self.variable is ReceptorVariable.SALINITY:
            if not isinstance(self.chemical, ChemicalIdentity):
                raise TypeError("salinity requires chemical identity")
        elif self.chemical is not None:
            raise ValueError("chemical identity belongs only to salinity")

    @property
    def unit(self) -> str:
        return {
            ReceptorVariable.STORAGE: "m3",
            ReceptorVariable.LEVEL: "m",
            ReceptorVariable.WET_AREA: "m2",
            ReceptorVariable.GROUNDWATER_HEAD: "m",
            ReceptorVariable.SALINITY: "kg/m3",
        }[self.variable]


@dataclass(frozen=True, init=False)
class ReceptorValue:
    domain: ReceptorDomain
    value: Fraction

    def __init__(self, domain: ReceptorDomain, value: Number, unit: str) -> None:
        if not isinstance(domain, ReceptorDomain) or unit != domain.unit:
            raise ValueError("state requires matching declared domain/unit; no conversion inferred")
        amount = finite_number(value)
        if domain.variable not in (ReceptorVariable.LEVEL, ReceptorVariable.GROUNDWATER_HEAD) and amount < 0:
            raise ValueError("storage, area and concentration cannot be negative")
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "value", amount)


@dataclass(frozen=True)
class ReceptorBounds:
    lower: ReceptorValue
    upper: ReceptorValue
    meaning: str
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.lower, ReceptorValue) or not isinstance(self.upper, ReceptorValue):
            raise TypeError("bounds require receptor values")
        if self.lower.domain != self.upper.domain or self.lower.value > self.upper.value:
            raise ValueError("bounds require ordered values on the same domain")
        _text(self.meaning, "bounds meaning")
        _text(self.source, "bounds source")


@dataclass(frozen=True)
class ReceptorContext:
    location: Location
    candidate: str
    scenario: str
    reference_member: str | None
    period: Interval

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location) or not isinstance(self.period, Interval):
            raise TypeError("receptor context requires location and exact period")
        _text(self.candidate, "candidate")
        _text(self.scenario, "scenario")
        if self.reference_member is not None:
            _text(self.reference_member, "reference_member")

    def evidence_scope(self, product: str, period: Interval) -> EvidenceScope:
        return EvidenceScope(
            product, self.location.reach.identifier, self.reference_member, period, "receptor assessment"
        )


def _evidence_identity(evidence: EvidenceFindings, context: ReceptorContext) -> None:
    if not isinstance(evidence, EvidenceFindings):
        raise TypeError("attributable EvidenceFindings required")
    if (evidence.provenance.scenario, evidence.provenance.reference_member) != (
        context.scenario,
        context.reference_member,
    ):
        raise ValueError("incompatible evidence scenario/reference member")


@dataclass(frozen=True)
class ReceptorTarget:
    identifier: str
    limit: ReceptorValue
    operator: Comparison
    statistic: StateStatistic
    season: str
    resolution: str
    ecological_purpose: str
    evidence: EvidenceFindings

    def __post_init__(self) -> None:
        for name in ("identifier", "season", "resolution", "ecological_purpose"):
            _text(getattr(self, name), name)
        if not isinstance(self.limit, ReceptorValue) or not isinstance(self.operator, Comparison):
            raise TypeError("target requires typed limit and comparison")
        if not isinstance(self.statistic, StateStatistic) or not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("target requires temporal statistic and evidence")


@dataclass(frozen=True)
class ReceptorProfile:
    identifier: str
    version: str
    context: ReceptorContext
    intervals: tuple[Interval, ...]
    targets: tuple[ReceptorTarget, ...]
    required_quantity: tuple[str, ...]
    required_salinity: tuple[str, ...]
    status: ProfileStatus

    def __post_init__(self) -> None:
        _text(self.identifier, "profile")
        _text(self.version, "version")
        if not isinstance(self.context, ReceptorContext) or not isinstance(self.status, ProfileStatus):
            raise TypeError("profile requires context and application status")
        for ids in (self.required_quantity, self.required_salinity):
            _texts(ids, "required targets")
        required = self.required_quantity + self.required_salinity
        if len(set(required)) != len(required):
            raise ValueError("duplicate required targets")
        if not isinstance(self.targets, tuple) or any(not isinstance(t, ReceptorTarget) for t in self.targets):
            raise TypeError("immutable target tuple required")
        ids = [t.identifier for t in self.targets]
        if len(set(ids)) != len(ids) or set(ids) - set(required):
            raise ValueError("duplicate or undeclared target")
        _intervals(self.intervals, self.context.period)
        for target in self.targets:
            _evidence_identity(target.evidence, self.context)
            if (target.limit.domain.variable is ReceptorVariable.SALINITY) != (
                target.identifier in self.required_salinity
            ):
                raise ValueError("target assigned to incompatible quantity/salinity family")


def _intervals(intervals: tuple[Interval, ...], period: Interval) -> None:
    if not isinstance(intervals, tuple) or not intervals or any(not isinstance(i, Interval) for i in intervals):
        raise ValueError("nonempty immutable interval axis required")
    for index, interval in enumerate(intervals):
        if interval.start < period.start or interval.end > period.end:
            raise ValueError("interval outside assessment period")
        if index and intervals[index - 1].end > interval.start:
            raise ValueError("overlapping or unordered intervals")


@dataclass(frozen=True)
class ReceptorState:
    context: ReceptorContext
    interval: Interval
    domain: ReceptorDomain
    statistic: StateStatistic
    bounds: ReceptorBounds | None
    presence: Presence
    evidence: EvidenceFindings
    reasons: tuple[str, ...] = ()
    physical_sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.context, ReceptorContext) or not isinstance(self.domain, ReceptorDomain):
            raise TypeError("state requires context and domain")
        _intervals((self.interval,), self.context.period)
        if not isinstance(self.statistic, StateStatistic) or not isinstance(self.presence, Presence):
            raise TypeError("explicit time statistic and presence required")
        _evidence_identity(self.evidence, self.context)
        _texts(self.reasons, "reasons")
        _texts(self.physical_sources, "physical_sources")
        if self.bounds is not None and (
            not isinstance(self.bounds, ReceptorBounds) or self.bounds.lower.domain != self.domain
        ):
            raise ValueError("state bounds have incompatible domain")
        if self.presence is Presence.PRESENT and self.bounds is None:
            raise ValueError("present state requires bounds")
        if self.presence not in (Presence.PRESENT, Presence.UNSUPPORTED) and self.bounds is not None:
            raise ValueError("missing/outside/dry state cannot carry numerical bounds")
        if self.presence is not Presence.PRESENT and not self.reasons:
            raise ValueError("unavailable state requires reason")


@dataclass(frozen=True)
class ReceptorTest:
    target: ReceptorTarget | None
    interval: Interval
    state: ReceptorState | None
    numerical: Check
    supported: Check


@dataclass(frozen=True)
class ReceptorAssessment:
    profile: ReceptorProfile
    states: tuple[ReceptorState, ...]
    tests: tuple[ReceptorTest, ...]
    numerical: CheckSummary
    summary: CheckSummary

    def interval_summary(self, interval: Interval) -> CheckSummary:
        if interval not in self.profile.intervals:
            raise ValueError("undeclared interval")
        return CheckSummary(tuple(t.supported for t in self.tests if t.interval == interval))


def assess_receptor(profile: ReceptorProfile, states: tuple[ReceptorState, ...]) -> ReceptorAssessment:
    """Assess every named target/slot; no omitted family can yield a vacuous pass."""
    if not isinstance(profile, ReceptorProfile):
        raise TypeError("ReceptorProfile required")
    if not isinstance(states, tuple) or any(not isinstance(s, ReceptorState) for s in states):
        raise TypeError("immutable receptor states required")
    keys = [(s.interval, s.domain, s.statistic) for s in states]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate state domain/time carrier")
    for state in states:
        if state.context != profile.context or state.interval not in profile.intervals:
            raise ValueError("incompatible candidate/scenario/location/time")
    targets = {t.identifier: t for t in profile.targets}
    required = profile.required_quantity + profile.required_salinity
    required += () if profile.required_quantity else ("missing_quantity_targets",)
    required += () if profile.required_salinity else ("missing_salinity_targets",)
    tests = []
    for index, interval in enumerate(profile.intervals):
        for identifier in required:
            target = targets.get(identifier)
            state = None
            reason = "required target missing"
            numerical = CheckFinding.UNKNOWN
            supported = CheckFinding.UNKNOWN
            if target is not None:
                state = next(
                    (
                        s
                        for s in states
                        if s.interval == interval
                        and s.domain == target.limit.domain
                        and s.statistic == target.statistic
                    ),
                    None,
                )
                reason = "state missing for exact compartment, domain and temporal statistic"
                if state is not None:
                    reason = "; ".join(state.reasons) or "state unsupported for requested use"
                    if state.bounds is not None:
                        numerical = compare_bounds(
                            state.bounds.lower.value, state.bounds.upper.value, target.limit.value, target.operator
                        )
                    permissions = (
                        permitted_use(
                            target.evidence, profile.context.evidence_scope(target.identifier, profile.context.period)
                        ),
                        permitted_use(
                            state.evidence, profile.context.evidence_scope(profile.context.candidate, interval)
                        ),
                    )
                    restrictions = warmup_restrictions(state.evidence.provenance, interval)
                    if (
                        state.presence is Presence.PRESENT
                        and not restrictions
                        and all(p.finding is CheckFinding.PASS for p in permissions)
                    ):
                        supported = numerical
                        reason = "configured target comparison on supported declared domain"
                    else:
                        reason = "; ".join((*restrictions, *(r for p in permissions for r in p.reasons), reason))
            check_id = f"{index}:{identifier}"
            tests.append(
                ReceptorTest(
                    target,
                    interval,
                    state,
                    Check(check_id, numerical, (reason,)),
                    Check(check_id, supported, (reason,)),
                )
            )
    tests_tuple = tuple(tests)
    return ReceptorAssessment(
        profile,
        states,
        tests_tuple,
        CheckSummary(tuple(t.numerical for t in tests_tuple)),
        CheckSummary(tuple(t.supported for t in tests_tuple)),
    )


class DurationOperator(StrEnum):
    CUMULATIVE = "cumulative"
    CONSECUTIVE = "consecutive"


class BoundaryHistory(StrEnum):
    WITHIN_PERIOD = "within_period"
    REQUIRED_MISSING = "required_missing"


@dataclass(frozen=True, init=False)
class Duration:
    seconds: Fraction

    def __init__(self, value: Number, unit: str = "s") -> None:
        if unit not in ("s", "h", "day"):
            raise ValueError("duration requires s, h or day")
        seconds = finite_number(value) * {"s": 1, "h": 3600, "day": 86400}[unit]
        if seconds < 0:
            raise ValueError("duration cannot be negative")
        object.__setattr__(self, "seconds", seconds)


@dataclass(frozen=True)
class DurationCriterion:
    identifier: str
    minimum: Duration
    comparison: Comparison
    operator: DurationOperator
    boundary_history: BoundaryHistory
    evidence: EvidenceFindings

    def __post_init__(self) -> None:
        _text(self.identifier, "duration criterion")
        if not isinstance(self.minimum, Duration) or self.comparison not in (Comparison.GE, Comparison.GT):
            raise ValueError("minimum-duration criterion requires duration and strict/inclusive lower comparison")
        if not isinstance(self.operator, DurationOperator) or not isinstance(self.boundary_history, BoundaryHistory):
            raise TypeError("declared duration operator and boundary-history meaning required")
        if not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("duration evidence required")


@dataclass(frozen=True)
class DurationAssessment:
    assessment: ReceptorAssessment
    criterion: DurationCriterion
    lower: Duration
    upper: Duration
    raw_coverage: Completeness
    check: Check


def assess_joint_duration(assessment: ReceptorAssessment, criterion: DurationCriterion) -> DurationAssessment:
    """Bound the intersection duration; point/mean states never establish whole intervals."""
    profile = assessment.profile
    _evidence_identity(criterion.evidence, profile.context)
    segments: list[tuple[Interval, CheckFinding]] = []
    raw_findings: list[CheckFinding] = []
    cursor = profile.context.period.start
    for interval in profile.intervals:
        if cursor < interval.start:
            segments.append((Interval(cursor, interval.start), CheckFinding.UNKNOWN))
        checks = []
        for test in assessment.tests:
            if test.interval != interval:
                continue
            finding = test.supported.finding
            if test.target is None or test.target.statistic is not StateStatistic.WHOLE_INTERVAL:
                finding = CheckFinding.UNKNOWN
            checks.append(Check(test.supported.check_id, finding))
            raw_findings.append(finding)
        segments.append((interval, CheckSummary(tuple(checks)).finding))
        cursor = interval.end
    if cursor < profile.context.period.end:
        segments.append((Interval(cursor, profile.context.period.end), CheckFinding.UNKNOWN))
    lower = upper = run_lower = run_upper = Fraction()
    for interval, finding in segments:
        lo = interval.seconds if finding is CheckFinding.PASS else Fraction()
        hi = interval.seconds if finding is not CheckFinding.FAIL else Fraction()
        if criterion.operator is DurationOperator.CUMULATIVE:
            lower += lo
            upper += hi
        else:
            run_lower = run_lower + lo if lo else Fraction()
            run_upper = run_upper + hi if hi else Fraction()
            lower, upper = max(lower, run_lower), max(upper, run_upper)
    raw = (
        Completeness.INCOMPLETE
        if any(f is CheckFinding.UNKNOWN for f in (*raw_findings, *(f for _, f in segments)))
        else Completeness.COMPLETE
    )
    finding = compare_bounds(lower, upper, criterion.minimum.seconds, criterion.comparison)
    reasons = ("duration bounds resolve only the configured duration test; raw state coverage is separate",)
    permission = permitted_use(
        criterion.evidence, profile.context.evidence_scope(criterion.identifier, profile.context.period)
    )
    if permission.finding is not CheckFinding.PASS or criterion.boundary_history is BoundaryHistory.REQUIRED_MISSING:
        finding = CheckFinding.UNKNOWN
        reasons += permission.reasons + ("duration use or required boundary history unresolved",)
    return DurationAssessment(
        assessment, criterion, Duration(lower), Duration(upper), raw, Check(criterion.identifier, finding, reasons)
    )
