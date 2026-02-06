"""Tests for DHRAM computation."""

import numpy as np
import pytest

from fishy.dhram._indicators import (
    apply_supplementary,
    circular_distance_days,
    circular_mean_doy,
    classify,
    compute_cv,
    extract_dhram_group_params,
    safe_percent_change,
    wfd_label,
)
from fishy.dhram.compute import compute_dhram
from fishy.dhram.errors import IncompatibleIHAResultsError, InsufficientYearsError
from fishy.dhram.types import (
    EMPIRICAL_THRESHOLDS,
    ThresholdVariant,
)
from fishy.iha.types import IHAResult, PulseThresholds


def make_iha_result(
    values: np.ndarray,
    years: np.ndarray | None = None,
    zero_flow_threshold: float = 0.001,
    pulse_thresholds: PulseThresholds | None = None,
) -> IHAResult:
    """Helper to construct IHAResult from a values array."""
    if values.ndim == 1:
        values = values.reshape(1, -1)
    n_years = values.shape[0]
    if years is None:
        years = np.arange(2000, 2000 + n_years, dtype=np.intp)
    if pulse_thresholds is None:
        pulse_thresholds = PulseThresholds(low=5.0, high=50.0)
    return IHAResult(
        values=values,
        years=years,
        zero_flow_threshold=zero_flow_threshold,
        pulse_thresholds=pulse_thresholds,
    )


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_incompatible_shapes_raises(self) -> None:
        nat = make_iha_result(np.ones((3, 33)))
        imp = make_iha_result(np.ones((3, 10)))
        with pytest.raises(IncompatibleIHAResultsError, match="parameters"):
            compute_dhram(nat, imp)

    def test_natural_incompatible_shape_raises(self) -> None:
        nat = make_iha_result(np.ones((3, 10)))
        imp = make_iha_result(np.ones((3, 33)))
        with pytest.raises(IncompatibleIHAResultsError):
            compute_dhram(nat, imp)

    def test_insufficient_natural_years(self) -> None:
        nat = make_iha_result(np.ones((1, 33)))
        imp = make_iha_result(np.ones((5, 33)))
        with pytest.raises(InsufficientYearsError, match="natural"):
            compute_dhram(nat, imp, min_years=3)

    def test_insufficient_impacted_years(self) -> None:
        nat = make_iha_result(np.ones((5, 33)))
        imp = make_iha_result(np.ones((1, 33)))
        with pytest.raises(InsufficientYearsError, match="impacted"):
            compute_dhram(nat, imp, min_years=3)


# ---------------------------------------------------------------------------
# Scoring logic
# ---------------------------------------------------------------------------


class TestScoringLogic:
    def test_score_below_lower(self) -> None:
        assert EMPIRICAL_THRESHOLDS[0].score(10.0) == 0

    def test_score_at_lower(self) -> None:
        assert EMPIRICAL_THRESHOLDS[0].score(19.9) == 1

    def test_score_at_intermediate(self) -> None:
        assert EMPIRICAL_THRESHOLDS[0].score(43.7) == 2

    def test_score_at_upper(self) -> None:
        assert EMPIRICAL_THRESHOLDS[0].score(67.5) == 3


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestCircularStatistics:
    def test_circular_mean_same_values(self) -> None:
        doy = np.array([180.0, 180.0, 180.0])
        assert circular_mean_doy(doy) == pytest.approx(180.0, abs=0.1)

    def test_circular_mean_wraps_around(self) -> None:
        doy = np.array([1.0, 365.0])
        mean = circular_mean_doy(doy)
        # Should be close to 0.5 (or 365.75) — near Jan 1
        assert mean < 5.0 or mean > 360.0

    def test_circular_distance_same(self) -> None:
        assert circular_distance_days(100.0, 100.0) == pytest.approx(0.0)

    def test_circular_distance_short_arc(self) -> None:
        assert circular_distance_days(10.0, 355.0) == pytest.approx(20.25, abs=0.1)

    def test_circular_distance_max(self) -> None:
        dist = circular_distance_days(1.0, 183.625)
        assert dist <= 365.25 / 2


