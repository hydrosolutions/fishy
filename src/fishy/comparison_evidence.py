"""comparison_evidence : IssuedThreshold × Delivery × EvidenceChecks → ScopedAdmission.

Evidence is supplied, not authenticated by numerical success. Scenario checks can
be explicitly supported without conferring authority or responsibility.
"""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from fishy.duties import Delivery, Floor, Obligation
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    Computability,
    OfficialAdmissibility,
    ProductionMethod,
    aggregate_checks,
)
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, interval_use
from fishy.quantities import Number, finite_number
from fishy.spatial import CompliancePoint


class NumericalFinding(StrEnum):
    BELOW = "below"
    NOT_BELOW = "not_below"
    INDETERMINATE = "indeterminate"
    UNAVAILABLE = "unavailable"


class AttributionFinding(StrEnum):
    TO_TESTED_CONDUCT = "attributed_to_tested_conduct"
    OTHER_CAUSE = "other_cause"
    INDETERMINATE = "indeterminate"
    UNASSESSED = "unassessed"


@dataclass(frozen=True)
class Attribution:
    finding: AttributionFinding
    source: str
    operator_control: Check
    conduct: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.finding, AttributionFinding) or not isinstance(self.operator_control, Check):
            raise TypeError("attribution requires typed finding and control evidence")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("attribution requires source, including unassessed reason")
        if (
            self.finding is AttributionFinding.TO_TESTED_CONDUCT
            and self.operator_control.finding is not CheckFinding.PASS
        ):
            raise ValueError("attribution to conduct requires supported operator control")
        if self.finding is AttributionFinding.TO_TESTED_CONDUCT and (
            not isinstance(self.conduct, str) or not self.conduct.strip()
        ):
            raise ValueError("attribution must identify the tested conduct")


@dataclass(frozen=True)
class ButForFlow:
    sample: FlowSample
    version: str
    conduct: str

    def __post_init__(self) -> None:
        if not isinstance(self.sample, FlowSample):
            raise TypeError("but-for flow requires FlowSample")
        if any(not isinstance(s, str) or not s.strip() for s in (self.version, self.conduct)):
            raise ValueError("but-for flow requires version and tested conduct")


@dataclass(frozen=True, init=False)
class MarginBounds:
    """Signed discharge margin bounds, in m3/s; not nonnegative Flow."""

    lower: Fraction
    upper: Fraction

    def __init__(self, lower: Number, upper: Number) -> None:
        lo, hi = finite_number(lower), finite_number(upper)
        if lo > hi:
            raise ValueError("margin bounds must be ordered")
        object.__setattr__(self, "lower", lo)
        object.__setattr__(self, "upper", hi)

    @property
    def finding(self) -> NumericalFinding:
        if self.upper < 0:
            return NumericalFinding.BELOW
        if self.lower >= 0:
            return NumericalFinding.NOT_BELOW
        return NumericalFinding.INDETERMINATE


