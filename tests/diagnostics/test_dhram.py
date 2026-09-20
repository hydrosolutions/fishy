"""Independent checks against Black2005 Tables3–6."""

import math

import pytest

from fishy.diagnostics.dhram import (
    THRESHOLDS,
    HydrologicalChanges,
    SupplementaryEvidence,
    SupplementaryFinding,
    classify_dhram,
)


def evidence(subdaily=SupplementaryFinding.EXCLUDED, cessation=SupplementaryFinding.EXCLUDED):
    return SupplementaryEvidence(subdaily, cessation, "synthetic known operational evidence")


def changes(values):
    return HydrologicalChanges(
        tuple(values),
        tuple("not supplied" if v is None else "" for v in values),
        "Black2005 supplied summary indicators",
    )


def test_megget_source_table5():
    result = classify_dhram(changes([21.7, 39.8, 31.0, 124.0, 30.9, 17.6, 46.3, 22.7, 34.2, 41.4]), evidence())
    assert result.impact_points == (1, 1, 0, 2, 2, 0, 1, 0, 0, 0)
    assert result.points_lower == result.points_upper == 7
    assert result.classification == 3


def test_allt_source_table6():
    result = classify_dhram(
        changes([81.2, 224.2, 69.8, 147.6, 20.6, 48.9, 73.5, 55.0, 292.3, 73.9]),
        evidence(cessation=SupplementaryFinding.CONFIRMED),
    )
    assert result.impact_points == (3, 3, 1, 2, 1, 1, 2, 1, 3, 1)
    assert result.points_lower == 18
    assert result.classification == 5


@pytest.mark.parametrize("index", range(10))
@pytest.mark.parametrize("level", range(3))
def test_every_threshold_equality_is_not_exceedance(index, level):
    values = [0.0] * 10
    values[index] = THRESHOLDS[index][level]
    assert classify_dhram(changes(values), evidence()).impact_points[index] == level
    values[index] = math.nextafter(values[index], math.inf)
    assert classify_dhram(changes(values), evidence()).impact_points[index] == level + 1


@pytest.mark.parametrize(
    "points,expected", [(0, 1), (1, 2), (4, 2), (5, 3), (10, 3), (11, 4), (20, 4), (21, 5), (30, 5)]
)
def test_every_class_boundary(points, expected):
    values = []
    for limits in THRESHOLDS:
        n = min(points, 3)
        values.append(0.0 if n == 0 else math.nextafter(limits[n - 1], math.inf))
        points -= n
    assert classify_dhram(changes(values), evidence()).classification == expected


def test_unknown_is_not_false_and_two_confirmed_adjustments():
    result = classify_dhram(changes([0.0] * 10), evidence(SupplementaryFinding.UNKNOWN, SupplementaryFinding.UNKNOWN))
    assert (result.class_lower, result.class_upper, result.classification) == (1, 3, None)
    result = classify_dhram(
        changes([0.0] * 10), evidence(SupplementaryFinding.CONFIRMED, SupplementaryFinding.CONFIRMED)
    )
    assert result.classification == 3


def test_missing_group_never_disappears_into_complete_score():
    result = classify_dhram(changes([None] + [0.0] * 9), evidence())
    assert result.points_lower == 0 and result.points_upper == 3
    assert result.classification is None and result.reasons


@pytest.mark.parametrize("value", [-1.0, float("nan"), float("inf")])
def test_invalid_change(value):
    with pytest.raises(ValueError):
        changes([value] + [0.0] * 9)


def test_source_and_required_membership():
    with pytest.raises(ValueError):
        changes([])
    with pytest.raises(ValueError):
        HydrologicalChanges((None,) * 10, ("",) * 10, "source")
    with pytest.raises(TypeError):
        SupplementaryEvidence(False, False, "source")  # ty: ignore[invalid-argument-type]


def test_summary_carrier_cannot_retain_mutable_lists():
    with pytest.raises(TypeError, match="immutable"):
        HydrologicalChanges([0.0] * 10, [""] * 10, "source")  # ty: ignore[invalid-argument-type]
