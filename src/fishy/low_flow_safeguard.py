"""assess_low_flow : CandidateFlow × DurationThreshold × AssessmentContext → LowFlowAssessment (pure).

Point comparisons, supported uncertainty and scientific permission remain
separate. This operation neither issues a family nor repairs a daily schedule.
"""

from dataclasses import dataclass
from enum import StrEnum

from fishy.annual_statistics import TrendTreatment
from fishy.duration_minima import DurationEstimator, DurationThreshold
from fishy.duration_windows import DurationWindow, DurationWindows, WindowUncertaintySupport, duration_windows
from fishy.evidence import Check, CheckFinding, CheckSummary, Completeness, Provenance
from fishy.flows import FlowSample
from fishy.quantities import Flow
from fishy.scientific_acceptance import ScientificAssessment, UsePurpose
from fishy.time import Interval


class AssessmentStage(StrEnum):
    PROVISIONAL = "provisional_ecological"
    FINAL = "final_uncapped_requirement"
    REALISED = "realised_operating_flow"


@dataclass(frozen=True)
class CandidateReferenceRelation:
    """Explicit selected-family or realised-scenario link to retained reference evidence."""

    candidate: Provenance
    reference_identity: str
    basis: str

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, Provenance):
            raise TypeError("relation requires candidate provenance")
        if any(not isinstance(s, str) or not s.strip() for s in (self.reference_identity, self.basis)):
            raise ValueError("relation requires exact reference identity and supported basis")


@dataclass(frozen=True)
class WindowComparison:
    window: DurationWindow
    shortfall: Flow | None
    point: CheckFinding
    uncertainty: CheckFinding


@dataclass(frozen=True)
class LowFlowAssessment:
    candidate: tuple[FlowSample, ...]
    threshold: DurationThreshold
    stage: AssessmentStage
    candidate_basis: str
    reference_relation: CandidateReferenceRelation | None
    windows: DurationWindows
    comparisons: tuple[WindowComparison, ...]
    point: CheckSummary
    uncertainty: CheckSummary
    permission: Check
    scientific_assessment: ScientificAssessment | None

    @property
    def checks(self) -> CheckSummary:
        return CheckSummary(
            (
                Check("point", self.point.finding),
                Check("uncertainty", self.uncertainty.finding),
                Check("scientific_permission", self.permission.finding, self.permission.reasons),
                Check(
                    "point_coverage",
                    CheckFinding.PASS if self.point.completeness is Completeness.COMPLETE else CheckFinding.UNKNOWN,
                    ("all required window point comparisons must be evaluated",),
                ),
                Check(
                    "uncertainty_coverage",
                    CheckFinding.PASS
                    if self.uncertainty.completeness is Completeness.COMPLETE
                    else CheckFinding.UNKNOWN,
                    ("all required window uncertainty comparisons must be evaluated",),
                ),
            )
        )


def assess_low_flow(
    candidate: tuple[FlowSample, ...],
    period: Interval,
    threshold: DurationThreshold,
    *,
    stage: AssessmentStage,
    candidate_basis: str,
    provenance: Provenance,
    predecessor_basis: str | None,
    scientific_assessment: ScientificAssessment | None,
    uncertainty_support: WindowUncertaintySupport | None = None,
    purpose: UsePurpose = UsePurpose.SIZING,
    reference_relation: CandidateReferenceRelation | None = None,
) -> LowFlowAssessment:
    if not isinstance(threshold, DurationThreshold) or not isinstance(stage, AssessmentStage):
        raise TypeError("typed threshold and assessment stage required")
    if not isinstance(provenance, Provenance):
        raise TypeError("candidate requires Provenance")
    if not isinstance(candidate_basis, str) or not candidate_basis.strip():
        raise ValueError("candidate attribution required")
    if not isinstance(purpose, UsePurpose):
        raise TypeError("typed intended use required")
    reference = threshold.reference
    if reference_relation is not None:
        if (
            not isinstance(reference_relation, CandidateReferenceRelation)
            or reference_relation.candidate != provenance
            or reference_relation.reference_identity != reference.identity
        ):
            raise ValueError("candidate/reference relation does not bind these exact inputs")
    elif any(
        getattr(provenance, f) != getattr(reference.provenance, f)
        for f in ("scenario", "reference_member", "reference_kind")
    ):
        raise ValueError("changed member/scenario/reference meaning needs explicit reference relation")
    windows = duration_windows(
        candidate,
        period,
        reference.rule,
        location=reference.location,
        provenance=provenance,
        predecessor_basis=predecessor_basis,
        uncertainty_support=uncertainty_support,
    )
    comparisons = []
    for window in windows.windows:
        shortfall = None
        point = uncertainty = CheckFinding.UNKNOWN
        if window.mean is not None and threshold.value is not None:
            shortfall = Flow(max(0, threshold.value.value - window.mean.value))
            point = CheckFinding.FAIL if shortfall.value > 0 else CheckFinding.PASS
            if window.uncertainty is not None and threshold.uncertainty is not None:
                if window.uncertainty.lower.value >= threshold.uncertainty.upper.value:
                    uncertainty = CheckFinding.PASS
                elif window.uncertainty.upper.value < threshold.uncertainty.lower.value:
                    uncertainty = CheckFinding.FAIL
        comparisons.append(WindowComparison(window, shortfall, point, uncertainty))
    point_checks = CheckSummary(tuple(Check(str(i), c.point, c.window.reasons) for i, c in enumerate(comparisons)))
    uncertainty_checks = CheckSummary(
        tuple(
            Check(
                str(i),
                c.uncertainty,
                ("missing uncertainty is not measured certainty; overlap is indeterminate",)
                if c.uncertainty is CheckFinding.UNKNOWN
                else (),
            )
            for i, c in enumerate(comparisons)
        )
    )
    if scientific_assessment is not None and not isinstance(scientific_assessment, ScientificAssessment):
        raise TypeError("scientific permission requires ScientificAssessment")
    permission = (
        Check("scientific_use", CheckFinding.UNKNOWN, ("exact duration-minimum scientific assessment not supplied",))
        if scientific_assessment is None
        else scientific_assessment.acceptance_for(threshold.product(purpose))
    )
    if threshold.estimator is not DurationEstimator.IMPORTED and reference.trend not in (
        TrendTreatment.COMMON_CLIMATE,
        TrendTreatment.TRANSFORMED,
    ):
        permission = Check(
            "scientific_use",
            CheckFinding.FAIL,
            (*permission.reasons, "stationary minimum population lacks supported common-climate treatment"),
        )
    return LowFlowAssessment(
        candidate,
        threshold,
        stage,
        candidate_basis,
        reference_relation,
        windows,
        tuple(comparisons),
        point_checks,
        uncertainty_checks,
        permission,
        scientific_assessment,
    )
