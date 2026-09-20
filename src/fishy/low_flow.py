"""pooled_q347 : DailyFlowSamples × Q347Conventions → Q347Estimate (pure).

Scientific acceptance and conditional verification consume scoped supplied findings.
"""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    Provenance,
    ScientificAdequacy,
    permitted_use,
)
from fishy.flows import FlowSample, daily_discharge
from fishy.quantities import Flow, FlowBounds
from fishy.spatial import Location
from fishy.time import Interval

ACT = "GSchG 2025-08-01 Arts. 4(h–i), 59"
GUIDE = "FOEN Wegleitung 2000 chapter 7, printed pp. 82–86"


class DailyBasis(StrEnum):
    DAILY_OBSERVATIONS = "daily observations"
    RECONSTRUCTED_DAILY = "supported reconstructed daily series"
    COARSE_REPETITION = "coarse means repeated daily"


class Q347Method(StrEnum):
    POOLED_DAILY = "pooled daily flow-duration distribution"
    ARTICLE_59 = "supplied Art. 59 estimate"


class EstimateStatus(StrEnum):
    PRELIMINARY = "preliminary"
    FINAL = "submitted for final use"


class VerificationRoute(StrEnum):
    REQUIRED = "little or no uplift: measurement verification required"
    JUSTIFIED_EXCEPTION = "justified exception to measurement verification"
    NOT_APPLICABLE = "conditional verification guidance not applicable"
    UNRESOLVED = "guidance applicability unresolved"


@dataclass(frozen=True)
class Q347Conventions:
    """Explicit supported convention; no silent dropping, filling or annual averaging."""

    record_selection: str
    daily_basis: DailyBasis
    calendar: str = "Gregorian UTC; retain leap days"
    interpolation: str = "linear descending rank; rank = 347 * complete calendar years, one-based"
    missing_data: str = "reject gaps and unsupported or partial days"

    def __post_init__(self) -> None:
        if not self.record_selection.strip():
            raise ValueError("record selection rationale required")
        if not isinstance(self.daily_basis, DailyBasis):
            raise TypeError("daily basis requires DailyBasis")
        if (self.calendar, self.interpolation, self.missing_data) != (
            "Gregorian UTC; retain leap days",
            "linear descending rank; rank = 347 * complete calendar years, one-based",
            "reject gaps and unsupported or partial days",
        ):
            raise ValueError("unsupported Q347 numerical convention")


@dataclass(frozen=True)
class Q347Estimate:
    value: Flow
    location: Location
    reference_period: Interval
    provenance: Provenance
    method: Q347Method
    method_description: str
    status: EstimateStatus
    uncertainty: FlowBounds | None
    conventions: Q347Conventions | None
    samples: tuple[FlowSample, ...] = ()
    source: str = ACT

    def __post_init__(self) -> None:
        for value, kind in (
            (self.value, Flow),
            (self.location, Location),
            (self.reference_period, Interval),
            (self.provenance, Provenance),
            (self.method, Q347Method),
            (self.status, EstimateStatus),
        ):
            if not isinstance(value, kind):
                raise TypeError("Q347 estimate requires typed quantities and attribution")
        if not self.method_description.strip() or self.source != ACT:
            raise ValueError("Q347 method and statutory source required")
        if self.uncertainty is not None:
            if not isinstance(self.uncertainty, FlowBounds):
                raise TypeError("uncertainty requires FlowBounds")
            if not self.uncertainty.lower.value <= self.value.value <= self.uncertainty.upper.value:
                raise ValueError("estimate outside uncertainty bounds")
        if not isinstance(self.samples, tuple):
            raise TypeError("samples must be immutable")
        if self.method is Q347Method.POOLED_DAILY and (not self.samples or self.conventions is None):
            raise ValueError("pooled Q347 must retain samples and conventions")

    @property
    def permanent_flow(self) -> CheckFinding:
        """Numerical Art. 4(i) only, not a permitting finding."""
        return CheckFinding.PASS if self.value.value > 0 else CheckFinding.FAIL


