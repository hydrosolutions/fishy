"""Exact arithmetic and support tests for source-bound correction operators."""

from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction

import pytest

from fishy.evidence import (
    CheckFinding,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ScientificAdequacy,
)
from fishy.flow_bounds import (
    AnnualReferenceVolume,
    BoundConflict,
    CandidateStatus,
    CorrectionOrder,
    DesignBounds,
    correct_schedule,
)
from fishy.flows import Coverage, FlowSample, Presence
from fishy.quantities import Flow, Volume
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.spawning import TimedCoefficient, coefficient_scope
from fishy.time import Interval

LOCATION = Location(Reach("r", "v1", WaterBody("river", "v1")), CalculationSection("s", "v1"), "mapping1")
YEAR = Interval(datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC))
P = Provenance(
    "synthetic",
    "scenario",
    "natural-member",
    "software1",
    "data1",
    "config1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
)
RESULT = replace(P, source="candidate", correction_state=CorrectionState.CORRECTED)


def sample(value, period=YEAR):
    return FlowSample(LOCATION, period, Flow(value), Presence.PRESENT, P)


def coefficient(value="1.5", period=YEAR):
    findings = EvidenceFindings(
        coefficient_scope(LOCATION, period, P),
        P,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("synthetic supported coefficient",),
    )
    return TimedCoefficient(LOCATION, period, Fraction(value), P, findings)


def bounds(periods=(YEAR,), recorded=3, low=5, high=10):
    return DesignBounds(
        tuple(sample(recorded, p) for p in periods),
        tuple(sample(low, p) for p in periods),
        tuple(sample(high, p) for p in periods),
        AnnualReferenceVolume(LOCATION, YEAR, Volume(5 * YEAR.seconds), Presence.PRESENT, P),
        AnnualReferenceVolume(LOCATION, YEAR, Volume(10 * YEAR.seconds), Presence.PRESENT, P),
        "179-НҚ:2025-07-23",
    )


@pytest.mark.parametrize(
    "order,expected,prebound,conflict",
    [
        (CorrectionOrder.CORRECTION_THEN_BOUNDS, 10, 12, BoundConflict.SUPPRESSED_CORRECTION),
        (CorrectionOrder.BOUNDS_THEN_CORRECTION, 12, 8, BoundConflict.UPPER_EXCEEDED),
    ],
)
def test_discriminator_real_volume_and_unresolved_priority(order, expected, prebound, conflict):
    result = correct_schedule((sample(8),), bounds(), (coefficient(),), order, RESULT)
    assert result.samples[0].value == Flow(expected)
    assert result.intervals[0].pre_bound == Flow(prebound)
    assert result.intervals[0].conflicts == (conflict,)
    assert result.actual_volume == Volume(expected * YEAR.seconds)
    assert result.status is CandidateStatus.INTERPRETED
    assert result.bounds.natural_p99[0].value == Flow(5)
    assert result.annual_checks.finding is (CheckFinding.PASS if expected == 10 else CheckFinding.FAIL)
    assert result.annual_scientific_use[0].finding is CheckFinding.UNKNOWN
    assert result.intervals[0].scientific_use.finding is CheckFinding.PASS
    assert result.samples[0].components[0] == sample(8)


def test_each_bound_adjustment_retained_and_recorded_floor_not_discarded():
    result = correct_schedule(
        (sample(1),), bounds(recorded=4, low=5), (coefficient(1),), CorrectionOrder.CORRECTION_THEN_BOUNDS, RESULT
    )
    assert [a.delta_m3_s for a in result.intervals[0].adjustments] == [3, 1, 0]
    assert result.samples[0].value == Flow(5)


@pytest.mark.parametrize("order", list(CorrectionOrder))
def test_crossed_bounds_refuse_before_any_candidate(order):
    result = correct_schedule((sample(8),), bounds(recorded=11), (coefficient(),), order, RESULT)
    assert result.samples[0].value is None
    assert result.intervals[0].pre_bound is None
    assert result.intervals[0].adjustments == ()
    assert result.intervals[0].conflicts == (BoundConflict.CROSSED,)
    assert result.actual_volume is None
    assert result.status is CandidateStatus.UNRESOLVED


def test_crossed_annual_bounds_stop_schedule_and_remain_attributed():
    source = bounds()
    source = replace(source, annual_p99=replace(source.annual_p99, value=Volume(11 * YEAR.seconds)))
    result = correct_schedule((sample(8),), source, (coefficient(),), CorrectionOrder.CORRECTION_THEN_BOUNDS, RESULT)
    assert result.intervals[0].pre_bound is None
    assert "crossed annual bounds" in result.reasons


