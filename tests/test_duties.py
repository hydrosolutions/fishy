from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from fishy.duties import (
    Availability,
    ComparisonKind,
    Deliverability,
    Delivery,
    DutyApplicability,
    Floor,
    Obligation,
    Requirement,
    SuppliedDuty,
    assess_duty,
    assess_feasibility,
)
from fishy.evidence import Check, CheckFinding, Completeness, CorrectionState, ProductionMethod, Provenance
from fishy.flows import Coverage, FlowSample, Presence, aggregate_flow, daily_discharge
from fishy.quantities import Flow, FlowBounds, SignedState, StateVariable, Volume, interval_volume, mean_discharge
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def location():
    return Location(
        Reach("reach", "geometry-v1", WaterBody("river", "v1")), CalculationSection("section", "v1"), "map-v1"
    )


def provenance(method=ProductionMethod.OBSERVED):
    return Provenance(
        "gauge", "observed-2020", None, "instrument-v1", "data-v1", "config-v1", method, CorrectionState.ORIGINAL
    )


def samples(values, *, method=ProductionMethod.OBSERVED):
    start = datetime(2020, 2, 28, tzinfo=UTC)
    return tuple(
        FlowSample(
            location(),
            Interval(start + timedelta(days=i), start + timedelta(days=i + 1)),
            Flow(value),
            Presence.PRESENT,
            provenance(method),
        )
        for i, value in enumerate(values)
    )


def duty(values=(2, 3), **kwargs):
    return SuppliedDuty(
        "issued-schedule",
        "v1",
        "supplied independent provision",
        DutyApplicability.APPLICABLE,
        tuple(Obligation(s, "v1") for s in samples(values, method=ProductionMethod.IMPORTED)),
        "documented instrument search",
        **kwargs,
    )


def test_supplied_schedule_shortfall_does_not_cancel_and_versions_stay_immutable():
    prescribed = duty()
    delivered = tuple(Delivery(s, "delivery-v1") for s in samples((1.5, 3.5)))
    result = assess_duty(prescribed, delivered)
    assert tuple(row.shortfall for row in result.intervals) == (Flow(Fraction(1, 2)), Flow(0))
    assert result.known_shortfall_volume == Volume(43200)
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.COMPLETE
    assert result.interpretation is ComparisonKind.OBSERVATION
    assert all(row.uncertainty_finding.finding is CheckFinding.UNKNOWN for row in result.intervals)
    scenario = assess_duty(
        prescribed, tuple(Delivery(s, "v2") for s in samples((2, 3), method=ProductionMethod.SIMULATED))
    )
    assert scenario.summary.finding is CheckFinding.PASS
    assert scenario.interpretation is ComparisonKind.PREDICTION
    assert prescribed.schedule[0].sample.value == Flow(2)
    with pytest.raises(FrozenInstanceError):
        prescribed.version = "revised"


@pytest.mark.parametrize(
    "presence", [Presence.MISSING, Presence.ABSENT, Presence.OUTSIDE_HORIZON, Presence.UNSUPPORTED]
)
def test_missing_unknown_and_unsupported_never_become_zero_or_cancel_known_failure(presence):
    a, b = samples((1.5, 3.5))
    unknown = replace(b, value=None, presence=presence, reasons=("attributable gap",))
    result = assess_duty(duty(), (Delivery(a, "v1"), Delivery(unknown, "v1")))
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert result.known_shortfall_volume == Volume(43200)
    assert result.intervals[1].shortfall is None
    assert result.intervals[1].delivery is not None
    assert result.intervals[1].delivery.sample.presence is presence


def test_zero_is_present_failure_and_omissions_are_indeterminate():
    result = assess_duty(duty((2,)), (Delivery(samples((0,))[0], "v1"),))
    assert result.known_shortfall_volume == Volume(172800)
    assert result.summary.finding is CheckFinding.FAIL
    assert assess_duty(duty(), ()).summary.finding is CheckFinding.UNKNOWN
    omitted = assess_duty(duty(), (Delivery(samples((2,))[0], "v1"),))
    assert omitted.summary.completeness is Completeness.INCOMPLETE
    assert omitted.summary.finding is CheckFinding.UNKNOWN