class TestSafePercentChange:
    def test_both_zero(self) -> None:
        assert safe_percent_change(0.0, 0.0) == 0.0

    def test_natural_zero_impacted_nonzero(self) -> None:
        assert safe_percent_change(0.0, 50.0) == 100.0

    def test_normal_change(self) -> None:
        assert safe_percent_change(100.0, 150.0) == pytest.approx(50.0)

    def test_no_change(self) -> None:
        assert safe_percent_change(50.0, 50.0) == pytest.approx(0.0)


class TestComputeCV:
    def test_constant_values(self) -> None:
        assert compute_cv(np.array([10.0, 10.0, 10.0])) == pytest.approx(0.0)

    def test_known_cv(self) -> None:
        values = np.array([10.0, 20.0, 30.0])
        mean = 20.0
        std = np.std(values, ddof=0)
        expected = float(std / mean * 100)
        assert compute_cv(values) == pytest.approx(expected)

    def test_near_zero_mean(self) -> None:
        assert compute_cv(np.array([1e-15, -1e-15])) == 0.0


class TestExtractGroupParams:
    def test_group1_has_12_columns(self) -> None:
        values = np.ones((3, 33))
        result = extract_dhram_group_params(values, 1)
        assert result.shape[1] == 12

    def test_group2_has_10_columns(self) -> None:
        values = np.ones((3, 33))
        result = extract_dhram_group_params(values, 2)
        assert result.shape[1] == 10

    def test_group2_excludes_zero_flow_and_bfi(self) -> None:
        values = np.zeros((1, 33))
        values[0, 22] = 999.0  # zero_flow_days
        values[0, 23] = 888.0  # BFI
        result = extract_dhram_group_params(values, 2)
        assert 999.0 not in result
        assert 888.0 not in result

    def test_group3_has_2_columns(self) -> None:
        values = np.ones((3, 33))
        assert extract_dhram_group_params(values, 3).shape[1] == 2

    def test_group4_has_4_columns(self) -> None:
        values = np.ones((3, 33))
        assert extract_dhram_group_params(values, 4).shape[1] == 4

    def test_group5_has_3_columns(self) -> None:
        values = np.ones((3, 33))
        assert extract_dhram_group_params(values, 5).shape[1] == 3


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class TestClassification:
    @pytest.mark.parametrize(
        "points, expected",
        [
            (0, 1),
            (1, 2),
            (2, 2),
            (3, 2),
            (4, 2),
            (5, 3),
            (6, 3),
            (10, 3),
            (11, 4),
            (15, 4),
            (20, 4),
            (21, 5),
            (25, 5),
            (30, 5),
        ],
    )
    def test_points_to_class(self, points: int, expected: int) -> None:
        assert classify(points) == expected


class TestSupplementary:
    def test_no_flags(self) -> None:
        assert apply_supplementary(2, flow_cessation=False, subdaily_oscillation=False) == 2

    def test_flow_cessation_only(self) -> None:
        assert apply_supplementary(2, flow_cessation=True, subdaily_oscillation=False) == 3

    def test_subdaily_only(self) -> None:
        assert apply_supplementary(2, flow_cessation=False, subdaily_oscillation=True) == 3

    def test_both_flags(self) -> None:
        assert apply_supplementary(2, flow_cessation=True, subdaily_oscillation=True) == 4

    def test_capped_at_5(self) -> None:
        assert apply_supplementary(4, flow_cessation=True, subdaily_oscillation=True) == 5

    def test_already_5_stays_5(self) -> None:
        assert apply_supplementary(5, flow_cessation=True, subdaily_oscillation=True) == 5


class TestWFDLabel:
    @pytest.mark.parametrize(
        "cls, label",
        [(1, "High"), (2, "Good"), (3, "Moderate"), (4, "Poor"), (5, "Bad")],
    )
    def test_label_mapping(self, cls: int, label: str) -> None:
        assert wfd_label(cls) == label


# ---------------------------------------------------------------------------
# Threshold variants
# ---------------------------------------------------------------------------