def pooled_q347(
    samples: tuple[FlowSample, ...],
    conventions: Q347Conventions,
    provenance: Provenance,
    status: EstimateStatus,
    uncertainty: FlowBounds | None = None,
) -> Q347Estimate:
    """Pool complete selected calendar years, retaining each day's original evidence.

    Short records remain numerical estimates, not automatically accepted ten-year evidence.
    Leap days increase the pooled population, not the 347-days-per-year exceedance rank.
    """
    if conventions.daily_basis is DailyBasis.COARSE_REPETITION:
        raise ValueError("repeated coarse means cannot establish daily low-flow evidence")
    daily_discharge(samples)  # Real shared support, identity, resolution and overlap checks.
    ordered = tuple(sorted(samples, key=lambda s: s.interval.start))
    first, last = ordered[0], ordered[-1]
    for a, b in zip(ordered, ordered[1:], strict=False):
        if a.interval.end != b.interval.start:
            raise ValueError("Q347 refuses missing days")
    start, end = first.interval.start, last.interval.end
    if (start.month, start.day, end.month, end.day) != (1, 1, 1, 1):
        raise ValueError("selected record must contain complete calendar years")
    for field in ("scenario", "reference_member", "reference_kind"):
        if getattr(provenance, field) != getattr(first.provenance, field):
            raise ValueError("estimate attribution differs from daily reference identity")
    values = sorted((s.value.value for s in ordered if s.value is not None), reverse=True)
    rank = Fraction(347 * (end.year - start.year))
    position = rank - 1
    lower = position.numerator // position.denominator
    fraction = position - lower
    value = values[lower] if not fraction else values[lower] + fraction * (values[lower + 1] - values[lower])
    return Q347Estimate(
        Flow(value),
        first.location,
        Interval(start, end),
        provenance,
        Q347Method.POOLED_DAILY,
        conventions.interpolation,
        status,
        uncertainty,
        conventions,
        ordered,
    )


def imported_q347(
    value: Flow,
    location: Location,
    reference_period: Interval,
    provenance: Provenance,
    method_description: str,
    status: EstimateStatus,
    uncertainty: FlowBounds | None = None,
) -> Q347Estimate:
    """Retain an Art. 59 observation/model estimate without inventing daily observations."""
    return Q347Estimate(
        value,
        location,
        reference_period,
        provenance,
        Q347Method.ARTICLE_59,
        method_description,
        status,
        uncertainty,
        None,
    )


@dataclass(frozen=True)
class Q347Review:
    findings: EvidenceFindings
    influences: Check
    representativeness: Check
    trend: Check
    verification_route: VerificationRoute
    verification: Check
    verification_period: Interval | None
    rationale: str
    guidance: str = GUIDE

    def __post_init__(self) -> None:
        if not isinstance(self.findings, EvidenceFindings):
            raise TypeError("scoped evidence findings required")
        for value in (self.influences, self.representativeness, self.trend, self.verification):
            if not isinstance(value, Check):
                raise TypeError("supplied findings require Check")
        if not isinstance(self.verification_route, VerificationRoute):
            raise TypeError("verification route requires VerificationRoute")
        if self.verification_period is not None and not isinstance(self.verification_period, Interval):
            raise TypeError("verification period requires Interval")
        if not self.rationale.strip() or self.guidance != GUIDE:
            raise ValueError("guidance version and applicable verification/exception rationale required")


def assess_q347(estimate: Q347Estimate, review: Q347Review, scope: EvidenceScope) -> CheckSummary:
    """Assess requested use, separately from numerical availability and official admission.

    Inputs are specialist decisions. No statistical trend or human-influence model is inferred.
    """
    expected = (estimate.location.reach.identifier, estimate.provenance.reference_member, estimate.reference_period)
    actual = (scope.reach, scope.member, scope.period)
    attribution = review.findings.provenance
    if (
        scope.product != "Q347"
        or actual != expected
        or any(
            getattr(attribution, f) != getattr(estimate.provenance, f)
            for f in ("scenario", "reference_member", "reference_kind")
        )
    ):
        return CheckSummary((Check("q347_scope", CheckFinding.UNKNOWN, ("Q347 evidence scope mismatch",)),))
    checks = [permitted_use(review.findings, scope)]
    for name, supplied in (
        ("influences", review.influences),
        ("representativeness", review.representativeness),
        ("trend", review.trend),
    ):
        checks.append(Check(name, supplied.finding, supplied.reasons))
    final = scope.intended_use == "final Q347 determination"
    if final:
        accepted = (
            estimate.status is EstimateStatus.FINAL
            and review.findings.scientific_adequacy is ScientificAdequacy.ACCEPTED
        )
        checks.append(
            Check(
                "final_acceptance",
                CheckFinding.PASS if accepted else CheckFinding.UNKNOWN,
                ("final status and scientific acceptance required; preliminary scenarios remain numerical",),
            )
        )
        route = review.verification_route
        finding = review.verification.finding
        if route is VerificationRoute.UNRESOLVED:
            finding = CheckFinding.UNKNOWN
        elif route is VerificationRoute.REQUIRED:
            period = review.verification_period
            # Three calendar years, not an unconditional record-length gate.
            enough = period is not None and period.end >= period.start.replace(
                year=period.start.year + 3,
                day=28 if period.start.month == 2 and period.start.day == 29 else period.start.day,
            )
            if not enough and finding is not CheckFinding.FAIL:
                finding = CheckFinding.UNKNOWN
        checks.append(Check("verification", finding, (review.guidance, review.rationale, *review.verification.reasons)))
    return CheckSummary(tuple(checks))
