"""Tests for DHRAM type definitions."""

import pytest

from fishy.dhram.types import (
    EMPIRICAL_THRESHOLDS,
    INDICATOR_NAMES,
    N_INDICATORS,
    SIMPLIFIED_THRESHOLDS,
    WFD_LABELS,
    DHRAMResult,
    IndicatorDetail,
    ScoringThresholds,
    ThresholdVariant,
)


class TestScoringThresholds:
    def test_valid_construction(self) -> None:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        assert t.lower == 10.0
        assert t.intermediate == 30.0
        assert t.upper == 50.0

    def test_invalid_order_raises(self) -> None:
        with pytest.raises(ValueError, match="0 <= lower <= intermediate <= upper"):
            ScoringThresholds(50.0, 30.0, 10.0)

    def test_negative_lower_raises(self) -> None:
        with pytest.raises(ValueError, match="0 <= lower"):
            ScoringThresholds(-1.0, 30.0, 50.0)

    def test_score_below_lower(self) -> None:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        assert t.score(5.0) == 0

    def test_score_at_lower(self) -> None:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        assert t.score(10.0) == 1

    def test_score_between_lower_and_intermediate(self) -> None:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        assert t.score(20.0) == 1

    def test_score_at_intermediate(self) -> None:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        assert t.score(30.0) == 2

    def test_score_between_intermediate_and_upper(self) -> None:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        assert t.score(40.0) == 2

    def test_score_at_upper(self) -> None:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        assert t.score(50.0) == 3

    def test_score_above_upper(self) -> None:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        assert t.score(100.0) == 3

    def test_frozen(self) -> None:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        with pytest.raises(AttributeError):
            t.lower = 5.0  # type: ignore[misc]


class TestThresholdConstants:
    def test_empirical_count(self) -> None:
        assert len(EMPIRICAL_THRESHOLDS) == N_INDICATORS

    def test_simplified_count(self) -> None:
        assert len(SIMPLIFIED_THRESHOLDS) == N_INDICATORS

    def test_empirical_spot_check_1a(self) -> None:
        assert EMPIRICAL_THRESHOLDS[0].lower == 19.9
        assert EMPIRICAL_THRESHOLDS[0].intermediate == 43.7
        assert EMPIRICAL_THRESHOLDS[0].upper == 67.5

    def test_empirical_spot_check_3a(self) -> None:
        assert EMPIRICAL_THRESHOLDS[4].lower == 7.0
        assert EMPIRICAL_THRESHOLDS[4].intermediate == 21.2
        assert EMPIRICAL_THRESHOLDS[4].upper == 35.5

    def test_empirical_monotonicity(self) -> None:
        for t in EMPIRICAL_THRESHOLDS:
            assert 0 <= t.lower <= t.intermediate <= t.upper

    def test_simplified_uniform(self) -> None:
        for t in SIMPLIFIED_THRESHOLDS:
            assert t.lower == 10.0
            assert t.intermediate == 30.0
            assert t.upper == 50.0


class TestIndicatorDetail:
    def test_construction(self) -> None:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        ind = IndicatorDetail(name="1a", group=1, statistic="mean", value=25.0, points=1, thresholds=t)
        assert ind.name == "1a"
        assert ind.points == 1

    def test_frozen(self) -> None:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        ind = IndicatorDetail(name="1a", group=1, statistic="mean", value=25.0, points=1, thresholds=t)
        with pytest.raises(AttributeError):
            ind.value = 50.0  # type: ignore[misc]


