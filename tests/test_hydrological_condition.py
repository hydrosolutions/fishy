"""Figure 33 aggregation and attribution contracts."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from fishy.evidence import Completeness, CorrectionState, ProductionMethod, Provenance
from fishy.hydrological_condition import (
    AssessmentContext,
    AssessmentState,
    HydrologyClass,
    Indicator,
    IndicatorResult,
    Metric,
    assess_hydrology,
    overall_class,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def context(name="site"):
    return AssessmentContext(
        Location(Reach(name, "1", WaterBody("river", "1")), CalculationSection(name, "1"), "mapping-1"),
        Interval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2010, 1, 1, tzinfo=UTC)),
        Provenance(
            "synthetic",
            "scenario",
            "reference-member",
            "test",
            "data-1",
            "config-1",
            ProductionMethod.ILLUSTRATIVE,
            CorrectionState.ORIGINAL,
        ),
    )


def result(indicator, cls, ctx=None, *, state=AssessmentState.ASSESSED):
    return IndicatorResult(
        indicator,
        ctx or context(),
        state,
        HydrologyClass(cls) if cls is not None else None,
        (),
        "synthetic supplied point assessment",
        ("attributable test",),
    )


@pytest.mark.parametrize(
    "worst,points,expected",
    [
        (1, 9, 1),
        (2, 10, 1),
        (2, 11, 2),
        (3, 12, 1),
        (3, 13, 2),
        (3, 14, 2),
        (3, 15, 3),
        (4, 16, 2),
        (4, 17, 3),
        (4, 22, 3),
        (4, 23, 4),
        (5, 24, 3),
        (5, 25, 4),
        (5, 30, 4),
        (5, 31, 5),
    ],
)
def test_every_figure33_transition(worst, points, expected):
    assert overall_class(HydrologyClass(worst), points) == expected


def test_26_points_and_hydropeaking_override():
    ctx = context()
    values = (5, 3, 3, 1, 1, 1, 1, 1, 1)
    rs = tuple(result(i, c, ctx) for i, c in zip(Indicator, values, strict=True))
    output = assess_hydrology(ctx, rs)
    assert (output.points, output.classification, output.completeness) == (26, 4, Completeness.COMPLETE)
    changed = tuple(
        replace(r, classification=HydrologyClass.BAD)
        if r.indicator is Indicator.HYDROPEAKING
        else replace(r, classification=HydrologyClass.HIGH)
        for r in rs
    )
    output = assess_hydrology(ctx, changed)
    assert output.points == 20
    assert output.classification == 5
    assert "overrides" in output.reasons[0]


def test_missing_and_two_known_bad_exception():
    ctx = context()
    assert assess_hydrology(ctx, ()).classification is None
    one = (result(Indicator.MEAN_FLOW, 5, ctx),)
    assert assess_hydrology(ctx, one).classification is None
    output = assess_hydrology(ctx, (*one, result(Indicator.FLOOD_FREQUENCY, 5, ctx)))
    assert output.classification == 5
    assert output.points == 24
    assert output.completeness is Completeness.INCOMPLETE
    assert len(output.indicators) == 9
    assert len([r for r in output.indicators if r.classification is None]) == 7


def test_screened_is_not_missing_and_partial_spatial_coverage_survives():
    ctx = context()
    rs = tuple(result(i, 1, ctx, state=AssessmentState.SCREENED) for i in Indicator)
    output = assess_hydrology(ctx, rs)
    assert output.classification == 1
    assert output.completeness is Completeness.COMPLETE
    partial = (replace(rs[0], coverage=Completeness.INCOMPLETE), *rs[1:])
    output = assess_hydrology(ctx, partial)
    assert output.classification == 1
    assert output.completeness is Completeness.INCOMPLETE
    missing = (replace(rs[0], state=AssessmentState.UNDETERMINED, classification=None), *rs[1:])
    assert assess_hydrology(ctx, missing).classification is None


def test_context_mismatch_duplicate_invalid_state_and_nonfinite_refused():
    ctx = context()
    with pytest.raises(ValueError, match="context differs"):
        assess_hydrology(ctx, (result(Indicator.MEAN_FLOW, 1, context("elsewhere")),))
    r = result(Indicator.MEAN_FLOW, 1, ctx)
    with pytest.raises(ValueError, match="duplicate"):
        assess_hydrology(ctx, (r, r))
    with pytest.raises(ValueError, match="only class 1"):
        replace(r, state=AssessmentState.SCREENED, classification=HydrologyClass.GOOD)
    with pytest.raises(ValueError, match="finite"):
        Metric("invalid", float("nan"), "1")


@pytest.mark.parametrize("worst,points", [(2, 9), (3, 11), (4, 15), (5, 19), (2, 19), (3, 37), (4, 73), (5, 109)])
def test_matrix_refuses_impossible_nine_indicator_point_totals(worst, points):
    with pytest.raises(ValueError, match="incompatible"):
        overall_class(HydrologyClass(worst), points)
