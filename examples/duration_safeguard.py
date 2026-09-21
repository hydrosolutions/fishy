"""synthetic_duration_assessment : CompleteReferenceYears × CandidateYear → LowFlowAssessment.

Run with ``uv run python examples/duration_safeguard.py``. All evidence and
singleton bounds below are explicit hypothetical assumptions, not basin data.
"""

from datetime import UTC, datetime, timedelta
from math import exp

from fishy.annual_statistics import TrendTreatment
from fishy.duration_minima import DurationEstimator, construct_duration_reference, estimate_duration_threshold
from fishy.duration_windows import DurationWindowRule, WindowDomain, WindowUncertaintySupport
from fishy.evidence import CorrectionState, ProductionMethod, Provenance, ReferenceKind
from fishy.flows import FlowSample, Presence
from fishy.low_flow_frequency import LowFlowReturnPeriod
from fishy.low_flow_safeguard import AssessmentStage, LowFlowAssessment, assess_low_flow
from fishy.quantities import Flow, FlowBounds
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def main() -> LowFlowAssessment:
    location = Location(Reach("river", "1", WaterBody("water-body", "1")), CalculationSection("control", "1"), "1")
    provenance = Provenance(
        "synthetic duration example",
        "hypothetical",
        "reference-a",
        "example-v1",
        "data-v1",
        "profile-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
    )
    rule = DurationWindowRule(7, WindowDomain.ANNUAL, 1, 0, None, "hypothetical seven-day annual test")
    start = datetime(2001, 1, 1, tzinfo=UTC)
    end = datetime(2003, 1, 1, tzinfo=UTC)
    wet, dry = 10 * exp(0.3), 10 * exp(-0.3)
    reference_samples = tuple(
        FlowSample(
            location,
            Interval(start + timedelta(days=i), start + timedelta(days=i + 1)),
            Flow(wet if i < 365 else dry),
            Presence.PRESENT,
            provenance,
        )
        for i in range(-6, 730)
    )
    reference = construct_duration_reference(
        reference_samples,
        Interval(start, end),
        rule,
        location=location,
        provenance=provenance,
        predecessor_basis="six explicitly supplied hypothetical wet days",
        climate_basis="stipulated common-climate synthetic years",
        trend=TrendTreatment.COMMON_CLIMATE,
        climate_evidence="scenario assumption, not scientific validation",
        dependence="shared synthetic reference errors",
    )
    threshold = estimate_duration_threshold(
        reference, LowFlowReturnPeriod(100), estimator=DurationEstimator.ZERO_MIXTURE, profile_version="synthetic-v1"
    )
    assert threshold.value is not None
    # A separate supported analysis would normally supply uncertainty. Here the
    # exact fitted number is held fixed solely to demonstrate synthetic support.
    fixed_threshold = FlowBounds(threshold.value, threshold.value, "fixed synthetic estimate", "example", "stipulation")
    threshold = estimate_duration_threshold(
        reference,
        LowFlowReturnPeriod(100),
        estimator=DurationEstimator.ZERO_MIXTURE,
        profile_version="synthetic-fixed-v1",
        uncertainty=fixed_threshold,
    )
    year = Interval(datetime(2020, 1, 1, tzinfo=UTC), datetime(2021, 1, 1, tzinfo=UTC))
    fixed_flow = FlowBounds(Flow(10), Flow(10), "fixed synthetic schedule", "example", "stipulation")
    candidate = tuple(
        FlowSample(
            location,
            Interval(year.start + timedelta(days=i), year.start + timedelta(days=i + 1)),
            Flow(10),
            Presence.PRESENT,
            provenance,
            uncertainty=fixed_flow,
        )
        for i in range(-6, 366)
    )
    result = assess_low_flow(
        candidate,
        year,
        threshold,
        stage=AssessmentStage.FINAL,
        candidate_basis="uncapped constant hypothetical requirement; no quality/receptor claim",
        provenance=provenance,
        predecessor_basis="six explicitly supplied hypothetical predecessor days",
        scientific_assessment=None,
        uncertainty_support=WindowUncertaintySupport(
            "joint fixed synthetic bounds", "example", "all values held fixed by assumption"
        ),
    )
    assert threshold.value is not None
    print(f"Threshold: {float(threshold.value.value):.12f} m3/s")
    print(
        f"Windows: {len(result.comparisons)}; point: {result.point.finding}; uncertainty: {result.uncertainty.finding}"
    )
    print(f"Scientific permission: {result.permission.finding}; no regime is issued by this example")
    return result


if __name__ == "__main__":
    main()