class TestDHRAMResult:
    def _make_result(self, total_points: int = 7, preliminary_class: int = 3, final_class: int = 3) -> DHRAMResult:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        indicators = tuple(
            IndicatorDetail(
                name=INDICATOR_NAMES[i],
                group=(i // 2) + 1,
                statistic="mean" if i % 2 == 0 else "cv",
                value=float(i * 5),
                points=1 if i < total_points else 0,
                thresholds=t,
            )
            for i in range(N_INDICATORS)
        )
        actual_points = sum(ind.points for ind in indicators)
        return DHRAMResult(
            indicators=indicators,
            total_points=actual_points,
            preliminary_class=preliminary_class,
            flow_cessation=False,
            subdaily_oscillation=False,
            final_class=final_class,
            wfd_status="Moderate",
            threshold_variant=ThresholdVariant.EMPIRICAL,
            natural_years=5,
            impacted_years=5,
        )

    def test_valid_construction(self) -> None:
        result = self._make_result()
        assert len(result.indicators) == 10

    def test_wrong_indicator_count_raises(self) -> None:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        with pytest.raises(ValueError, match="Expected 10 indicators"):
            DHRAMResult(
                indicators=(IndicatorDetail("1a", 1, "mean", 0.0, 0, t),),
                total_points=0,
                preliminary_class=1,
                flow_cessation=False,
                subdaily_oscillation=False,
                final_class=1,
                wfd_status="High",
                threshold_variant=ThresholdVariant.EMPIRICAL,
                natural_years=5,
                impacted_years=5,
            )

    def test_invalid_points_raises(self) -> None:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        indicators = tuple(IndicatorDetail(INDICATOR_NAMES[i], (i // 2) + 1, "mean", 0.0, 0, t) for i in range(10))
        with pytest.raises(ValueError, match="Total points"):
            DHRAMResult(
                indicators=indicators,
                total_points=31,
                preliminary_class=1,
                flow_cessation=False,
                subdaily_oscillation=False,
                final_class=1,
                wfd_status="High",
                threshold_variant=ThresholdVariant.EMPIRICAL,
                natural_years=5,
                impacted_years=5,
            )

    def test_invalid_class_raises(self) -> None:
        t = ScoringThresholds(10.0, 30.0, 50.0)
        indicators = tuple(IndicatorDetail(INDICATOR_NAMES[i], (i // 2) + 1, "mean", 0.0, 0, t) for i in range(10))
        with pytest.raises(ValueError, match="Preliminary class"):
            DHRAMResult(
                indicators=indicators,
                total_points=0,
                preliminary_class=0,
                flow_cessation=False,
                subdaily_oscillation=False,
                final_class=1,
                wfd_status="High",
                threshold_variant=ThresholdVariant.EMPIRICAL,
                natural_years=5,
                impacted_years=5,
            )

    def test_indicator_lookup(self) -> None:
        result = self._make_result()
        ind = result.indicator("1a")
        assert ind.name == "1a"

    def test_indicator_lookup_missing(self) -> None:
        result = self._make_result()
        with pytest.raises(ValueError, match="not found"):
            result.indicator("6a")

    def test_group_points(self) -> None:
        result = self._make_result()
        total = sum(result.group_points(g) for g in range(1, 6))
        assert total == result.total_points

    def test_group_points_invalid_group(self) -> None:
        result = self._make_result()
        with pytest.raises(ValueError, match="Group must be"):
            result.group_points(0)

    def test_summary_contains_class(self) -> None:
        result = self._make_result()
        summary = result.summary()
        assert "Class" in summary
        assert "Moderate" in summary

    def test_frozen(self) -> None:
        result = self._make_result()
        with pytest.raises(AttributeError):
            result.total_points = 0  # type: ignore[misc]


class TestWFDMapping:
    @pytest.mark.parametrize(
        "dhram_class, expected_label",
        [(1, "High"), (2, "Good"), (3, "Moderate"), (4, "Poor"), (5, "Bad")],
    )
    def test_wfd_labels(self, dhram_class: int, expected_label: str) -> None:
        assert WFD_LABELS[dhram_class - 1] == expected_label


class TestPointsToClass:
    @pytest.mark.parametrize(
        "points, expected_class",
        [
            (0, 1),
            (1, 2),
            (4, 2),
            (5, 3),
            (10, 3),
            (11, 4),
            (20, 4),
            (21, 5),
            (30, 5),
        ],
    )
    def test_classification_boundaries(self, points: int, expected_class: int) -> None:
        from fishy.dhram._indicators import classify

        assert classify(points) == expected_class
