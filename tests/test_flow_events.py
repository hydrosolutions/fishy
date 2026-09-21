"""HYDMOD-F event frequency source equations and attributed observation routes."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from fishy.evidence import CorrectionState, ProductionMethod, Provenance
from fishy.flow_events import (
    DrainageResponse,
    EventCause,
    EventFrequency,
    EventSupport,
    InstantaneousDischarge,
    InstantaneousRecord,
    InstantaneousSample,
    RainfallFrequency,
    StormwaterEvent,
    estimate_mhq_from_area,
    estimate_mhq_from_mean,
    flood_frequency,
    flood_frequency_from_record,
    observed_mhq,
    stormwater_events,
    stormwater_frequency,
    stormwater_rainfall,
)
from fishy.flows import FlowSample, Presence
from fishy.hydrological_condition import AssessmentContext, AssessmentState
from fishy.quantities import Area, Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


@pytest.fixture
def context():
    location = Location(Reach("r", "v1", WaterBody("w", "v1")), CalculationSection("s", "v1"), "m1")
    provenance = Provenance(
        "synthetic", "managed", "member", "v1", "d1", "c1", ProductionMethod.ILLUSTRATIVE, CorrectionState.ORIGINAL
    )
    return AssessmentContext(
        location, Interval(datetime(2020, 1, 1, tzinfo=UTC), datetime(2021, 1, 1, tzinfo=UTC)), provenance
    )


def record(context, values, support=EventSupport.COMPLETE):
    return InstantaneousRecord(
        context,
        tuple(
            InstantaneousSample(
                context.period.start + timedelta(days=day),
                InstantaneousDischarge(value),
                Presence.PRESENT,
                context,
                cause,
            )
            for day, value, cause in values
        ),
        support,
        "prepared subdaily crossing and trough catalogue; complete calendar year",
    )


@pytest.mark.parametrize(
    "regime,threshold",
    [(r, 2 if r in (1, 2, 3, 4, 5, 13) else 6 if r in (8, 9, 16) else Fraction(7, 2)) for r in range(1, 17)],
)
def test_flood_natural_regime_groups(context, regime, threshold):
    assert flood_frequency(context, EventFrequency(threshold, "import"), regime).classification == 1
    assert flood_frequency(context, EventFrequency(threshold - Fraction(1, 1000), "import"), regime).classification == 2


@pytest.mark.parametrize(
    "value,cls",
    [
        (0, 5),
        (Fraction(1, 3) - Fraction(1, 1000), 5),
        (Fraction(1, 3), 4),
        (Fraction(2, 3), 3),
        (1, 2),
        (2, 1),
        (100, 1),
    ],
)
def test_flood_boundaries(context, value, cls):
    assert flood_frequency(context, EventFrequency(value, "import"), 1).classification == cls


def test_missing_regime_only_affects_best_classes(context):
    assert flood_frequency(context, EventFrequency(Fraction(1, 2), "import"), None).classification == 4
    assert flood_frequency(context, EventFrequency(2, "import"), None).state is AssessmentState.UNDETERMINED
    assert flood_frequency(context, None, 1).state is AssessmentState.UNDETERMINED


def test_independent_crossings_drop_five_days_and_flushing_exception(context):
    n = EventCause.NATURAL
    values = [
        (0, 0, n),
        (1, 7, n),
        (2, 4, n),
        (7, 7, n),  # no half-threshold drop: same event
        (8, 3, n),
        (12, 7, n),  # only four days after qualifying drop: same event
        (13, 2, n),
        (18, 7, n),  # five days after the renewed drop: second independent event
        (19, 0, n),
        (24, 8, EventCause.FLUSHING),
        (25, 0, n),
        (30, 8, EventCause.ECOLOGICAL_FLOOD),
    ]
    result = flood_frequency_from_record(record(context, values), Flow(10), 1)
    assert result.classification == 1
    assert result.metrics[0].value == 3
    assert result.metrics[1].value == 6
    assert isinstance(result.inputs[0], InstantaneousRecord)
    assert result.inputs[0].samples[-1].cause is EventCause.ECOLOGICAL_FLOOD
    assert result.context is context


def test_strict_crossing_and_five_day_equality(context):
    n = EventCause.NATURAL
    result = flood_frequency_from_record(
        record(context, [(0, 0, n), (1, 6, n), (2, 7, n), (3, 3, n), (8, 7, n)]), Flow(10), 1
    )
    assert result.metrics[0].value == 2


def test_cross_year_separation_keeps_predecessor(context):
    context = replace(context, period=Interval(context.period.start, datetime(2022, 1, 1, tzinfo=UTC)))
    n = EventCause.NATURAL
    result = flood_frequency_from_record(
        record(context, [(0, 0, n), (364, 7, n), (365, 3, n), (366, 7, n)]), Flow(10), 1
    )
    assert result.metrics[0].value == Fraction(1, 2)


@pytest.mark.parametrize("support", [EventSupport.DAILY_ONLY, EventSupport.INCOMPLETE])
def test_daily_or_incomplete_cannot_certify_frequency(context, support):
    result = flood_frequency_from_record(record(context, [(0, 0, EventCause.NATURAL)], support), Flow(10), 1)
    assert result.state is AssessmentState.UNDETERMINED


def test_missing_and_partial_year_keep_undetermined(context):
    r = record(context, [(0, 0, EventCause.NATURAL)])
    missing = replace(r.samples[0], value=None, presence=Presence.OUTSIDE_HORIZON)
    assert flood_frequency_from_record(replace(r, samples=(missing,)), Flow(10), 1).classification is None
    partial = replace(context, period=Interval(context.period.start, datetime(2020, 6, 1, tzinfo=UTC)))
    assert (
        flood_frequency_from_record(record(partial, [(0, 0, EventCause.NATURAL)]), Flow(10), 1).classification is None
    )
    assert flood_frequency_from_record(r, None, 1).classification is None


def test_instantaneous_types_and_invalid_inputs(context):
    with pytest.raises(TypeError):
        InstantaneousSample(context.period.start, Flow(1), Presence.PRESENT, context)  # ty: ignore[invalid-argument-type]
    for value in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            InstantaneousDischarge(value)
        with pytest.raises(ValueError):
            EventFrequency(value, "test")
    assert InstantaneousDischarge(1000, "l/s").value == 1
    r = record(context, [(0, 0, EventCause.NATURAL)])
    with pytest.raises(ValueError, match="unique"):
        replace(r, samples=r.samples * 2)
    with pytest.raises(ValueError):
        flood_frequency(context, EventFrequency(2, "test"), 17)


@pytest.mark.parametrize(
    "regime,ratio,specific",
    list(
        zip(
            range(1, 17),
            [
                "5.5",
                "5.2",
                "4.7",
                "5.4",
                "5.6",
                "5.1",
                "8.7",
                "9.9",
                "10.2",
                "9.2",
                "7.3",
                "9.7",
                "7.3",
                "14.9",
                "11.4",
                "8.7",
            ],
            [291, 297, 259, 257, 253, 225, 456, 411, 272, 139, 161, 145, 348, 706, 418, 257],
            strict=True,
        )
    ),
)
def test_source_mhq_tables(context, regime, ratio, specific):
    assert estimate_mhq_from_mean(Flow(2), regime).flow.value == 2 * Fraction(ratio)
    assert estimate_mhq_from_area(Area(10, "km2"), regime).flow.value == Fraction(specific, 100)


def test_observed_mhq_complete_leap_year_and_missing_day(context):
    samples = tuple(
        FlowSample(
            context.location,
            Interval(context.period.start + timedelta(days=i), context.period.start + timedelta(days=i + 1)),
            Flow(20 if i == 59 else 2),
            Presence.PRESENT,
            context.provenance,
        )
        for i in range(366)
    )
    result = observed_mhq(samples)
    assert result.flow.value == 20
    assert result.inputs == samples
    with pytest.raises(ValueError, match="missing days"):
        observed_mhq(samples[:59] + samples[60:])
    with pytest.raises(ValueError, match="calendar years"):
        observed_mhq(samples[:-1])


@pytest.mark.parametrize(
    "value,cls", [(0, 1), (Fraction(199, 1000), 1), (Fraction(1, 5), 2), (2, 3), (4, 4), (8, 5), (100, 5)]
)
def test_stormwater_boundaries(context, value, cls):
    assert stormwater_frequency(context, EventFrequency(value, "import")).classification == cls


def test_stormwater_additional_drainage_events_not_natural_peaks(context):
    events = tuple(
        StormwaterEvent(
            str(i), context.period.start + timedelta(days=i), InstantaneousDischarge(q), "drainage catalogue"
        )
        for i, q in enumerate((4, 5, 1))
    )
    result = stormwater_events(context, events, Flow(2), Flow(10), EventSupport.COMPLETE)
    # Threshold 6: 2+4 is equal, only 2+5 exceeds. Natural river peaks are not operands.
    assert result.metrics[0].value == 1
    assert result.classification == 2
    assert result.inputs[0] == events
    with pytest.raises(ValueError, match="duplicate"):
        stormwater_events(context, events * 2, Flow(2), Flow(10), EventSupport.COMPLETE)
    assert stormwater_events(context, events, None, Flow(10), EventSupport.COMPLETE).classification is None
    assert stormwater_events(context, (), Flow(2), Flow(10), EventSupport.COMPLETE).classification == 1
    assert stormwater_events(context, (), Flow(2), Flow(10), EventSupport.INCOMPLETE).classification is None


def test_gep_inverse_rainfall_and_frequency(context):
    drainage = DrainageResponse(Area(2, "km2"), Fraction(1, 2), Fraction(3600), "site drainage")
    rain = RainfallFrequency(Fraction(4, 1000000), Fraction(3600), Fraction(5), "site IDF at concentration time")
    result = stormwater_rainfall(context, Flow(2), Flow(10), drainage, rain)
    assert result.metrics[0].value == Fraction(4, 1000000)
    assert result.metrics[1].value == Fraction(1, 5)
    assert result.classification == 2
    assert result.inputs[-1] is rain
    assert stormwater_rainfall(context, Flow(2), Flow(10), drainage, None).classification is None
    assert (
        stormwater_rainfall(
            context, Flow(2), Flow(10), drainage, replace(rain, duration_seconds=Fraction(60))
        ).classification
        is None
    )
    assert stormwater_rainfall(context, Flow(7), Flow(10), drainage, rain).classification is None


def test_premature_recrossing_restarts_required_drop_wait(context):
    n = EventCause.NATURAL
    values = [(0, 0, n), (1, 7, n), (2, 3, n), (6, 7, n), (7, 3, n), (8, 7, n), (9, 3, n), (14, 7, n)]
    result = flood_frequency_from_record(record(context, values), Flow(10), 1)
    # No crossing until five days after the drop: recrossing after four days
    # interrupts that separation; an older drop cannot certify a later event.
    assert result.metrics[0].value == 2


def test_observed_mhq_refuses_warmup_exclusions(context):
    excluded = Interval(context.period.start, context.period.start + timedelta(days=1))
    provenance = replace(context.provenance, excluded_warmup=(excluded,))
    samples = tuple(
        FlowSample(
            context.location,
            Interval(context.period.start + timedelta(days=i), context.period.start + timedelta(days=i + 1)),
            Flow(2),
            Presence.PRESENT,
            provenance,
        )
        for i in range(366)
    )
    with pytest.raises(ValueError, match="complete daily means"):
        observed_mhq(samples)


@pytest.mark.parametrize("scope", ["record", "sample"])
def test_instantaneous_warmup_cannot_certify_event_frequency(context, scope):
    n = EventCause.NATURAL
    r = record(context, [(0, 0, n), (1, 7, n)])
    excluded = Interval(context.period.start, context.period.start + timedelta(days=1))
    affected = replace(context, provenance=replace(context.provenance, excluded_warmup=(excluded,)))
    if scope == "record":
        r = replace(r, context=affected)
    else:
        r = replace(r, samples=(replace(r.samples[0], context=affected), r.samples[1]))
    assert flood_frequency_from_record(r, Flow(10), 1).state is AssessmentState.UNDETERMINED


def test_instantaneous_reference_kind_mismatch_is_invalid(context):
    from fishy.evidence import ReferenceKind

    r = record(context, [(0, 0, EventCause.NATURAL)])
    different = replace(
        context, provenance=replace(context.provenance, reference_kind=ReferenceKind.FUTURE_CLIMATE_STRESS)
    )
    with pytest.raises(ValueError, match="reference"):
        replace(r, samples=(replace(r.samples[0], context=different),))


def test_missing_correction_cannot_carry_instantaneous_value(context):
    missing = replace(context, provenance=replace(context.provenance, correction_state=CorrectionState.MISSING))
    with pytest.raises(ValueError, match="missing"):
        InstantaneousSample(context.period.start, InstantaneousDischarge(0), Presence.PRESENT, missing)


@pytest.mark.parametrize("route", ["flood", "stormwater", "rainfall"])
def test_reference_mhq_route_preserved_in_indicator_inputs(context, route):
    reference = estimate_mhq_from_mean(Flow(2), 3)
    if route == "flood":
        result = flood_frequency_from_record(record(context, [(0, 0, EventCause.NATURAL)]), reference, 3)
        assert result.classification == 5
    elif route == "stormwater":
        result = stormwater_events(context, (), Flow(2), reference, EventSupport.COMPLETE)
        assert result.classification == 1
    else:
        drainage = DrainageResponse(Area(2, "km2"), Fraction(1, 2), Fraction(3600), "site")
        intensity = (reference.flow.value * Fraction(3, 5) - 2) / 1000000
        rain = RainfallFrequency(intensity, Fraction(3600), Fraction(5), "IDF")
        result = stormwater_rainfall(context, Flow(2), reference, drainage, rain)
        assert result.classification == 2
    assert reference in result.inputs
    assert reference.source.endswith("Table 4")
    assert reference.inputs == (Flow(2), 3)


def test_stormwater_warmup_cannot_certify_absence(context):
    affected = replace(context, provenance=replace(context.provenance, excluded_warmup=(context.period,)))
    result = stormwater_events(affected, (), Flow(2), Flow(10), EventSupport.COMPLETE)
    assert result.state is AssessmentState.UNDETERMINED


def test_stormwater_support_requires_enum(context):
    with pytest.raises(TypeError, match="EventSupport"):
        stormwater_events(context, (), Flow(2), Flow(10), "complete")  # ty: ignore[invalid-argument-type]


def test_invalid_regime_not_hidden_by_missing_event_evidence(context):
    r = record(context, [], EventSupport.INCOMPLETE)
    with pytest.raises(ValueError, match="regime"):
        flood_frequency_from_record(r, None, 17)


@pytest.mark.parametrize("route", ["mean_estimate", "stormwater", "rainfall"])
def test_instantaneous_flow_cannot_substitute_mean_operand(context, route):
    q = InstantaneousDischarge(2)
    with pytest.raises(TypeError, match="Flow"):
        if route == "mean_estimate":
            estimate_mhq_from_mean(q, 3)  # ty: ignore[invalid-argument-type]
        elif route == "stormwater":
            stormwater_events(context, (), q, Flow(10), EventSupport.COMPLETE)  # ty: ignore[invalid-argument-type]
        else:
            drainage = DrainageResponse(Area(2, "km2"), Fraction(1, 2), Fraction(3600), "site")
            stormwater_rainfall(context, q, Flow(10), drainage, None)  # ty: ignore[invalid-argument-type]


def test_unaffected_warmup_period_does_not_block_events(context):
    previous = Interval(datetime(2019, 1, 1, tzinfo=UTC), context.period.start)
    context = replace(context, provenance=replace(context.provenance, excluded_warmup=(previous,)))
    result = flood_frequency_from_record(record(context, [(0, 0, EventCause.NATURAL)]), Flow(10), 1)
    assert result.classification == 5


@pytest.mark.parametrize("route", ["flood", "stormwater"])
@pytest.mark.parametrize("support", ["missing", "warmup", "previous_warmup"])
def test_imported_event_frequency_honors_context_support_and_retains_inputs(context, route, support):
    if support == "missing":
        provenance = replace(context.provenance, correction_state=CorrectionState.MISSING)
    elif support == "warmup":
        provenance = replace(context.provenance, excluded_warmup=(context.period,))
    else:
        previous = Interval(datetime(2019, 1, 1, tzinfo=UTC), context.period.start)
        provenance = replace(context.provenance, excluded_warmup=(previous,))
    context = replace(context, provenance=provenance)
    frequency = EventFrequency(2, "prepared imported annual event estimate")
    result = flood_frequency(context, frequency, 1) if route == "flood" else stormwater_frequency(context, frequency)
    assert result.context is context
    assert frequency in result.inputs
    assert result.metrics[0].value == 2
    if support == "previous_warmup":
        assert result.state is AssessmentState.ASSESSED
        assert result.classification is not None
    else:
        assert result.state is AssessmentState.UNDETERMINED
        assert result.classification is None
        assert result.reasons