def test_missing_order_and_coefficient_preserve_uncorrected_values():
    result = correct_schedule((sample(8),), bounds(), (None,), None, RESULT)
    assert result.intervals[0].original.value == Flow(8)
    assert result.samples[0].value is None
    assert result.actual_volume is None


def test_timing_and_leap_days_no_volume_renormalisation():
    feb = Interval(datetime(2024, 2, 1, tzinfo=UTC), datetime(2024, 3, 1, tzinfo=UTC))
    march = Interval(feb.end, datetime(2024, 4, 1, tzinfo=UTC))
    periods = (feb, march)
    result = correct_schedule(
        tuple(sample(8, p) for p in periods),
        bounds(periods),
        (coefficient("1.5", feb), coefficient(1, march)),
        CorrectionOrder.CORRECTION_THEN_BOUNDS,
        RESULT,
    )
    assert result.supported_volume == Volume((10 * 29 + 8 * 31) * 86400)
    assert result.actual_volume is None  # partial annual horizon is not an annual total
    assert [s.value for s in result.samples] == [Flow(10), Flow(8)]


def test_missing_interval_does_not_erase_supported_numerics_or_invent_total():
    midpoint = datetime(2024, 7, 1, tzinfo=UTC)
    periods = (Interval(YEAR.start, midpoint), Interval(midpoint, YEAR.end))
    result = correct_schedule(
        tuple(sample(8, p) for p in periods),
        bounds(periods),
        (coefficient(1, periods[0]), None),
        CorrectionOrder.CORRECTION_THEN_BOUNDS,
        RESULT,
    )
    assert result.samples[0].value == Flow(8)
    assert result.samples[1].value is None
    assert result.supported_volume == Volume(8 * periods[0].seconds)
    assert result.actual_volume is None


@pytest.mark.parametrize("alteration", ["location", "interval", "scenario", "member"])
def test_misaligned_coefficient_is_rejected(alteration):
    c = coefficient()
    if alteration == "location":
        c = replace(c, location=replace(LOCATION, mapping_version="other"))
    elif alteration == "interval":
        c = replace(c, interval=Interval(datetime(2024, 2, 1, tzinfo=UTC), YEAR.end))
    elif alteration == "scenario":
        c = replace(c, provenance=replace(P, scenario="other"))
    else:
        c = replace(c, provenance=replace(P, reference_member="other"))
    with pytest.raises(ValueError):
        correct_schedule((sample(8),), bounds(), (c,), CorrectionOrder.CORRECTION_THEN_BOUNDS, RESULT)


def test_scientific_rejection_does_not_promote_or_erase_numeric_candidate():
    c = coefficient()
    c = replace(c, findings=replace(c.findings, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED))
    result = correct_schedule((sample(8),), bounds(), (c,), CorrectionOrder.CORRECTION_THEN_BOUNDS, RESULT)
    assert result.samples[0].value == Flow(10)
    assert result.intervals[0].scientific_use.finding is CheckFinding.FAIL


def test_stale_findings_and_warmup_cannot_support_correction():
    c = coefficient()
    c = replace(c, findings=replace(c.findings, provenance=replace(P, data_version="old")))
    result = correct_schedule((sample(8),), bounds(), (c,), CorrectionOrder.CORRECTION_THEN_BOUNDS, RESULT)
    assert result.samples[0].value is None
    assert result.intervals[0].scientific_use.finding is CheckFinding.UNKNOWN
    excluded = replace(sample(8), provenance=replace(P, excluded_warmup=(YEAR,)))
    result = correct_schedule((excluded,), bounds(), (coefficient(),), CorrectionOrder.CORRECTION_THEN_BOUNDS, RESULT)
    assert result.samples[0].value is None


def test_partial_bound_preserves_unresolved_and_zero_stays_zero():
    b = bounds(low=0, recorded=0)
    result = correct_schedule((sample(0),), b, (coefficient(1),), CorrectionOrder.CORRECTION_THEN_BOUNDS, RESULT)
    assert result.samples[0].value == Flow(0)
    b = replace(b, natural_p99=(replace(sample(0), coverage=Coverage.PARTIAL, reasons=("missing support",)),))
    result = correct_schedule((sample(0),), b, (coefficient(1),), CorrectionOrder.CORRECTION_THEN_BOUNDS, RESULT)
    assert result.samples[0].value is None


