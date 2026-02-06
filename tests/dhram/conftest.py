"""Shared fixtures for DHRAM tests."""

import numpy as np
import pytest

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


@pytest.fixture
def identical_iha_pair() -> tuple[IHAResult, IHAResult]:
    """Identical natural and impacted — should be Class 1, 0 points."""
    rng = np.random.default_rng(42)
    values = rng.uniform(1.0, 100.0, size=(5, 33))
    # Set timing columns to valid DOY range
    values[:, 24] = rng.uniform(1, 365, size=5)
    values[:, 25] = rng.uniform(1, 365, size=5)
    natural = make_iha_result(values.copy())
    impacted = make_iha_result(values.copy())
    return natural, impacted


@pytest.fixture
def slightly_altered_pair() -> tuple[IHAResult, IHAResult]:
    """Small perturbation — should be low class (1 or 2)."""
    rng = np.random.default_rng(42)
    values = rng.uniform(10.0, 100.0, size=(5, 33))
    values[:, 24] = rng.uniform(100, 200, size=5)
    values[:, 25] = rng.uniform(100, 200, size=5)
    natural = make_iha_result(values.copy())
    # Add ~5% noise
    noise = values * rng.uniform(-0.05, 0.05, size=values.shape)
    impacted_values = values + noise
    impacted_values = np.maximum(impacted_values, 0.01)
    impacted = make_iha_result(impacted_values)
    return natural, impacted


@pytest.fixture
def severely_altered_pair() -> tuple[IHAResult, IHAResult]:
    """10x amplification — should be high class (4 or 5)."""
    rng = np.random.default_rng(42)
    values = rng.uniform(10.0, 50.0, size=(5, 33))
    values[:, 24] = rng.uniform(50, 100, size=5)
    values[:, 25] = rng.uniform(50, 100, size=5)
    natural = make_iha_result(values.copy())
    impacted_values = values * 10.0
    # Keep timing in valid range
    impacted_values[:, 24] = rng.uniform(250, 350, size=5)
    impacted_values[:, 25] = rng.uniform(250, 350, size=5)
    impacted = make_iha_result(impacted_values)
    return natural, impacted


@pytest.fixture
def single_year_iha_pair() -> tuple[IHAResult, IHAResult]:
    """Single-year pair — CV edge case (all zeros)."""
    rng = np.random.default_rng(42)
    values = rng.uniform(10.0, 100.0, size=(1, 33))
    values[:, 24] = 180.0
    values[:, 25] = 50.0
    natural = make_iha_result(values.copy())
    impacted_values = values * 2.0
    impacted_values[:, 24] = 300.0
    impacted_values[:, 25] = 150.0
    impacted = make_iha_result(impacted_values)
    return natural, impacted
