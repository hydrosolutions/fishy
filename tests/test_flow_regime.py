"""Source transcription and independent numerical checks for flow-regime assessment."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction
from math import sqrt

import pytest

from fishy.evidence import CorrectionState, ProductionMethod, Provenance
from fishy.flow_regime import (
    PARDE_COEFFICIENTS,
    R_QUANTILES,
    REGIME_CV,
    SPECIFIC_LOW,
    SPECIFIC_MEAN,
    Extremum,
    ExtremumTie,
    FlushingCorrection,
    FlushingTreatment,
    LowFlowDuration,
    LowFlowStatistics,
    MonthlyRegime,
    Percent,
    ReferenceEllipse,
    RegimeReference,
    RunoffDepth,
    SeasonalityPoint,
    TroughApplicability,
    TroughDischarge,
    annual_mean_from_observations,
    assess_low_flow_duration,
    assess_low_flow_magnitude,
    assess_mean_flow,
    assess_seasonality,
    circular_timing,
    ellipse_distance,
    low_flow_duration,
    low_flow_from_observations,
    low_flow_thresholds,
    monthly_from_observations,
    monthly_from_parde,
    monthly_from_raster,
    raster_discharge,
    regime_low_flow,
    regime_mean_flow,
    seasonality_from_observations,
)
from fishy.flows import FlowSample, Presence
from fishy.hydrological_condition import AssessmentContext, AssessmentState, Indicator
from fishy.quantities import Area, Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

P = Provenance("synthetic", "test", "member", "test", "1", "1", ProductionMethod.ILLUSTRATIVE, CorrectionState.ORIGINAL)
L = Location(Reach("r", "1", WaterBody("w", "1")), CalculationSection("s", "1"), "1")
C = AssessmentContext(L, Interval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2010, 1, 1, tzinfo=UTC)), P)
NO_FLUSH = FlushingCorrection(FlushingTreatment.ABSENT, "documented no flushing")


def observations(year=2001, years=1, value=10):
    start = datetime(year, 1, 1, tzinfo=UTC)
    count = (datetime(year + years, 1, 1, tzinfo=UTC) - start).days
    return tuple(
        FlowSample(
            L,
            Interval(start + timedelta(days=i), start + timedelta(days=i + 1)),
            Flow(value(i) if callable(value) else value),
            Presence.PRESENT,
            P,
        )
        for i in range(count)
    )


def monthly(value):
    return MonthlyRegime((Flow(value),) * 12, "synthetic imported")


def low(value, cv=0):
    return LowFlowStatistics(
        Flow(value, "l/s"), Percent(Fraction(cv)) if cv is not None else None, "synthetic imported"
    )


# Complete independent Table 10 rows, not values generated from implementation.
@pytest.mark.parametrize(
    "index,expected",
    enumerate(
        [
            (18, 19.8, 21.9),
            (16.3, 18.3, 20.6),
            (17.5, 20.2, 23.8),
            (21.1, 23.9, 27.7),
            (19.3, 21.6, 24.7),
            (25.9, 28.8, 32.7),
            (31.5, 35.1, 39.8),
            (39.5, 43.4, 48.7),
            (40.4, 44.8, 49.9),
            (42.8, 47.7, 53.5),
            (44.9, 48.2, 52.3),
            (49.1, 54.2, 60.8),
            (27.7, 32.2, 38.4),
            (44.5, 49.8, 56.8),
            (52.8, 62, 75.1),
            (39.8, 45.6, 53.5),
        ]
    ),
)
def test_table10(index, expected):
    assert R_QUANTILES[index] == tuple(Fraction(str(v)) for v in expected)


@pytest.mark.parametrize("regime,expected", [(3, 2), (10, 1)])
def test_source_36_percent_contrast(regime, expected):
    result = assess_mean_flow(C, monthly(100), monthly(64), RegimeReference(regime, "supplied Swiss type"))
    assert result.classification == expected
    assert result.metrics[0].value == 36
    assert result.context is C
    assert len(result.inputs) == 3


@pytest.mark.parametrize("reduction,expected", [(29, 1), (30, 2), (45, 3), (60, 4), (85, 5), (100, 5)])
def test_absolute_mean_boundaries(reduction, expected):
    assert (
        assess_mean_flow(C, monthly(100), monthly(100 - reduction), RegimeReference(3, "source")).classification
        == expected
    )


def test_mean_flow_sums_absolute_monthly_changes_not_net_change():
    influenced = MonthlyRegime(tuple(Flow(v) for v in [150, 50] * 6), "source")
    assert assess_mean_flow(C, monthly(100), influenced, RegimeReference(3, "source")).metrics[0].value == 50


def test_mean_missing_zero_and_independent_absolute_class_one():
    assert assess_mean_flow(C, None, monthly(1), None).state is AssessmentState.UNDETERMINED
    assert assess_mean_flow(C, monthly(0), monthly(1), None).classification is None
    assert assess_mean_flow(C, monthly(100), monthly(90), None).classification == 1
    assert assess_mean_flow(C, monthly(100), monthly(64), None).classification is None


@pytest.mark.parametrize("kind,area,mean,low_q,cv", [(1, 10, 510, 32, 22), (16, 2, 62, 18.4, 21), (10, 1, 16, 4.4, 30)])
def test_regime_source_estimates(kind, area, mean, low_q, cv):
    regime = RegimeReference(kind, "explicit attribution")
    a = Area(Fraction(area), "km2")
    result = regime_mean_flow(regime, a)
    assert result.monthly_means[0] is not None
    assert result.monthly_means[0].value == Fraction(str(mean)) / 1000 * PARDE_COEFFICIENTS[0][kind - 1]
    low_result = regime_low_flow(regime, a)
    assert low_result.q347 == Flow(low_q, "l/s")
    assert low_result.coefficient_of_variation == Percent(Fraction(cv))
    assert regime in result.inputs


def test_estimate_table_transcription_all_types():
    assert (
        tuple(
            map(
                Fraction,
                ["51", "61", "54", "48", "43", "42", "49", "36", "27", "16", "21", "16", "52", "51", "35", "31"],
            )
        )
        == SPECIFIC_MEAN
    )
    assert (
        tuple(
            map(
                Fraction,
                [
                    "3.2",
                    "5.1",
                    "6.5",
                    "6.4",
                    "7",
                    "7.5",
                    "6.8",
                    "4.8",
                    "4.1",
                    "4.4",
                    "4.4",
                    "2.7",
                    "8.4",
                    "5.5",
                    "5.2",
                    "9.2",
                ],
            )
        )
        == SPECIFIC_LOW
    )
    assert (
        tuple(
            map(
                Fraction,
                ["22", "19", "19", "13", "18", "22", "30", "35", "38", "30", "37", "38", "19", "38", "34", "21"],
            )
        )
        == REGIME_CV
    )
    assert tuple(row[0] for row in PARDE_COEFFICIENTS) == tuple(
        map(Fraction, ["0.07", ".06", ".07", ".17", ".76", "2", "3.21", "3.09", "1.61", ".57", ".19", ".11"])
    )
    assert tuple(row[-1] for row in PARDE_COEFFICIENTS) == tuple(
        map(Fraction, [".91", ".9", ".99", "1.14", "1.33", "1.09", ".81", ".74", ".92", "1.21", "1.15", ".82"])
    )


def test_raster_and_parde_routes_preserve_units_and_inputs():
    depth = RunoffDepth(Fraction(100), Fraction(86400 * 30), "monthly raster")
    area = Area(Fraction(20), "km2")
    expected = Flow(Fraction(2_000_000, 2_592_000))
    assert raster_discharge(depth, area) == expected
    assert monthly_from_raster((depth,) * 12, area).monthly_means == (expected,) * 12
    assert monthly_from_parde(Flow(3), (Fraction(2),) * 12, "explicit coefficients").monthly_means == (Flow(6),) * 12


def test_complete_months_only_and_daily_pooled_annual_means():
    samples = observations(2000, 2, lambda i: 1 if i < 366 else 2)
    assert annual_mean_from_observations(samples).value == Flow(Fraction(1096, 731))
    feb = monthly_from_observations(samples).monthly_means[1]
    assert feb == Flow(Fraction(85, 57))  # Leap February contributes 29 values, not one equal-year mean.
    partial = monthly_from_observations(samples[1:])
    assert partial.monthly_means[0] == Flow(2)
    assert "1 incomplete" in partial.reasons[0]
    assert monthly_from_observations(()).monthly_means == (None,) * 12


@pytest.mark.parametrize(
    "q,expected",
    [
        (1, (20, 40, 65)),
        (50, (20, 40, 65)),
        (200, (25, 45, 70)),
        (500, (35, 55, 80)),
        (1000, (45, 65, 85)),
        (2000, (45, 65, 85)),
        (125, (22.5, 42.5, 67.5)),
        (350, (30, 50, 75)),
        (750, (40, 60, 82.5)),
    ],
)
def test_figure22_anchors_interpolation_and_endpoint_rule(q, expected):
    assert low_flow_thresholds(Flow(q, "l/s")) == tuple(Fraction(str(v)) for v in expected)


@pytest.mark.parametrize(
    "q,bounds", [(50, (20, 40, 65)), (200, (25, 45, 70)), (500, (35, 55, 80)), (1000, (45, 65, 85))]
)
def test_all_low_magnitude_class_boundaries(q, bounds):
    for expected, reduction in enumerate(bounds, 3):
        result = assess_low_flow_magnitude(
            C, low(q), low(Fraction(q) * (1 - Fraction(reduction, 100))), TroughApplicability.ABSENT
        )
        assert result.classification == expected
        below = assess_low_flow_magnitude(
            C,
            low(q),
            low(Fraction(q) * (1 - Fraction(reduction, 100) + Fraction(1, 10000))),
            TroughApplicability.ABSENT,
        )
        assert below.classification == expected - 1


def test_cv_better_class_increase_and_trough_substitution():
    assert assess_low_flow_magnitude(C, low(50, 90), low(10), TroughApplicability.ABSENT).classification == 1
    assert assess_low_flow_magnitude(C, low(50, 80), low(10), TroughApplicability.ABSENT).classification == 5
    assert assess_low_flow_magnitude(C, low(50, None), low(60), TroughApplicability.ABSENT).classification == 1
    assert assess_low_flow_magnitude(C, low(50, None), low(40), TroughApplicability.ABSENT).classification is None
    result = assess_low_flow_magnitude(
        C, low(50, 20), low(45), TroughApplicability.PRESENT, TroughDischarge(Fraction(1, 100), "subdaily minima")
    )
    assert result.classification == 5
    assert result.metrics[0].value == 80
    assert assess_low_flow_magnitude(C, low(50, 20), low(45), TroughApplicability.PRESENT).classification is None
    assert assess_low_flow_magnitude(C, low(0), low(0), TroughApplicability.ABSENT).classification is None


def test_pooled_q347_not_annual_mean_and_annual_cv():
    result = low_flow_from_observations(observations(2001, 2, lambda i: 1 if i < 365 else 9), NO_FLUSH)
    assert result.q347 == Flow(1)
    assert result.annual_q347 == ((2001, Flow(1)), (2002, Flow(9)))
    assert result.coefficient_of_variation is not None
    assert float(result.coefficient_of_variation.value) == pytest.approx(100 * sqrt(32) / 5)
    assert result.q347 != Flow(5)


def test_linear_quantile_and_flushing_correction():
    samples = observations(value=lambda i: i + 5)
    result = low_flow_from_observations(samples, NO_FLUSH)
    assert result.q347 == Flow(Fraction(116, 5))  # 5 + .05 * 364 = 23.2
    components = tuple(replace(s, value=Flow(4)) for s in samples)
    corrected = low_flow_from_observations(
        samples, FlushingCorrection(FlushingTreatment.SUBTRACT, "known components", components)
    )
    assert corrected.q347 == Flow(Fraction(96, 5))
    assert low_flow_from_observations(samples, FlushingCorrection(FlushingTreatment.UNKNOWN, "unknown")).q347 is None
    assert low_flow_from_observations(samples[1:], NO_FLUSH).q347 is None
    assert (
        low_flow_from_observations(
            samples, FlushingCorrection(FlushingTreatment.SUBTRACT, "missing", components[:-1])
        ).q347
        is None
    )
    excessive = tuple(replace(s, value=Flow(1000)) for s in samples)
    with pytest.raises(ValueError, match="exceeds"):
        low_flow_from_observations(samples, FlushingCorrection(FlushingTreatment.SUBTRACT, "invalid", excessive))


@pytest.mark.parametrize("indicator", [Indicator.FLOOD_SEASONALITY, Indicator.LOW_FLOW_SEASONALITY])
def test_circular_year_boundary(indicator):
    point = circular_timing((date(2001, 12, 31), date(2002, 1, 1)), "dates")
    january = circular_timing((date(2003, 1, 1),), "reference")
    result = assess_seasonality(C, indicator, point, january)
    assert result.classification == 1
    assert result.metrics[0].value < 0.01
    assert point is not None
    assert point.x > 0.99


@pytest.mark.parametrize("distance,expected", [(0.3, 1), (0.6, 2), (0.9, 3), (1.2, 4), (1.21, 5)])
def test_direct_seasonality_boundaries(distance, expected):
    result = assess_seasonality(
        C, Indicator.FLOOD_SEASONALITY, SeasonalityPoint(distance - 0.6, 0, "b"), SeasonalityPoint(-0.6, 0, "r")
    )
    assert result.classification == expected


def test_ellipse_and_direct_distinct_thresholds_and_geometry():
    regime = RegimeReference(3, "source")
    origin = SeasonalityPoint(0, 0, "origin")
    ellipse = ReferenceEllipse(origin, 0.1, 0.1, 0, regime, "supplied 75% zone")
    influenced = SeasonalityPoint(0.38, 0, "b")
    assert ellipse_distance(influenced, ellipse) == pytest.approx(0.28, abs=1e-12)
    assert assess_seasonality(C, Indicator.LOW_FLOW_SEASONALITY, influenced, ellipse).classification == 2
    assert (
        assess_seasonality(C, Indicator.LOW_FLOW_SEASONALITY, SeasonalityPoint(0.28, 0, "b"), origin).classification
        == 1
    )
    assert ellipse_distance(origin, ellipse) == 0
    elongated = ReferenceEllipse(origin, 0.5, 0.2, 0, regime, "specialist")
    assert ellipse_distance(SeasonalityPoint(0, 0.7, "b"), elongated) == pytest.approx(0.5)
    rotated = replace(elongated, rotation_radians=3.141592653589793 / 2)
    assert ellipse_distance(SeasonalityPoint(0.7, 0, "b"), rotated) == pytest.approx(0.5)


def test_observed_extrema_and_explicit_tie_policy():
    samples = observations(value=lambda i: 20 if i == 100 else (0 if i == 200 else 10))
    maximum = seasonality_from_observations(samples, Extremum.MAXIMUM, ExtremumTie.UNRESOLVED)
    minimum = seasonality_from_observations(samples, Extremum.MINIMUM, ExtremumTie.UNRESOLVED)
    expected_max = circular_timing((date(2001, 4, 11),), "x")
    expected_min = circular_timing((date(2001, 7, 20),), "x")
    assert maximum is not None and minimum is not None and expected_max is not None and expected_min is not None
    assert maximum.x == pytest.approx(expected_max.x)
    assert minimum.x == pytest.approx(expected_min.x)
    assert seasonality_from_observations(observations(), Extremum.MAXIMUM, ExtremumTie.UNRESOLVED) is None
    assert seasonality_from_observations(observations(), Extremum.MAXIMUM, ExtremumTie.EARLIEST) is not None
    assert seasonality_from_observations(samples[1:], Extremum.MAXIMUM, ExtremumTie.EARLIEST) is None


@pytest.mark.parametrize("days,expected", [(19, 1), (20, 2), (34, 2), (35, 3), (49, 3), (50, 4), (64, 4), (65, 5)])
def test_duration_intervals(days, expected):
    assert (
        assess_low_flow_duration(C, LowFlowDuration(Fraction(days), ((2001, days),), "source")).classification
        == expected
    )


def test_annual_longest_not_total_and_threshold_equality():
    samples = observations(value=lambda i: 1 if 10 <= i < 25 or 100 <= i < 115 else 10)
    result = low_flow_duration(samples, Flow(1))
    assert result is not None
    assert result.annual_longest == ((2001, 15),)
    assert result.mean_days == 15  # Total is 30, which would incorrectly classify as class 2.
    assert assess_low_flow_duration(C, result).classification == 1


def test_cross_year_spell_whole_and_assigned_start_year():
    samples = observations(2001, 2, lambda i: 1 if 355 <= i < 385 else 10)
    result = low_flow_duration(samples, Flow(1))
    assert result is not None
    assert result.annual_longest == ((2001, 30), (2002, 0))
    assert result.mean_days == 15
    partial = low_flow_duration(samples[:-1], Flow(1))
    assert partial is not None
    assert partial.annual_longest == ((2001, 30),)


def test_missing_and_terminal_spell_stay_unknown():
    samples = observations(value=lambda i: 1 if i >= 355 else 10)
    assert low_flow_duration(samples, Flow(1)) is None
    missing = replace(samples[20], value=None, presence=Presence.MISSING, reasons=("missing day",))
    assert low_flow_duration((*samples[:20], missing, *samples[21:]), Flow(1)) is None
    assert assess_low_flow_duration(C, None).state is AssessmentState.UNDETERMINED
    assert assess_seasonality(C, Indicator.FLOOD_SEASONALITY, None, None).classification is None


@pytest.mark.parametrize(
    "factory",
    [
        lambda: RegimeReference(17, "s"),
        lambda: regime_mean_flow(RegimeReference(1, "s"), Area(0)),
        lambda: Percent(Fraction(-1)),
        lambda: TroughDischarge(Fraction(-1), "s"),
        lambda: SeasonalityPoint(float("nan"), 0, "s"),
        lambda: SeasonalityPoint(2, 0, "s"),
        lambda: MonthlyRegime((Flow(1),), "s"),
        lambda: RunoffDepth(Fraction(1), Fraction(0), "s"),
    ],
)
def test_invalid_domain_inputs_raise_not_unknown(factory):
    with pytest.raises((ValueError, TypeError)):
        factory()


def test_invalid_daily_overlap_resolution_and_location():
    samples = observations()
    with pytest.raises(ValueError, match="overlap"):
        monthly_from_observations((samples[0], samples[0]))
    coarse = replace(samples[0], interval=Interval(samples[0].interval.start, samples[1].interval.end))
    with pytest.raises(ValueError, match="daily"):
        monthly_from_observations((coarse,))


def test_missing_regime_cannot_disable_type_independent_worst_class():
    assert assess_mean_flow(C, monthly(100), monthly(0), None).classification == 5


def test_excluded_months_retain_incomplete_coverage():
    from fishy.evidence import Completeness

    samples = observations(2001, 2)[1:]
    result = assess_mean_flow(C, monthly_from_observations(samples), monthly(10), RegimeReference(3, "s"))
    assert result.classification == 1
    assert result.coverage is Completeness.INCOMPLETE


def test_observation_assessments_and_unknowns_keep_original_inputs():
    from fishy.flow_regime import (
        assess_duration_observations,
        assess_low_flow_observations,
        assess_mean_flow_observations,
        assess_seasonality_observations,
    )

    samples = observations(2001, 2, lambda i: 1 if i in (100, 465) else 10)
    mean_result = assess_mean_flow_observations(C, samples, samples, RegimeReference(3, "s"))
    assert mean_result.classification == 1
    low_result = assess_low_flow_observations(C, samples, samples, NO_FLUSH, NO_FLUSH, TroughApplicability.ABSENT)
    # Constant annual Q347 has CV=0, so strict delta<CV is false; preserve source strictness.
    assert low_result.classification == 2
    assert isinstance(low_result.inputs[0], LowFlowStatistics)
    assert low_result.inputs[0].inputs[0] == samples
    season_result = assess_seasonality_observations(
        C, Indicator.LOW_FLOW_SEASONALITY, samples, samples, ExtremumTie.UNRESOLVED
    )
    assert season_result.classification == 1
    assert season_result.inputs[0] == samples
    unknown = assess_seasonality_observations(C, Indicator.FLOOD_SEASONALITY, samples, samples, ExtremumTie.UNRESOLVED)
    assert unknown.classification is None
    assert unknown.inputs[0] == samples
    duration_result = assess_duration_observations(C, samples, Flow(1))
    assert duration_result.classification == 1
    assert duration_result.inputs[0] == samples
    missing = assess_duration_observations(C, samples, None)
    assert missing.classification is None
    assert missing.inputs[0] == samples


def test_observation_assessment_refuses_relabelled_context():
    from fishy.flow_regime import assess_duration_observations

    samples = observations()
    with pytest.raises(ValueError, match="scenario"):
        assess_duration_observations(replace(C, provenance=replace(P, scenario="other")), samples, Flow(1))
    other_location = replace(L, mapping_version="other")
    with pytest.raises(ValueError, match="location"):
        assess_duration_observations(replace(C, location=other_location), samples, Flow(1))
    with pytest.raises(ValueError, match="outside"):
        assess_duration_observations(replace(C, period=samples[0].interval), samples, Flow(1))


def test_initial_low_spell_has_unknown_start_not_invented_january_start():
    samples = observations(value=lambda i: 1 if i < 10 else 10)
    assert low_flow_duration(samples, Flow(1)) is None


def test_parde_ratio_and_unmodified_rounded_source_coefficients():
    from fishy.flow_regime import parde_from_means

    assert parde_from_means(monthly(2), Flow(4)).monthly == (Fraction(1, 2),) * 12
    assert parde_from_means(monthly(2), Flow(0)).monthly == (None,) * 12
    first = regime_mean_flow(RegimeReference(1, "Swiss"), Area(Fraction(1), "km2"))
    parde = parde_from_means(first, Flow(51, "l/s"))
    assert all(v is not None for v in parde.monthly)
    assert sum(v for v in parde.monthly if v is not None) != 12


def test_regime_matching_both_hit_counts_and_two_hit_margin():
    from fishy.flow_regime import PardeCoefficients, PardeEnvelope, match_parde_regime

    values = PardeCoefficients((Fraction(1),) * 12, "measured")

    def envelope(kind, hits, wider_hits):
        return PardeEnvelope(
            RegimeReference(kind, "Swiss A2 supplied"),
            (Fraction(0),) * 12,
            (Fraction(1),) * hits + (Fraction(0),) * (12 - hits),
            (Fraction(0),) * 12,
            (Fraction(1),) * wider_hits + (Fraction(0),) * (12 - wider_hits),
            "supplied A2 zone",
        )

    others = tuple(envelope(i, 0, 0) for i in range(3, 17))
    clear = match_parde_regime(values, (envelope(1, 12, 12), envelope(2, 10, 10), *others))
    assert clear.regime is not None
    assert clear.regime.swiss_type == 1
    assert clear.hits[0] == (1, 12, 12)
    assert match_parde_regime(values, (envelope(1, 12, 12), envelope(2, 11, 11), *others)).regime is None
    assert match_parde_regime(values, (envelope(1, 12, 12), envelope(2, 9, 11), *others)).regime is None
    assert match_parde_regime(values, (envelope(1, 12, 12),)).regime is None
    with pytest.raises(ValueError, match="duplicate"):
        match_parde_regime(values, (envelope(1, 12, 12), envelope(1, 12, 12)))


def test_predecessor_and_successor_resolve_boundary_spells():
    start = datetime(2001, 1, 1, tzinfo=UTC)
    samples = observations(value=lambda i: 1 if i < 10 or i >= 360 else 10)
    preceding = replace(samples[0], value=Flow(10), interval=Interval(start - timedelta(days=1), start))
    end = samples[-1].interval.end
    following = replace(samples[0], value=Flow(10), interval=Interval(end, end + timedelta(days=1)))
    result = low_flow_duration((preceding, *samples, following), Flow(1))
    assert result is not None
    assert result.annual_longest == ((2001, 10),)


def test_observation_order_does_not_change_coverage():
    samples = observations()
    forward = assess_mean_flow(C, monthly_from_observations(samples), monthly(10), RegimeReference(3, "s"))
    reverse = assess_mean_flow(
        C, monthly_from_observations(tuple(reversed(samples))), monthly(10), RegimeReference(3, "s")
    )
    assert reverse.coverage == forward.coverage


def test_observation_reference_location_must_be_explicitly_transferred():
    from fishy.flow_regime import assess_mean_flow_observations

    samples = observations()
    reference = tuple(replace(s, location=replace(L, mapping_version="elsewhere")) for s in samples)
    with pytest.raises(ValueError, match="reference location"):
        assess_mean_flow_observations(C, reference, samples, RegimeReference(3, "s"))


def test_observation_member_cannot_be_relabelled():
    from fishy.flow_regime import assess_duration_observations

    with pytest.raises(ValueError, match="reference_member"):
        assess_duration_observations(
            replace(C, provenance=replace(P, reference_member="other")), observations(), Flow(1)
        )


def test_mean_estimate_selected_excluded_years_and_source_intervals():
    from fishy.evidence import Completeness

    samples = observations(2000, 2)[1:]
    result = annual_mean_from_observations(samples)
    assert result.selected_years == (2001,)
    assert result.excluded_years == (2000,)
    assert result.coverage is Completeness.INCOMPLETE
    assert result.inputs == (samples,)


def test_shorter_observation_window_retains_partial_assessment_coverage():
    from fishy.evidence import Completeness
    from fishy.flow_regime import assess_mean_flow_observations

    samples = observations()
    result = assess_mean_flow_observations(C, samples, samples, RegimeReference(3, "s"))
    assert result.classification == 1
    assert result.coverage is Completeness.INCOMPLETE
    exact_context = replace(C, period=Interval(samples[0].interval.start, samples[-1].interval.end))
    assert (
        assess_mean_flow_observations(exact_context, samples, samples, RegimeReference(3, "s")).coverage
        is Completeness.COMPLETE
    )


def test_reference_period_and_kind_are_not_silently_relabelled():
    from fishy.evidence import ReferenceKind
    from fishy.flow_regime import assess_mean_flow_observations

    reference = tuple(
        replace(
            s,
            provenance=replace(P, reference_kind=ReferenceKind.PRESENT_CLIMATE_NATURAL, scenario="historic reference"),
        )
        for s in observations(1999)
    )
    influenced = observations(2001)
    result = assess_mean_flow_observations(C, reference, influenced, RegimeReference(3, "s"))
    assert result.classification == 1
    assert isinstance(result.inputs[0], MonthlyRegime)
    assert result.inputs[0].inputs[0] == reference


def test_warmup_year_cannot_enter_q347_or_annual_mean():
    samples = observations(2001, 2, lambda i: 1 if i < 365 else 10)
    excluded = samples[0].interval
    warmup = tuple(replace(s, provenance=replace(P, excluded_warmup=(excluded,))) for s in samples)
    estimate = annual_mean_from_observations(warmup)
    assert estimate.selected_years == (2002,)
    assert estimate.value == Flow(10)
    assert low_flow_from_observations(warmup, NO_FLUSH).q347 == Flow(10)


@pytest.mark.parametrize("distance,expected", [(0.25, 1), (0.5, 2), (0.75, 3), (1, 4), (1.01, 5)])
def test_ellipse_inclusive_thresholds_at_declared_numerical_precision(distance, expected):
    ellipse = ReferenceEllipse(
        SeasonalityPoint(-0.9, 0, "centre"), 0.1, 0.1, 0, RegimeReference(3, "Swiss source"), "supplied ellipse"
    )
    point = SeasonalityPoint(-0.8 + distance, 0, "influenced")
    result = assess_seasonality(C, Indicator.FLOOD_SEASONALITY, point, ellipse)
    assert result.metrics[0].value == pytest.approx(distance, abs=1e-12)
    assert result.classification == expected


def test_flushing_components_cannot_cross_scenarios():
    samples = observations()
    components = tuple(replace(s, value=Flow(1), provenance=replace(P, scenario="other")) for s in samples)
    with pytest.raises(ValueError, match="flushing component scenario"):
        low_flow_from_observations(samples, FlushingCorrection(FlushingTreatment.SUBTRACT, "components", components))


@pytest.mark.parametrize(
    "regime,column",
    enumerate(
        [
            "0.07 0.06 0.07 0.17 0.76 2 3.21 3.09 1.61 0.57 0.19 0.11",
            "0.13 0.12 0.17 0.37 1.08 2.19 2.86 2.52 1.46 0.57 0.29 0.19",
            "0.18 0.17 0.21 0.46 1.35 2.44 2.58 2.04 1.25 0.67 0.37 0.23",
            "0.24 0.2 0.2 0.4 1.41 2.68 2.34 1.58 1.2 0.85 0.51 0.33",
            "0.21 0.2 0.26 0.62 1.69 2.64 2.15 1.6 1.1 0.71 0.48 0.29",
            "0.33 0.34 0.49 0.99 2.16 2.29 1.61 1.15 0.89 0.7 0.58 0.43",
            "0.44 0.52 0.81 1.44 1.9 1.73 1.34 1.08 0.85 0.66 0.66 0.56",
            "0.59 0.71 1.06 1.65 1.59 1.34 1.12 0.97 0.79 0.7 0.8 0.66",
            "0.96 1.11 1.27 1.25 1.03 1.12 0.94 0.79 0.84 0.7 0.89 1.11",
            "1.14 1.33 1.3 1.16 1.05 1.02 0.77 0.67 0.69 0.75 0.96 1.17",
            "1.07 1.21 1.45 1.61 1.07 0.85 0.64 0.51 0.64 0.77 1.02 1.19",
            "1.39 1.52 1.54 1.28 0.95 0.84 0.55 0.35 0.48 0.75 0.97 1.42",
            "0.29 0.25 0.29 0.59 1.79 2.49 1.79 1.22 1.13 1.04 0.7 0.39",
            "0.33 0.31 0.56 1.26 2.18 1.73 0.99 0.73 1.18 1.36 0.91 0.44",
            "0.52 0.46 0.72 1.48 1.8 1.42 0.86 0.55 1 1.45 1.13 0.59",
            "0.91 0.9 0.99 1.14 1.33 1.09 0.81 0.74 0.92 1.21 1.15 0.82",
        ],
        start=1,
    ),
)
def test_table3_all_192_cells_from_primary_pdf_columns(regime, column):
    # Independently transcribed down PDF p.37 (printed p.35), Table3 columns.
    # Implementation stores month rows; this fixture deliberately stores type columns.
    expected = tuple(Fraction(value) for value in column.split())
    assert tuple(row[regime - 1] for row in PARDE_COEFFICIENTS) == expected
    result = regime_mean_flow(RegimeReference(regime, "explicit Swiss type"), Area(2, "km2"))
    mean = SPECIFIC_MEAN[regime - 1] * Fraction(2, 1000)
    assert result.monthly_means == tuple(Flow(mean * coefficient) for coefficient in expected)