def test_bounds_then_reduction_exposes_lower_conflict():
    result = correct_schedule(
        (sample(8),), bounds(), (coefficient("0.5"),), CorrectionOrder.BOUNDS_THEN_CORRECTION, RESULT
    )
    assert result.samples[0].value == Flow(4)
    assert result.intervals[0].conflicts == (BoundConflict.LOWER_EXCEEDED,)


def test_immutable_input_validation_and_result_not_observed():
    with pytest.raises(TypeError):
        AnnualReferenceVolume(LOCATION, YEAR, 3, Presence.PRESENT, P)  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError):
        correct_schedule((sample(8),), bounds(), (coefficient(),), CorrectionOrder.CORRECTION_THEN_BOUNDS, P)
    with pytest.raises(ValueError):
        correct_schedule(
            (sample(8), sample(8)), bounds(), (coefficient(),), CorrectionOrder.CORRECTION_THEN_BOUNDS, RESULT
        )


def test_partial_volume_already_above_annual_upper_preserves_known_failure():
    first = Interval(YEAR.start, datetime(2024, 12, 1, tzinfo=UTC))
    second = Interval(first.end, YEAR.end)
    b = bounds((first, second), high=20)
    result = correct_schedule(
        (sample(12, first), sample(12, second)),
        b,
        (coefficient(1, first), None),
        CorrectionOrder.CORRECTION_THEN_BOUNDS,
        RESULT,
    )
    assert result.actual_volume is None
    assert result.supported_volume.value > b.annual_p50.value.value
    assert result.annual_checks.finding is CheckFinding.FAIL
    assert result.annual_checks.checks[0].finding is CheckFinding.UNKNOWN


def test_annual_reference_refuses_partial_year_identity():
    partial = Interval(YEAR.start, datetime(2024, 2, 1, tzinfo=UTC))
    with pytest.raises(ValueError, match="whole Gregorian"):
        AnnualReferenceVolume(LOCATION, partial, Volume(1), Presence.PRESENT, P)


def test_supplied_biological_monthly_schedule_enters_bounds_and_changes_annual_volume():
    from datetime import timedelta

    from fishy.design_conditions import DesignClass
    from fishy.evidence import EvidenceScope
    from fishy.quantities import SignedState, StateVariable
    from fishy.spawning import (
        BiologicalTiming,
        CoefficientInterpretation,
        EligibilityInterpretation,
        StarRelevance,
        TemporalBasis,
        spawning_schedule,
    )

    months = tuple(
        Interval(datetime(2024, m, 1, tzinfo=UTC), datetime(2024, m + 1, 1, tzinfo=UTC) if m < 12 else YEAR.end)
        for m in range(1, 13)
    )
    onset = datetime(2024, 4, 15, tzinfo=UTC)
    period = Interval(onset, onset + timedelta(days=6))
    timing_evidence = replace(
        coefficient().findings,
        scope=EvidenceScope(
            "spawning_timing", LOCATION.reach.identifier, P.reference_member, period, "spawning_correction"
        ),
    )
    timing = BiologicalTiming(
        "Сазан",
        onset,
        0,
        (2, 2, 2),
        SignedState(StateVariable.TEMPERATURE, 15, "degC", "water"),
        SignedState(StateVariable.TEMPERATURE, 15, "degC", "water"),
        timing_evidence,
        LOCATION,
    )
    coefficients = spawning_schedule(
        LOCATION,
        months,
        P,
        DesignClass.MODERATELY_DRY,
        EligibilityInterpretation.PERCENTAGE_WORDING,
        TemporalBasis.MONTHLY_AVERAGE,
        CoefficientInterpretation.LISTED_VALUE,
        StarRelevance.NOT_RELIED_UPON,
        timing,
        tuple(coefficient(1, m).findings for m in months),
        basin_row=2,
    )
    result = correct_schedule(
        tuple(sample(8, m) for m in months),
        bounds(months),
        coefficients,
        CorrectionOrder.CORRECTION_THEN_BOUNDS,
        RESULT,
    )
    assert result.samples[3].value == Flow("9.44")
    assert result.samples[0].value == Flow(8)
    assert result.actual_volume == Volume(8 * YEAR.seconds + Fraction("1.44") * 30 * 86400)
    assert result.actual_volume.value > 8 * YEAR.seconds
    assert result.status is CandidateStatus.INTERPRETED