class TestThresholdVariants:
    def test_default_is_empirical(self, identical_iha_pair) -> None:
        nat, imp = identical_iha_pair
        result = compute_dhram(nat, imp)
        assert result.threshold_variant == ThresholdVariant.EMPIRICAL

    def test_simplified_option(self, identical_iha_pair) -> None:
        nat, imp = identical_iha_pair
        result = compute_dhram(nat, imp, threshold_variant=ThresholdVariant.SIMPLIFIED)
        assert result.threshold_variant == ThresholdVariant.SIMPLIFIED


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_identical_produces_class_1(self, identical_iha_pair) -> None:
        nat, imp = identical_iha_pair
        result = compute_dhram(nat, imp)
        assert result.total_points == 0
        assert result.final_class == 1
        assert result.wfd_status == "High"

    def test_severe_alteration_high_class(self, severely_altered_pair) -> None:
        nat, imp = severely_altered_pair
        result = compute_dhram(nat, imp)
        assert result.final_class >= 4

    def test_single_year_cv_zero(self, single_year_iha_pair) -> None:
        nat, imp = single_year_iha_pair
        result = compute_dhram(nat, imp)
        # Single year means CV=0 for both → 0% CV change for all groups
        for ind in result.indicators:
            if ind.statistic == "cv":
                assert ind.value == pytest.approx(0.0)

    def test_supplementary_worsens_class(self, identical_iha_pair) -> None:
        nat, imp = identical_iha_pair
        result_no_flags = compute_dhram(nat, imp)
        result_cessation = compute_dhram(nat, imp, flow_cessation=True)
        assert result_cessation.final_class >= result_no_flags.final_class

    def test_ten_indicators_always(self, identical_iha_pair) -> None:
        nat, imp = identical_iha_pair
        result = compute_dhram(nat, imp)
        assert len(result.indicators) == 10
        names = [ind.name for ind in result.indicators]
        assert names == ["1a", "1b", "2a", "2b", "3a", "3b", "4a", "4b", "5a", "5b"]


# ---------------------------------------------------------------------------
# Invariants (parametrized across fixtures)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name",
    ["identical_iha_pair", "slightly_altered_pair", "severely_altered_pair", "single_year_iha_pair"],
)
class TestInvariants:
    def test_points_in_range(self, fixture_name, request) -> None:
        nat, imp = request.getfixturevalue(fixture_name)
        result = compute_dhram(nat, imp)
        assert 0 <= result.total_points <= 30

    def test_class_in_range(self, fixture_name, request) -> None:
        nat, imp = request.getfixturevalue(fixture_name)
        result = compute_dhram(nat, imp)
        assert 1 <= result.final_class <= 5

    def test_final_geq_preliminary(self, fixture_name, request) -> None:
        nat, imp = request.getfixturevalue(fixture_name)
        result = compute_dhram(nat, imp)
        assert result.final_class >= result.preliminary_class

    def test_ten_indicators(self, fixture_name, request) -> None:
        nat, imp = request.getfixturevalue(fixture_name)
        result = compute_dhram(nat, imp)
        assert len(result.indicators) == 10

    def test_each_indicator_0_to_3(self, fixture_name, request) -> None:
        nat, imp = request.getfixturevalue(fixture_name)
        result = compute_dhram(nat, imp)
        for ind in result.indicators:
            assert 0 <= ind.points <= 3

    def test_indicator_values_non_negative(self, fixture_name, request) -> None:
        nat, imp = request.getfixturevalue(fixture_name)
        result = compute_dhram(nat, imp)
        for ind in result.indicators:
            assert ind.value >= 0.0

    def test_sum_matches_total(self, fixture_name, request) -> None:
        nat, imp = request.getfixturevalue(fixture_name)
        result = compute_dhram(nat, imp)
        assert sum(ind.points for ind in result.indicators) == result.total_points

    def test_wfd_matches_class(self, fixture_name, request) -> None:
        nat, imp = request.getfixturevalue(fixture_name)
        result = compute_dhram(nat, imp)
        expected_wfd = ["High", "Good", "Moderate", "Poor", "Bad"][result.final_class - 1]
        assert result.wfd_status == expected_wfd