@dataclass(frozen=True)
class ComparisonEvidence:
    """Checks bind exact versioned operands, not merely a reach or method name.

    Required admission limbs: coverage, infill, authentication, reconciliation,
    uncertainty. Floor assessment also requires abstraction_metering and
    downstream_of_conduct. A PASS reason names the supplied support/assumption.
    Bounds meaning/source/dependence live on the samples; uncertainty's reason
    supplies accepted coverage, not an inferred joint confidence level.
    """

    threshold: Floor | Obligation
    actual: Delivery | None
    but_for: ButForFlow | None
    checks: tuple[Check, ...]
    point: CompliancePoint | None
    official_admissibility: OfficialAdmissibility
    attribution: Attribution
    source: str

    def __post_init__(self) -> None:
        if type(self.threshold) not in (Floor, Obligation):
            raise TypeError("comparison threshold requires Floor or Obligation")
        if self.actual is not None and type(self.actual) is not Delivery:
            raise TypeError("actual requires Delivery")
        if self.but_for is not None and not isinstance(self.but_for, ButForFlow):
            raise TypeError("counterfactual requires ButForFlow")
        if not isinstance(self.official_admissibility, OfficialAdmissibility) or not isinstance(
            self.attribution, Attribution
        ):
            raise TypeError("comparison requires typed admission and attribution")
        CheckSummary(self.checks)
        if any(not check.reasons for check in self.checks):
            raise ValueError("every evidence check requires its support or missing/rejected reason")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("comparison evidence requires a source/version")
        if self.point is not None:
            if not isinstance(self.point, CompliancePoint):
                raise TypeError("point requires designated CompliancePoint, not a gauge")
            if self.point.section != self.threshold.sample.location.section:
                raise ValueError("designated point must match tested section")
        for role in (self.actual, self.but_for):
            if role is not None:
                sample = role.sample
                target = self.threshold.sample
                if sample.location != target.location or sample.interval != target.interval:
                    raise ValueError("comparison operands require identical location and interval")
                if sample.provenance.scenario != target.provenance.scenario:
                    raise ValueError("comparison operands cannot mix scenarios")
        if (
            self.but_for is not None
            and self.attribution.finding is AttributionFinding.TO_TESTED_CONDUCT
            and self.attribution.conduct != self.but_for.conduct
        ):
            raise ValueError("attribution must concern the same tested conduct as the but-for flow")
        _ = self.admission  # Reject undeclared evidence limbs at the boundary.
        if type(self.threshold) is Obligation and self.but_for is not None:
            raise ValueError("delivery test does not use but-for flow")

    @property
    def admission(self) -> CheckSummary:
        names = ("coverage", "infill", "authentication", "reconciliation", "uncertainty")
        if type(self.threshold) is Floor:
            names += ("abstraction_metering", "downstream_of_conduct")
        return aggregate_checks(names, self.checks)


def sample_computability(sample: FlowSample) -> Computability:
    """Whole-interval numeric availability, not scientific or official acceptance."""
    if (
        sample.presence is Presence.PRESENT
        and sample.coverage is Coverage.COMPLETE
        and sample.value is not None
        and interval_use(sample) is IntervalUse.ELIGIBLE
    ):
        return Computability.COMPUTABLE
    return Computability.NOT_COMPUTABLE


def official_comparison(evidence: ComparisonEvidence, numerical: NumericalFinding) -> Check:
    """Eligibility for an official numeric finding, never a legal liability decision."""
    reasons = []
    if evidence.admission.finding is not CheckFinding.PASS:
        reasons.append("required evidence missing or rejected")
    if evidence.point is None:
        reasons.append("control point not designated; technical comparison only")
    if evidence.official_admissibility is not OfficialAdmissibility.ADMISSIBLE:
        reasons.append("official evidence admission not established")
    if evidence.actual is None or evidence.actual.sample.provenance.production_method is not ProductionMethod.OBSERVED:
        reasons.append("scenario/imported prediction is not observed compliance")
    if evidence.threshold.sample.provenance.production_method in (
        ProductionMethod.ILLUSTRATIVE,
        ProductionMethod.SIMULATED,
    ):
        reasons.append("hypothetical threshold does not establish an official duty")
    if numerical in (NumericalFinding.UNAVAILABLE, NumericalFinding.INDETERMINATE):
        reasons.append("no decisive supported numeric finding")
    return Check("official_numeric_finding", CheckFinding.UNKNOWN if reasons else CheckFinding.PASS, tuple(reasons))


def responsibility(evidence: ComparisonEvidence, numerical: NumericalFinding) -> Check:
    """Retain supplied causality separately; no automatic legal verdict."""
    official = official_comparison(evidence, numerical)
    if numerical is not NumericalFinding.BELOW:
        return Check("responsibility", CheckFinding.UNKNOWN, ("no established numerical shortfall",))
    if official.finding is not CheckFinding.PASS:
        return Check("responsibility", CheckFinding.UNKNOWN, official.reasons)
    if evidence.attribution.finding is not AttributionFinding.TO_TESTED_CONDUCT:
        return Check(
            "responsibility", CheckFinding.UNKNOWN, (evidence.attribution.finding.value, evidence.attribution.source)
        )
    return Check(
        "responsibility",
        CheckFinding.PASS,
        (
            "supplied attribution and official prerequisites supported; not a legal liability decision",
            evidence.attribution.source,
        ),
    )