def test_other_required_components_cannot_disappear():
    prescribed = duty((2,), required_components=("discharge", "velocity", "within-day"))
    result = assess_duty(
        prescribed, (Delivery(samples((2,))[0], "v1"),), component_checks=(Check("velocity", CheckFinding.FAIL),)
    )
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    with pytest.raises(ValueError, match="undeclared"):
        assess_duty(prescribed, (), component_checks=(Check("invented", CheckFinding.PASS),))


def test_quantity_roles_are_distinct_and_no_foreign_duty_cap_is_applied():
    sample = samples((10,))[0]
    requirement = Requirement(sample, "v1")
    floor = Floor(replace(sample, value=Flow(2)), "v1")
    available = Availability(replace(sample, value=Flow(8)), "v1")
    deliverable = Deliverability(replace(sample, value=Flow(6)), "v1")
    issued = Obligation(replace(sample, value=Flow(6)), "v1")
    delivered = Delivery(replace(sample, value=Flow(5)), "v1")
    # The later Uzbek assembly owns selecting/issuing 6 from 10/6. Here 6 is supplied.
    assert requirement.sample.value is not None
    assert issued.sample.value is not None
    assert delivered.sample.value is not None
    assert requirement.sample.value.value - issued.sample.value.value == 4
    assert issued.sample.value.value - delivered.sample.value.value == 1
    assert floor.sample.value == Flow(2) and available.sample.value == Flow(8)
    infeasible = assess_feasibility(duty((10,)), (deliverable,))
    assert infeasible.intervals[0].shortfall == Flow(4)
    assert infeasible.duty.schedule[0].sample.value == Flow(10)
    assert infeasible.interpretation is ComparisonKind.FEASIBILITY
    with pytest.raises(TypeError, match="actual Delivery"):
        assess_duty(duty((10,)), (deliverable,))  # ty: ignore[invalid-argument-type] -- runtime role refusal


def test_uncertainty_is_separate_and_daily_means_do_not_certify_within_day():
    sample = samples((2,))[0]
    bounds = FlowBounds(Flow("1.9"), Flow("2.1"), "measurement interval", "rating-v2", "shared rating errors")
    result = assess_duty(
        duty((2,), required_components=("discharge", "within-day")),
        (Delivery(replace(sample, uncertainty=bounds), "v1"),),
    )
    assert result.intervals[0].numerical.finding is CheckFinding.PASS
    assert result.intervals[0].uncertainty_finding.finding is CheckFinding.UNKNOWN
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.summary.completeness is Completeness.INCOMPLETE


@pytest.mark.parametrize(
    "state", [DutyApplicability.INAPPLICABLE, DutyApplicability.UNRESOLVED, DutyApplicability.NONE_LOCATED]
)
def test_duty_inventory_states_do_not_mean_no_duty_or_compliance(state):
    inventory = replace(duty(), applicability=state, schedule=(), reasons=("documented follow-up and search date",))
    result = assess_duty(inventory, ())
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.duty.applicability is state


def test_exact_intervals_leap_partial_and_volume_preserving_aggregation():
    values = samples((1, 3))
    assert values[1].interval.start.day == 29
    merged = aggregate_flow(values)
    assert merged.value == Flow(2)
    assert interval_volume(merged.value, merged.interval) == Volume(345600)
    assert "resolution" in " ".join(merged.reasons)
    assert merged.uncertainty is None
    expected = pl.DataFrame(
        {"date": [datetime(2020, 2, 28).date(), datetime(2020, 2, 29).date()], "discharge_m3_s": [1.0, 3.0]}
    )
    assert_frame_equal(daily_discharge(values), expected)
    hour = Interval(datetime(2020, 2, 29, tzinfo=UTC), datetime(2020, 2, 29, 1, tzinfo=UTC))
    assert mean_discharge(Volume(3600), hour) == Flow(1)
    partial = replace(values[0], coverage=Coverage.PARTIAL, reasons=("half-day observation coverage",))
    assert assess_duty(duty((2,)), (Delivery(partial, "v1"),)).summary.finding is CheckFinding.UNKNOWN
    with pytest.raises(ValueError, match="unavailable or partial"):
        daily_discharge((partial,))
    with pytest.raises(ValueError, match="whole UTC"):
        daily_discharge((replace(values[0], interval=hour),))


