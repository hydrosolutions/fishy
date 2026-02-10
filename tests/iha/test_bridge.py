"""Tests for IHA bridge between taqsim WaterSystem and IHA computation."""

from datetime import date

import numpy as np
import pytest
from taqsim.node import TimeSeries, WaterOutput
from taqsim.testing import make_edge, make_reach, make_sink, make_source, make_system
from taqsim.time import Frequency

from fishy.iha.bridge import iha_from_reach
from fishy.iha.errors import (
    EmptyReachTraceError,
    MissingStartDateError,
    NonDailyFrequencyError,
    NotAReachError,
    ReachNotFoundError,
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
    """Simulated daily Source -> Reach -> Sink system with natural tags."""
    system = make_system(
        make_source("source", n_steps=N_STEPS, inflow=_variable_inflow(N_STEPS)),
        make_reach("reach"),
        make_sink("sink"),
        make_edge("e_in", "source", "reach", tags=frozenset({"natural"})),
        make_edge("e_out", "reach", "sink", tags=frozenset({"natural"})),
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
        make_reach("reach"),
        make_sink("sink"),
        make_edge("e_in", "source", "reach"),
        make_edge("e_out", "reach", "sink"),
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
        make_reach("reach"),
        make_sink("sink"),
        make_edge("e_in", "source", "reach"),
        make_edge("e_out", "reach", "sink"),
        frequency=Frequency.DAILY,
        validate=False,
    )
    system.simulate(N_STEPS)
    return system


@pytest.fixture
def unsimulated_system():
    """Daily system that has not been simulated — Reach has no WaterOutput events."""
    return make_system(
        make_source("source", n_steps=N_STEPS),
        make_reach("reach"),
        make_sink("sink"),
        make_edge("e_in", "source", "reach"),
        make_edge("e_out", "reach", "sink"),
        frequency=Frequency.DAILY,
        start_date=date(2020, 1, 1),
        validate=False,
    )


class TestValidation:
    def test_non_daily_raises(self, monthly_system) -> None:
        with pytest.raises(NonDailyFrequencyError, match="365"):
            iha_from_reach(monthly_system, "reach")

    def test_missing_start_date_raises(self, no_start_date_system) -> None:
        with pytest.raises(MissingStartDateError, match="start_date"):
            iha_from_reach(no_start_date_system, "reach")

    def test_reach_not_found_raises(self, daily_system) -> None:
        with pytest.raises(ReachNotFoundError, match="nonexistent"):
            iha_from_reach(daily_system, "nonexistent")

    def test_reach_not_found_shows_available(self, daily_system) -> None:
        with pytest.raises(ReachNotFoundError, match="reach"):
            iha_from_reach(daily_system, "nonexistent")

    def test_not_a_reach_raises(self, daily_system) -> None:
        with pytest.raises(NotAReachError, match="Sink"):
            iha_from_reach(daily_system, "sink")

    def test_empty_trace_raises(self, unsimulated_system) -> None:
        with pytest.raises(EmptyReachTraceError, match="reach"):
            iha_from_reach(unsimulated_system, "reach")


class TestConversion:
    def test_returns_iha_result(self, daily_system) -> None:
        result = iha_from_reach(daily_system, "reach")
        assert isinstance(result, IHAResult)

    def test_has_correct_shape(self, daily_system) -> None:
        result = iha_from_reach(daily_system, "reach")
        assert result.values.shape[1] == 33

    def test_years_populated(self, daily_system) -> None:
        result = iha_from_reach(daily_system, "reach")
        assert len(result.years) >= 1

    def test_extracted_flow_matches_inflow(self) -> None:
        """Constant-inflow source through Reach should produce matching trace values."""
        from fishy.iha.types import PulseThresholds

        system = make_system(
            make_source("source", n_steps=N_STEPS, inflow=TimeSeries(values=[100.0] * N_STEPS)),
            make_reach("reach"),
            make_sink("sink"),
            make_edge("e_in", "source", "reach", tags=frozenset({"natural"})),
            make_edge("e_out", "reach", "sink", tags=frozenset({"natural"})),
            frequency=Frequency.DAILY,
            start_date=date(2020, 1, 1),
            validate=False,
        )
        system.simulate(N_STEPS)
        result = iha_from_reach(system, "reach", pulse_thresholds=PulseThresholds(low=50.0, high=150.0))
        # All daily values should be 100.0
        assert result.values.shape[0] >= 1
        assert np.allclose(result.values[0, 0], 100.0, rtol=1e-6)  # Jan mean

    def test_reach_emits_water_output(self, daily_system) -> None:
        """Reach node should have WaterOutput events after simulation."""
        reach = daily_system.nodes["reach"]
        outputs = list(reach.events_of_type(WaterOutput))
        assert len(outputs) > 0
        assert all(hasattr(e, "amount") for e in outputs)


class TestEndToEnd:
    def test_full_pipeline(self, daily_system) -> None:
        result = iha_from_reach(daily_system, "reach")
        assert isinstance(result, IHAResult)
        assert result.values.shape[0] >= 1
        assert result.values.shape[1] == 33
        # Years should be in the 2020 range
        assert all(2020 <= y <= 2022 for y in result.years)

    def test_custom_pulse_thresholds(self, daily_system) -> None:
        from fishy.iha.types import PulseThresholds

        thresholds = PulseThresholds(low=10.0, high=90.0)
        result = iha_from_reach(daily_system, "reach", pulse_thresholds=thresholds)
        assert result.pulse_thresholds == thresholds
