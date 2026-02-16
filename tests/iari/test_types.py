"""Tests for IARI type definitions."""

import numpy as np
import pytest

from fishy.iari.types import (
    CLASSIFICATION_LABELS,
    EXCELLENT_THRESHOLD,
    GOOD_THRESHOLD,
    IARIResult,
    NaturalBands,
)
from fishy.iha.types import PulseThresholds


def _make_bands(
    q25: np.ndarray | None = None,
    q75: np.ndarray | None = None,
) -> NaturalBands:
    """Helper to build a valid NaturalBands with defaults."""
    if q25 is None:
        q25 = np.full(33, 10.0)
    if q75 is None:
        q75 = np.full(33, 40.0)
    return NaturalBands(
        q25=q25,
        q75=q75,
        pulse_thresholds=PulseThresholds(low=5.0, high=50.0),
    )


def _make_iari_result(
    n_years: int = 3,
    overall: float = 0.1,
    classification: str = "Good",
    degenerate_params: frozenset[int] | None = None,
) -> IARIResult:
    """Helper to build a valid IARIResult with defaults."""
    deviations = np.full((n_years, 33), 0.1)
    years = np.arange(2000, 2000 + n_years, dtype=np.intp)
    per_year = np.full(n_years, overall)
    bands = _make_bands()
    if degenerate_params is None:
        degenerate_params = frozenset()
    return IARIResult(
        deviations=deviations,
        years=years,
        per_year=per_year,
        overall=overall,
        classification=classification,
        bands=bands,
        degenerate_params=degenerate_params,
        natural_years=5,
        impacted_years=n_years,
    )


class TestNaturalBands:
    def test_valid_construction(self) -> None:
        bands = _make_bands()
        assert bands.q25.shape == (33,)
        assert bands.q75.shape == (33,)
        assert isinstance(bands.pulse_thresholds, PulseThresholds)

    def test_wrong_q25_shape_raises(self) -> None:
        with pytest.raises(ValueError, match="q25 must have shape"):
            _make_bands(q25=np.full(10, 10.0))

    def test_wrong_q75_shape_raises(self) -> None:
        with pytest.raises(ValueError, match="q75 must have shape"):
            _make_bands(q75=np.full(5, 40.0))

    def test_q25_greater_than_q75_raises(self) -> None:
        q25 = np.full(33, 50.0)
        q75 = np.full(33, 10.0)
        with pytest.raises(ValueError, match="q25 must be <= q75"):
            _make_bands(q25=q25, q75=q75)

    def test_width_property(self) -> None:
        q25 = np.full(33, 10.0)
        q75 = np.full(33, 40.0)
        bands = _make_bands(q25=q25, q75=q75)
        np.testing.assert_array_equal(bands.width, np.full(33, 30.0))

    def test_degenerate_mask_property(self) -> None:
        q25 = np.full(33, 20.0)
        q75 = np.full(33, 20.0)
        # All degenerate (width=0)
        bands = _make_bands(q25=q25, q75=q75)
        assert bands.degenerate_mask.all()

        # Mix: first 10 degenerate, rest not
        q75_mixed = np.full(33, 20.0)
        q75_mixed[10:] = 40.0
        bands_mixed = _make_bands(q25=q25, q75=q75_mixed)
        assert bands_mixed.degenerate_mask[:10].all()
        assert not bands_mixed.degenerate_mask[10:].any()

    def test_frozen(self) -> None:
        bands = _make_bands()
        with pytest.raises(AttributeError):
            bands.q25 = np.full(33, 0.0)  # type: ignore[misc]


class TestIARIResult:
    def test_valid_construction(self) -> None:
        result = _make_iari_result()
        assert result.deviations.shape == (3, 33)
        assert result.years.shape == (3,)
        assert result.per_year.shape == (3,)
        assert result.overall == 0.1
        assert result.classification == "Good"

    def test_wrong_deviations_shape_raises(self) -> None:
        with pytest.raises(ValueError, match="deviations must have shape"):
            IARIResult(
                deviations=np.full((3, 10), 0.1),
                years=np.arange(2000, 2003, dtype=np.intp),
                per_year=np.full(3, 0.1),
                overall=0.1,
                classification="Good",
                bands=_make_bands(),
                degenerate_params=frozenset(),
                natural_years=5,
                impacted_years=3,
            )

    def test_years_shape_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="years must have shape"):
            IARIResult(
                deviations=np.full((3, 33), 0.1),
                years=np.arange(2000, 2005, dtype=np.intp),  # 5 != 3
                per_year=np.full(3, 0.1),
                overall=0.1,
                classification="Good",
                bands=_make_bands(),
                degenerate_params=frozenset(),
                natural_years=5,
                impacted_years=3,
            )

    def test_per_year_shape_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="per_year must have shape"):
            IARIResult(
                deviations=np.full((3, 33), 0.1),
                years=np.arange(2000, 2003, dtype=np.intp),
                per_year=np.full(5, 0.1),  # 5 != 3
                overall=0.1,
                classification="Good",
                bands=_make_bands(),
                degenerate_params=frozenset(),
                natural_years=5,
                impacted_years=3,
            )

    def test_invalid_classification_raises(self) -> None:
        with pytest.raises(ValueError, match="classification must be one of"):
            _make_iari_result(classification="Terrible")

    def test_negative_overall_raises(self) -> None:
        with pytest.raises(ValueError, match="overall must be >= 0"):
            _make_iari_result(overall=-0.5)

    def test_year_row_found(self) -> None:
        result = _make_iari_result(n_years=3)
        row = result.year_row(2001)
        assert row.shape == (33,)
        np.testing.assert_array_equal(row, result.deviations[1])

    def test_year_row_not_found_raises(self) -> None:
        result = _make_iari_result(n_years=3)
        with pytest.raises(ValueError, match="year 9999 not found"):
            result.year_row(9999)

    def test_param_deviation_valid(self) -> None:
        result = _make_iari_result(n_years=3)
        col_data = result.param_deviation(0)
        assert col_data.shape == (3,)
        np.testing.assert_array_equal(col_data, result.deviations[:, 0])

    def test_param_deviation_out_of_range_raises(self) -> None:
        result = _make_iari_result(n_years=3)
        with pytest.raises(ValueError, match="col must be between 0 and 32"):
            result.param_deviation(33)
        with pytest.raises(ValueError, match="col must be between 0 and 32"):
            result.param_deviation(-1)

    def test_summary_contains_key_info(self) -> None:
        result = _make_iari_result(n_years=2, overall=0.12, classification="Good")
        text = result.summary()
        assert "0.1200" in text
        assert "Good" in text
        assert "2000" in text
        assert "2001" in text
        assert "natural" in text.lower() or "Natural" in text
        assert "impacted" in text.lower() or "Impacted" in text

    def test_frozen(self) -> None:
        result = _make_iari_result()
        with pytest.raises(AttributeError):
            result.overall = 0.5  # type: ignore[misc]


class TestConstants:
    def test_excellent_threshold(self) -> None:
        assert EXCELLENT_THRESHOLD == 0.05

    def test_good_threshold(self) -> None:
        assert GOOD_THRESHOLD == 0.15

    def test_classification_labels(self) -> None:
        assert CLASSIFICATION_LABELS == ("Excellent", "Good", "Poor")
