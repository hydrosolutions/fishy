"""Tests for IHA bridge between taqsim WaterSystem and IHA computation."""

from datetime import date

import numpy as np
import pytest
from taqsim.node import TimeSeries
from taqsim.testing import make_edge, make_sink, make_source, make_system
from taqsim.time import Frequency

from fishy.iha.bridge import iha_from_trace
from fishy.iha.errors import (
    EdgeNotFoundError,
    EmptyTraceError,
    MissingStartDateError,
    NonDailyFrequencyError,
)
from fishy.iha.types import IHAResult

N_STEPS = 730  # ~2 years of daily data


def _variable_inflow(n: int, seed: int = 42) -> TimeSeries:
    """Create a sinusoidal + noise inflow pattern with distinct percentiles."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 4 * np.pi, n)
    values = 50.0 + 40.0 * np.sin(t) + rng.normal(0, 5, n)
    values = np.maximum(values, 0.1)
    return TimeSeries(values=values.tolist())


@pytest.fixture
def daily_system():
    """Simulated daily Source -> Sink system with natural tag."""
    system = make_system(
        make_source("source", n_steps=N_STEPS, inflow=_variable_inflow(N_STEPS)),
        make_sink("sink"),
        make_edge("e1", "source", "sink", tags=frozenset({"natural"})),
        frequency=Frequency.DAILY,
        start_date=date(2020, 1, 1),
        validate=False,
    )
    system.simulate(N_STEPS)
    return system


@pytest.fixture
def monthly_system():
    """Monthly system — IHA should reject."""
    system = make_system(
        make_source("source", n_steps=24),
        make_sink("sink"),
        make_edge("e1", "source", "sink"),
        frequency=Frequency.MONTHLY,
        start_date=date(2020, 1, 1),
        validate=False,
    )
    system.simulate(24)
    return system


@pytest.fixture
def no_start_date_system():
    """Daily system without start_date."""
    system = make_system(
        make_source("source", n_steps=N_STEPS),
        make_sink("sink"),
        make_edge("e1", "source", "sink"),
        frequency=Frequency.DAILY,
        validate=False,
    )
    system.simulate(N_STEPS)
    return system


@pytest.fixture
def unsimulated_system():
    """Daily system that has not been simulated — edges have no traces."""
    return make_system(
        make_source("source", n_steps=N_STEPS),
        make_sink("sink"),
        make_edge("e1", "source", "sink"),
        frequency=Frequency.DAILY,
        start_date=date(2020, 1, 1),
        validate=False,
    )


class TestValidation:
    def test_non_daily_raises(self, monthly_system) -> None:
        with pytest.raises(NonDailyFrequencyError, match="365"):
            iha_from_trace(monthly_system, "e1")

    def test_missing_start_date_raises(self, no_start_date_system) -> None:
        with pytest.raises(MissingStartDateError, match="start_date"):
            iha_from_trace(no_start_date_system, "e1")

    def test_edge_not_found_raises(self, daily_system) -> None:
        with pytest.raises(EdgeNotFoundError, match="nonexistent"):
            iha_from_trace(daily_system, "nonexistent")

    def test_edge_not_found_shows_available(self, daily_system) -> None:
        with pytest.raises(EdgeNotFoundError, match="e1"):
            iha_from_trace(daily_system, "nonexistent")

    def test_empty_trace_raises(self, unsimulated_system) -> None:
        with pytest.raises(EmptyTraceError, match="e1"):
            iha_from_trace(unsimulated_system, "e1")


class TestConversion:
    def test_returns_iha_result(self, daily_system) -> None:
        result = iha_from_trace(daily_system, "e1")
        assert isinstance(result, IHAResult)

    def test_has_correct_shape(self, daily_system) -> None:
        result = iha_from_trace(daily_system, "e1")
        assert result.values.shape[1] == 33

    def test_years_populated(self, daily_system) -> None:
        result = iha_from_trace(daily_system, "e1")
        assert len(result.years) >= 1


class TestEndToEnd:
    def test_full_pipeline(self, daily_system) -> None:
        result = iha_from_trace(daily_system, "e1")
        assert isinstance(result, IHAResult)
        assert result.values.shape[0] >= 1
        assert result.values.shape[1] == 33
        # Years should be in the 2020 range
        assert all(2020 <= y <= 2022 for y in result.years)

    def test_custom_pulse_thresholds(self, daily_system) -> None:
        from fishy.iha.types import PulseThresholds

        thresholds = PulseThresholds(low=10.0, high=90.0)
        result = iha_from_trace(daily_system, "e1", pulse_thresholds=thresholds)
        assert result.pulse_thresholds == thresholds