def test_import_refuses_invalid_domains_units_nonfinite_duplicates_and_mappings():
    for bad in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            Flow(bad)
        with pytest.raises(ValueError):
            Volume(bad)
    with pytest.raises(ValueError):
        Flow(1, "mm/day")
    with pytest.raises(ValueError):
        Volume(1, "kg")
    with pytest.raises(ValueError):
        Interval(datetime(2020, 1, 1), datetime(2020, 1, 2))
    sample = samples((1,))[0]
    with pytest.raises(ValueError, match="duplicate or overlapping"):
        daily_discharge((sample, sample))
    with pytest.raises(ValueError, match="incompatible physical"):
        assess_duty(
            duty((2,)), (Delivery(replace(sample, location=replace(location(), mapping_version="different")), "v1"),)
        )
    with pytest.raises(ValueError, match="exact duty interval"):
        assess_duty(
            duty((2,)),
            (
                Delivery(
                    replace(sample, interval=Interval(sample.interval.start, sample.interval.end + timedelta(hours=1))),
                    "v1",
                ),
            ),
        )
    assert SignedState(StateVariable.STAGE, "-1.25", "m", "datum-relative").value == Fraction(-5, 4)
    assert SignedState(StateVariable.VELOCITY, "-0.2", "m/s", "downstream-positive").value == Fraction(-1, 5)
    assert Flow(1000, "l/s") == Flow(1)
    assert Volume(1000, "l") == Volume(1)


def test_excluded_warmup_cannot_enter_supported_assessment():
    sample = samples((3,))[0]
    excluded = replace(sample, provenance=replace(sample.provenance, excluded_warmup=(sample.interval,)))
    result = assess_duty(duty((2,)), (Delivery(excluded, "1"),))
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.intervals[0].shortfall is None


def test_missing_observation_correction_status_cannot_carry_present_value():
    sample = samples((3,))[0]
    with pytest.raises(ValueError, match="missing observation"):
        replace(sample, provenance=replace(sample.provenance, correction_state=CorrectionState.MISSING))


def test_heterogeneous_observation_corrections_and_source_history_remain_attributable():
    original, corrected = samples((1, 3))
    corrected = replace(
        corrected,
        provenance=replace(
            corrected.provenance,
            source="replacement gauge",
            data_version="corrected-v2",
            correction_state=CorrectionState.CORRECTED,
        ),
    )
    readings = (original, corrected)
    result = assess_duty(duty(), tuple(Delivery(s, "1") for s in readings))
    assert result.intervals[0].delivery is not None
    assert result.intervals[1].delivery is not None
    assert result.intervals[0].delivery.sample.provenance.correction_state is CorrectionState.ORIGINAL
    assert result.intervals[1].delivery.sample.provenance.correction_state is CorrectionState.CORRECTED
    assert result.intervals[1].delivery.sample.provenance.source == "replacement gauge"
    assert daily_discharge(readings).height == 2
    aggregate_provenance = replace(
        provenance(ProductionMethod.IMPORTED), source="documented weighted aggregation", data_version="aggregation-v1"
    )
    aggregate = aggregate_flow(readings, provenance=aggregate_provenance)
    assert aggregate.value == Flow(2)
    assert aggregate.components == readings
    assert aggregate.provenance == aggregate_provenance
    with pytest.raises(ValueError, match="aggregate provenance"):
        aggregate_flow(readings)
