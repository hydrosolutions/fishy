"""Tests for IARI computation orchestrator."""

import numpy as np
import pytest

from fishy.iari.compute import compute_iari
from fishy.iari.errors import IncompatibleIHAResultsError, InsufficientYearsError

from .conftest import make_iha_result


class TestInputValidation:
    def test_incompatible_params_raises(self) -> None:
        natural = make_iha_result(np.ones((3, 33)))
        # Impacted has wrong number of params (32 instead of 33)
        impacted_values = np.ones((3, 32))
        impacted = make_iha_result(impacted_values)
        with pytest.raises(IncompatibleIHAResultsError):
            compute_iari(natural, impacted)

    def test_insufficient_natural_years_raises(self) -> None:
        # Natural has 0 years, min_years=1 (default)
        natural = make_iha_result(np.ones((0, 33)))
        impacted = make_iha_result(np.ones((3, 33)))
        with pytest.raises(InsufficientYearsError, match="natural"):
            compute_iari(natural, impacted, min_years=1)

    def test_insufficient_impacted_years_raises(self) -> None:
        natural = make_iha_result(np.ones((3, 33)))
        impacted = make_iha_result(np.ones((1, 33)))
        with pytest.raises(InsufficientYearsError, match="impacted"):
            compute_iari(natural, impacted, min_years=2)


class TestComputeIARI:
    def test_identical_is_non_negative(self, identical_iha_pair) -> None:
        natural, impacted = identical_iha_pair
        result = compute_iari(natural, impacted)
        assert result.overall >= 0

    def test_identical_has_valid_classification(self, identical_iha_pair) -> None:
        natural, impacted = identical_iha_pair
        result = compute_iari(natural, impacted)
        assert result.classification in ("Excellent", "Good", "Poor")

    def test_controlled_deviation(self, controlled_iha_pair) -> None:
        natural, impacted = controlled_iha_pair
        result = compute_iari(natural, impacted)
        # Natural: 5 years [10,20,30,40,50] per param -> Q25=20, Q75=40, IQR=20
        # Impacted: all 50 -> deviation = min(|50-20|,|50-40|)/20 = 10/20 = 0.5
        np.testing.assert_allclose(result.deviations, 0.5)
        np.testing.assert_allclose(result.overall, 0.5)

    def test_within_band_gives_zero(self, within_band_pair) -> None:
        natural, impacted = within_band_pair
        result = compute_iari(natural, impacted)
        np.testing.assert_allclose(result.overall, 0.0, atol=1e-10)

    def test_result_has_correct_years(self, identical_iha_pair) -> None:
        natural, impacted = identical_iha_pair
        result = compute_iari(natural, impacted)
        np.testing.assert_array_equal(result.years, impacted.years)

    def test_degenerate_params_recorded(self, degenerate_band_pair) -> None:
        natural, impacted = degenerate_band_pair
        result = compute_iari(natural, impacted)
        assert isinstance(result.degenerate_params, frozenset)
        assert len(result.degenerate_params) > 0

    def test_per_year_is_mean_of_deviations(self, controlled_iha_pair) -> None:
        natural, impacted = controlled_iha_pair
        result = compute_iari(natural, impacted)
        expected_per_year = np.mean(result.deviations, axis=1)
        np.testing.assert_allclose(result.per_year, expected_per_year)

    def test_overall_is_mean_of_per_year(self, controlled_iha_pair) -> None:
        natural, impacted = controlled_iha_pair
        result = compute_iari(natural, impacted)
        expected_overall = np.mean(result.per_year)
        np.testing.assert_allclose(result.overall, expected_overall)


class TestInvariants:
    def test_deviations_non_negative(self, identical_iha_pair) -> None:
        natural, impacted = identical_iha_pair
        result = compute_iari(natural, impacted)
        assert np.all(result.deviations >= 0)

    def test_overall_non_negative(self, identical_iha_pair) -> None:
        natural, impacted = identical_iha_pair
        result = compute_iari(natural, impacted)
        assert result.overall >= 0

    def test_deviations_shape(self, controlled_iha_pair) -> None:
        natural, impacted = controlled_iha_pair
        result = compute_iari(natural, impacted)
        n_impacted_years = impacted.values.shape[0]
        assert result.deviations.shape == (n_impacted_years, 33)
