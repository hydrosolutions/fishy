"""Tests for IARI deviation math."""

import numpy as np

from fishy.iari._deviation import bands_from_iha, classify_iari, compute_deviations
from fishy.iari.types import NaturalBands
from fishy.iha.types import PulseThresholds

from .conftest import make_iha_result


class TestBandsFromIHA:
    def test_returns_natural_bands(self) -> None:
        values = np.tile(np.linspace(10, 50, 5), (33, 1)).T  # (5, 33)
        iha = make_iha_result(values)
        bands = bands_from_iha(iha)
        assert isinstance(bands, NaturalBands)

    def test_q25_q75_from_known_values(self) -> None:
        # 5 years, each param has values [10, 20, 30, 40, 50]
        col_values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        values = np.tile(col_values, (33, 1)).T  # shape (5, 33)
        iha = make_iha_result(values)
        bands = bands_from_iha(iha)
        expected_q25 = np.percentile(col_values, 25)
        expected_q75 = np.percentile(col_values, 75)
        np.testing.assert_allclose(bands.q25, np.full(33, expected_q25))
        np.testing.assert_allclose(bands.q75, np.full(33, expected_q75))

    def test_preserves_pulse_thresholds(self) -> None:
        col_values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        values = np.tile(col_values, (33, 1)).T
        pt = PulseThresholds(low=3.0, high=80.0)
        iha = make_iha_result(values, pulse_thresholds=pt)
        bands = bands_from_iha(iha)
        assert bands.pulse_thresholds == pt


class TestComputeDeviations:
    def _make_bands(self, q25: float = 20.0, q75: float = 40.0) -> NaturalBands:
        return NaturalBands(
            q25=np.full(33, q25),
            q75=np.full(33, q75),
            pulse_thresholds=PulseThresholds(low=5.0, high=50.0),
        )

    def test_within_band_zero(self) -> None:
        bands = self._make_bands(q25=20.0, q75=40.0)
        impacted = np.full((1, 33), 30.0)
        result = compute_deviations(impacted, bands)
        np.testing.assert_allclose(result, 0.0)

    def test_below_band(self) -> None:
        bands = self._make_bands(q25=20.0, q75=40.0)
        impacted = np.full((1, 33), 5.0)
        result = compute_deviations(impacted, bands)
        # min(|5-20|, |5-40|) / 20 = min(15, 35) / 20 = 0.75
        np.testing.assert_allclose(result, 0.75)

    def test_above_band(self) -> None:
        bands = self._make_bands(q25=20.0, q75=40.0)
        impacted = np.full((1, 33), 50.0)
        result = compute_deviations(impacted, bands)
        # min(|50-20|, |50-40|) / 20 = min(30, 10) / 20 = 0.5
        np.testing.assert_allclose(result, 0.5)

    def test_at_boundary_zero(self) -> None:
        bands = self._make_bands(q25=20.0, q75=40.0)
        # Value at Q25
        impacted_q25 = np.full((1, 33), 20.0)
        result_q25 = compute_deviations(impacted_q25, bands)
        np.testing.assert_allclose(result_q25, 0.0)
        # Value at Q75
        impacted_q75 = np.full((1, 33), 40.0)
        result_q75 = compute_deviations(impacted_q75, bands)
        np.testing.assert_allclose(result_q75, 0.0)

    def test_hand_computed_example(self) -> None:
        """Value=50, Q25=20, Q75=40, IQR=20 -> deviation = min(30,10)/20 = 0.5."""
        bands = self._make_bands(q25=20.0, q75=40.0)
        impacted = np.full((1, 33), 50.0)
        result = compute_deviations(impacted, bands)
        np.testing.assert_allclose(result, 0.5)

    def test_vectorized_multiple_years(self) -> None:
        bands = self._make_bands(q25=20.0, q75=40.0)
        # 3 years: row0=30 (inside), row1=50 (above), row2=5 (below)
        impacted = np.array(
            [
                np.full(33, 30.0),
                np.full(33, 50.0),
                np.full(33, 5.0),
            ]
        )
        result = compute_deviations(impacted, bands)
        assert result.shape == (3, 33)
        np.testing.assert_allclose(result[0], 0.0)
        np.testing.assert_allclose(result[1], 0.5)
        np.testing.assert_allclose(result[2], 0.75)

    def test_degenerate_band_outside_gets_one(self) -> None:
        # IQR=0, value differs from band -> 1.0
        bands = self._make_bands(q25=30.0, q75=30.0)
        impacted = np.full((1, 33), 50.0)
        result = compute_deviations(impacted, bands)
        np.testing.assert_allclose(result, 1.0)

    def test_degenerate_band_inside_gets_zero(self) -> None:
        # IQR=0, value matches band -> 0.0
        bands = self._make_bands(q25=30.0, q75=30.0)
        impacted = np.full((1, 33), 30.0)
        result = compute_deviations(impacted, bands)
        np.testing.assert_allclose(result, 0.0)


class TestClassifyIARI:
    def test_excellent(self) -> None:
        assert classify_iari(0.0) == "Excellent"
        assert classify_iari(0.03) == "Excellent"

    def test_good(self) -> None:
        assert classify_iari(0.10) == "Good"

    def test_poor(self) -> None:
        assert classify_iari(0.5) == "Poor"
        assert classify_iari(1.0) == "Poor"

    def test_boundary_excellent(self) -> None:
        # 0.05 is the threshold: <= 0.05 -> Excellent
        assert classify_iari(0.05) == "Excellent"
        # Just above -> Good
        assert classify_iari(0.051) == "Good"

    def test_boundary_good(self) -> None:
        # 0.15 is the threshold: <= 0.15 -> Good
        assert classify_iari(0.15) == "Good"
        # Just above -> Poor
        assert classify_iari(0.151) == "Poor"

    def test_zero_is_excellent(self) -> None:
        assert classify_iari(0.0) == "Excellent"
