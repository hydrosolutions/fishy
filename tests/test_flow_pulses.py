"""HYDMOD source pulse examples; numerical witnesses, not ecological validation."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction
from zoneinfo import ZoneInfo

import pytest

from fishy.evidence import Completeness, CorrectionState, ProductionMethod, Provenance, ReferenceKind
from fishy.flow_pulses import (
    FlushingMetrics,
    FlushingOperation,
    FlushingTiming,
    HydropeakingApplicability,
    HydropeakingMetrics,
    HydropeakingOperation,
    HydropeakingReview,
    InstantaneousDischarge,
    PulseObservation,
    PulseSampling,
    StageRate,
    assess_flushing,
    assess_hydropeaking,
    catchment_correction,
    estimate_flushing,
    estimate_hydropeaking,
    observe_flushing,
    observe_hydropeaking,
    stage_correction,
)
from fishy.hydrological_condition import AssessmentContext, AssessmentState
from fishy.quantities import Area, Flow, SignedState, StateVariable
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

LOCATION = Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "1")
PROVENANCE = Provenance(
    "synthetic",
    "scenario",
    "member",
    "test",
    "1",
    "1",
    ProductionMethod.RECONSTRUCTED,
    CorrectionState.ORIGINAL,
    ReferenceKind.NATURALISED_HISTORICAL,
)
CONTEXT = AssessmentContext(
    LOCATION, Interval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2006, 1, 1, tzinfo=UTC)), PROVENANCE
)
AREA = Area(1250, "km2")


def metrics(result):
    return {m.name: m.value for m in result.metrics}


def pulse(x, y):
    return HydropeakingMetrics(
        InstantaneousDischarge(x),
        InstantaneousDischarge(Fraction(x) / Fraction(y)),
        Fraction(y),
        StageRate(Fraction(2)),
        StageRate(Fraction(1)),
        "specialist",
    )


@pytest.mark.parametrize(
    "rate,expected",
    [
        (0, Fraction(65, 100)),
        (0.5, Fraction(65, 100)),
        (0.75, Fraction(7, 10)),
        (1, Fraction(3, 4)),
        (1.5, Fraction(7, 8)),
        (2, Fraction(1)),
        (3, Fraction(5, 4)),
        (4, Fraction(3, 2)),
        (100, Fraction(3, 2)),
    ],
)
def test_stage_correction_anchors_and_interpolation(rate, expected):
    assert stage_correction(StageRate(rate)) == expected


@pytest.mark.parametrize(
    "area,expected",
    [
        (1, Fraction(1, 2)),
        (250, Fraction(1, 2)),
        (500, Fraction(5, 8)),
        (750, Fraction(3, 4)),
        (1000, Fraction(7, 8)),
        (1250, Fraction(1)),
        (2000, Fraction(1)),
    ],
)
def test_catchment_correction(area, expected):
    assert catchment_correction(Area(area, "km2")) == expected


@pytest.mark.parametrize(
    "x,y,expected",
    [
        (0.1, 1.5, 1),
        (0.1, 2.5, 2),
        (0.1, 3.5, 3),
        (0.1, 5, 4),
        (0.1, 6.5, 5),
        (1, 1.3, 1),
        (1, 2, 2),
        (1, 3, 3),
        (1, 4.5, 4),
        (1, 6, 5),
        (3, 1.1, 1),
        (3, 1.35, 2),
        (3, 1.7, 3),
        (3, 2.2, 4),
        (3, 5, 5),
    ],
)
def test_figure25_supported_interiors(x, y, expected):
    result = assess_hydropeaking(CONTEXT, pulse(x, y), Flow(1), AREA)
    assert result.classification == expected
    assert result.context is CONTEXT
    assert "±2 native pixels" in result.source


@pytest.mark.parametrize("x,y", [(0.1, 2), (0.1, 2.01), (3.3, 2), (1, 8)])
def test_figure25_edges_precision_and_domain(x, y):
    assert assess_hydropeaking(CONTEXT, pulse(x, y), Flow(1), AREA).classification is None


def test_operating_estimates_and_zero_trough():
    operation = HydropeakingOperation(
        InstantaneousDischarge(3),
        InstantaneousDischarge(2),
        StageRate(Fraction(2)),
        StageRate(Fraction(1)),
        "concession",
    )
    result = estimate_hydropeaking(CONTEXT, operation, Flow(5), AREA)
    assert metrics(result)["peak"] == 5
    assert metrics(result)["trough"] == 2
    assert metrics(result)["daily_ratio_quantile"] == Fraction(5, 2)
    assert result.inputs[0] is operation
    zero = estimate_hydropeaking(CONTEXT, replace(operation, residual=InstantaneousDischarge(0)), Flow(5), AREA)
    assert zero.classification is None
    assert metrics(zero)["trough"] == 0


def test_missing_stage_does_not_erase_independent_metrics():
    result = assess_hydropeaking(CONTEXT, replace(pulse(1, 3), rise=None), Flow(1), AREA)
    assert result.classification is None
    assert metrics(result)["hydraulic_stress"] == 1
    assert assess_hydropeaking(CONTEXT, None, Flow(1), AREA).state is AssessmentState.UNDETERMINED
    assert assess_hydropeaking(CONTEXT, pulse(1, 3), Flow(0), AREA).classification is None


@pytest.fixture(scope="module")
def observations():
    weeks = tuple(date.fromisocalendar(y, w, 1) for y in range(2000, 2005) for w in range(2, 12))
    sampling = PulseSampling(
        weeks, ZoneInfo("UTC"), timedelta(hours=6), "selected low-flow weeks", "current operating regime"
    )
    data = {}
    for week in weeks:
        for offset in range(-1, 7 * 4):
            t = datetime.combine(week, datetime.min.time(), UTC) + timedelta(hours=6 * offset)
            # Two populations whose quantile ratio differs from ratio of quantiles.
            low = Fraction(1 if t.day % 2 else 10)
            flow = low * (4 if t.hour == 12 else 1)
            stage = SignedState(StateVariable.STAGE, Fraction(t.hour, 100), "m", "gauge datum")
            data[t] = PulseObservation(t, InstantaneousDischarge(flow), stage, "gauge")
    return sampling, tuple(data[t] for t in sorted(data))


def test_observation_daily_ratio_quantile_not_ratio_of_quantiles(observations):
    sampling, data = observations
    result = observe_hydropeaking(CONTEXT, sampling, data, Flow(40), AREA)
    values = metrics(result)
    assert values["daily_ratio_quantile"] == 4
    assert values["peak"] == 40 and values["trough"] == 1
    assert values["rise"] == Fraction(1, 60)
    assert values["fall"] == Fraction(1, 20)
    assert values["stage_correction"] == Fraction(65, 100)
    assert result.classification is None  # intensity 2.6 lies on the Figure25 class2/3 edge
    assert result.inputs[0] is sampling


def test_observation_gaps_and_stage_gaps(observations):
    sampling, data = observations
    result = observe_hydropeaking(CONTEXT, sampling, data[:4] + data[5:], Flow(40), AREA)
    assert result.classification is None
    stage_missing = tuple(replace(o, stage=None) for o in data)
    result = observe_hydropeaking(CONTEXT, sampling, stage_missing, Flow(40), AREA)
    assert metrics(result)["peak"] == 40
    assert result.classification is None


def test_invalid_daily_evidence_and_window(observations):
    sampling, data = observations
    with pytest.raises(ValueError, match="subdaily"):
        replace(sampling, cadence=timedelta(days=1))
    with pytest.raises(ValueError, match="ten calendar weeks"):
        replace(sampling, week_starts=sampling.week_starts[:-1])
    with pytest.raises(TypeError, match="interval mean"):
        replace(data[0], discharge=Flow(2))
    with pytest.raises(ValueError, match="duplicate"):
        observe_hydropeaking(CONTEXT, sampling, data + (data[0],), Flow(40), AREA)


@pytest.mark.parametrize(
    "stress,frequency,expected",
    [
        (0.2, 1, 1),
        (1, 10, 2),
        (1, 20, 3),
        (1, 40, 4),
        (2, 50, 5),
        (10, 0.2, 1),
        (10, 0.6, 2),
        (10, 1.5, 3),
        (10, 3, 4),
        (10, 20, 5),
        (60, 1, 5),
    ],
)
def test_figure27_supported_interiors(stress, frequency, expected):
    pulse = FlushingMetrics(
        InstantaneousDischarge(stress),
        Fraction(str(frequency)),
        StageRate(Fraction(2)),
        FlushingTiming.MEAN_FLOW,
        "operating record",
    )
    assert assess_flushing(CONTEXT, (pulse,), Flow(1)).classification == expected


def test_figure27_below_plot_and_review_at60():
    pulse = FlushingMetrics(
        InstantaneousDischarge(1), Fraction(1, 20), StageRate(Fraction(2)), FlushingTiming.MEAN_FLOW, "operating"
    )
    assert assess_flushing(CONTEXT, (pulse,), Flow(1)).classification is None
    pulse = replace(pulse, events_per_year=60)
    result = assess_flushing(CONTEXT, (pulse,), Flow(1))
    assert result.classification is None and any("review" in r for r in result.reasons)
    review = HydropeakingReview(HydropeakingApplicability.RETAIN_FLUSHING, "site judgement")
    result = assess_flushing(CONTEXT, (pulse,), Flow(1), review)
    assert review in result.inputs
    assert any("supplied applicability" in r for r in result.reasons)
    assert any("graphical domain" in r for r in result.reasons)


@pytest.mark.parametrize(
    "timing,expected",
    [
        (FlushingTiming.HIGH_FLOW, Fraction(3, 4)),
        (FlushingTiming.MEAN_FLOW, Fraction(1)),
        (FlushingTiming.LOW_FLOW, Fraction(3, 2)),
    ],
)
def test_flushing_timing_and_rise_interpolation(timing, expected):
    pulse = FlushingMetrics(InstantaneousDischarge(10), Fraction(1), StageRate(Fraction(3, 2)), timing, "record")
    values = metrics(assess_flushing(CONTEXT, (pulse,), Flow(10)))
    assert values["type_0.stage_correction"] == Fraction(7, 8)
    assert values["type_0.timing_correction"] == expected
    assert values["type_0.hydraulic_stress"] == Fraction(7, 8) * expected


def test_worst_flushing_combination_not_average():
    small = FlushingMetrics(
        InstantaneousDischarge(0.2), Fraction(1), StageRate(Fraction(2)), FlushingTiming.MEAN_FLOW, "small"
    )
    large = FlushingMetrics(
        InstantaneousDischarge(10), Fraction(3), StageRate(Fraction(2)), FlushingTiming.MEAN_FLOW, "large"
    )
    result = assess_flushing(CONTEXT, (small, large), Flow(1))
    assert result.classification == 4
    assert len(result.metrics) == 10
    unknown = replace(small, rise=None)
    assert assess_flushing(CONTEXT, (unknown, large), Flow(1)).classification is None
    bad = replace(large, events_per_year=20)
    result = assess_flushing(CONTEXT, (unknown, bad), Flow(1))
    assert result.classification == 5 and result.coverage is Completeness.INCOMPLETE


def test_flushing_observation_and_operating_estimate():
    start = datetime(2001, 1, 1, tzinfo=UTC)

    def observation(minutes, q, stage):
        return PulseObservation(
            start + timedelta(minutes=minutes),
            InstantaneousDischarge(q),
            SignedState(StateVariable.STAGE, stage, "m", "datum"),
            "event gauge",
        )

    data = (observation(0, 2, 0), observation(10, 12, 0.1), observation(20, 22, 0.5))
    result = observe_flushing(CONTEXT, data, Fraction(1), FlushingTiming.MEAN_FLOW, Flow(10), "typical event")
    assert metrics(result)["type_0.excess"] == 20
    assert metrics(result)["type_0.stage_correction"] == Fraction(3, 2)
    operation = FlushingOperation(
        InstantaneousDischarge(22),
        InstantaneousDischarge(2),
        data[0].stage,
        data[-1].stage,
        timedelta(minutes=20),
        Fraction(1),
        FlushingTiming.MEAN_FLOW,
        "concession",
    )
    result = estimate_flushing(CONTEXT, (operation,), Flow(10))
    assert metrics(result)["type_0.stage_correction"] == Fraction(9, 8)
    assert result.inputs[0] == (operation,)
    with pytest.raises(ValueError, match="ordered"):
        observe_flushing(CONTEXT, data[::-1], Fraction(1), FlushingTiming.MEAN_FLOW, Flow(10), "event")


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_rates(value):
    with pytest.raises(ValueError):
        StageRate(value)


def test_invalid_types_and_units():
    with pytest.raises(ValueError):
        catchment_correction(Area(0))
    with pytest.raises(ValueError):
        InstantaneousDischarge(2, "m3/day")
    with pytest.raises(TypeError):
        HydropeakingMetrics(Flow(1), InstantaneousDischarge(1), Fraction(1), None, None, "source")  # ty: ignore[invalid-argument-type]


def test_high_frequency_review_does_not_erase_computable_stress():
    pulse = FlushingMetrics(
        InstantaneousDischarge(10), Fraction(60), StageRate(Fraction(2)), FlushingTiming.MEAN_FLOW, "record"
    )
    result = assess_flushing(CONTEXT, (pulse,), Flow(10))
    assert metrics(result)["type_0.hydraulic_stress"] == 1
    assert result.classification is None


def test_observation_successful_interior(observations):
    sampling, data = observations
    result = observe_hydropeaking(CONTEXT, sampling, data, Flow(80), AREA)
    assert result.classification == 2


def test_figure25_dark_grid_pixels_do_not_create_false_class_edge():
    result = assess_hydropeaking(CONTEXT, pulse(1, 3.52), Flow(1), AREA)
    assert result.classification == 3


def test_residual_sum_and_intermediate_reference_estimate():
    from fishy.flow_pulses import estimate_hydropeaking_from_residuals

    result = estimate_hydropeaking_from_residuals(
        CONTEXT,
        InstantaneousDischarge(3),
        (Flow(1), Flow(0.5)),
        Flow(0.5),
        StageRate(Fraction(2)),
        StageRate(Fraction(1)),
        Flow(5),
        AREA,
        "concessions plus reference",
    )
    assert metrics(result)["trough"] == 2
    assert metrics(result)["peak"] == 5
    assert result.inputs[0] == (Flow(1), Flow(0.5))


def test_flushing_frequency_counts_threshold_equality_not_lower_events():
    from fishy.flow_pulses import FlushingAnnualEvents, assess_flushing_events

    years = (
        FlushingAnnualEvents(2001, tuple(InstantaneousDischarge(q) for q in (1, 2, 3)), "register", "complete"),
        FlushingAnnualEvents(2002, (InstantaneousDischarge(2),), "register", "complete"),
    )
    result = assess_flushing_events(
        CONTEXT,
        years,
        InstantaneousDischarge(2),
        StageRate(Fraction(2)),
        FlushingTiming.MEAN_FLOW,
        Flow(10),
        "selected threshold",
    )
    assert metrics(result)["type_0.frequency"] == Fraction(3, 2)
    assert result.classification == 1
    assert result.inputs[0] is years
    with pytest.raises(ValueError, match="duplicate"):
        assess_flushing_events(CONTEXT, (years[0], years[0]), InstantaneousDischarge(2), None, None, Flow(1), "record")


def test_figure25_exact_right_endpoint_does_not_use_last_interior_sample():
    # Original right-edge red/orange boundary ~2.18, not ~2.24 at last interior sample.
    result = assess_hydropeaking(CONTEXT, pulse(3.25, 2.2), Flow(1), AREA)
    assert result.classification is None


def test_hydropeaking_warmup_discharge_and_stage_intervals(observations):
    sampling, data = observations
    start = datetime.combine(sampling.week_starts[0], datetime.min.time(), UTC)
    context = replace(
        CONTEXT, provenance=replace(PROVENANCE, excluded_warmup=(Interval(start, start + timedelta(hours=1)),))
    )
    result = observe_hydropeaking(context, sampling, data, Flow(80), AREA)
    assert result.classification is None
    assert any("warmup" in reason for reason in result.reasons)
    # A warmup wholly between sampled instantaneous times still affects the stage transition.
    context = replace(
        CONTEXT,
        provenance=replace(
            PROVENANCE, excluded_warmup=(Interval(start + timedelta(hours=1), start + timedelta(hours=2)),)
        ),
    )
    result = observe_hydropeaking(context, sampling, data, Flow(80), AREA)
    assert result.classification is None
    assert metrics(result)["peak"] == 40


def test_flushing_observation_warmup_interval_is_not_assessed():
    start = datetime(2001, 1, 1, tzinfo=UTC)
    stage = SignedState(StateVariable.STAGE, 0, "m", "datum")
    data = (
        PulseObservation(start, InstantaneousDischarge(1), stage, "gauge"),
        PulseObservation(start + timedelta(minutes=10), InstantaneousDischarge(2), stage, "gauge"),
    )
    context = replace(
        CONTEXT,
        provenance=replace(
            PROVENANCE, excluded_warmup=(Interval(start + timedelta(minutes=1), start + timedelta(minutes=2)),)
        ),
    )
    result = observe_flushing(context, data, Fraction(1), FlushingTiming.MEAN_FLOW, Flow(2), "typical")
    assert result.classification is None
    assert any("warmup" in reason for reason in result.reasons)


def test_observation_presence_preserves_unsupported_numbers(observations):
    from fishy.flows import Presence

    sampling, data = observations
    assert PulseObservation(data[0].time, None, data[0].stage, data[0].source).presence is Presence.MISSING
    unsupported = replace(data[10], presence=Presence.UNSUPPORTED)
    result = observe_hydropeaking(CONTEXT, sampling, data[:10] + (unsupported,) + data[11:], Flow(80), AREA)
    assert result.classification is None
    assert any("unsupported" in reason for reason in result.reasons)
    outside = PulseObservation(data[0].time, None, None, "outside record", Presence.OUTSIDE_HORIZON)
    assert outside.presence is Presence.OUTSIDE_HORIZON


def test_flushing_annual_catalogue_rejects_outside_window_and_mixed_types():
    from fishy.flow_pulses import FlushingAnnualEvents, assess_flushing_events

    outside = (FlushingAnnualEvents(1990, (InstantaneousDischarge(2),), "register", "complete"),)
    with pytest.raises(ValueError, match="outside"):
        assess_flushing_events(CONTEXT, outside, InstantaneousDischarge(2), None, None, Flow(2), "source")
    records = (
        FlushingAnnualEvents(2001, (InstantaneousDischarge(2),), "register", "complete", event_type="sediment"),
        FlushingAnnualEvents(2002, (InstantaneousDischarge(2),), "register", "complete", event_type="emptying"),
    )
    with pytest.raises(ValueError, match="type"):
        assess_flushing_events(CONTEXT, records, InstantaneousDischarge(2), None, None, Flow(2), "source")
