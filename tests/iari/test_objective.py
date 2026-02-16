"""Tests for IARI objective factory."""

import numpy as np
import pytest
from fishy.iari.objective import iari_objective
from taqsim.objective import Objective

from fishy.iari._deviation import bands_from_iha
from fishy.iari.types import NaturalBands
from fishy.iha.bridge import iha_from_reach
from fishy.iha.types import PulseThresholds


class TestIARIObjective:
    def test_returns_objective(self) -> None:
        bands = NaturalBands(
            q25=np.zeros(33),
            q75=np.ones(33),
            pulse_thresholds=PulseThresholds(low=5.0, high=50.0),
        )
        obj = iari_objective(bands, "my_reach")
        assert isinstance(obj, Objective)

    def test_name_includes_reach_id(self) -> None:
        bands = NaturalBands(
            q25=np.zeros(33),
            q75=np.ones(33),
            pulse_thresholds=PulseThresholds(low=5.0, high=50.0),
        )
        obj = iari_objective(bands, "my_reach")
        assert obj.name == "my_reach.iari"

    def test_direction_is_minimize(self) -> None:
        bands = NaturalBands(
            q25=np.zeros(33),
            q75=np.ones(33),
            pulse_thresholds=PulseThresholds(low=5.0, high=50.0),
        )
        obj = iari_objective(bands, "my_reach")
        assert obj.direction == "minimize"

    def test_priority_passed_through(self) -> None:
        bands = NaturalBands(
            q25=np.zeros(33),
            q75=np.ones(33),
            pulse_thresholds=PulseThresholds(low=5.0, high=50.0),
        )
        obj = iari_objective(bands, "my_reach", priority=3)
        assert obj.priority == 3

    def test_evaluate_returns_float(self, simple_daily_system) -> None:
        iha = iha_from_reach(simple_daily_system, "reach")
        bands = bands_from_iha(iha)
        obj = iari_objective(bands, "reach")
        score = obj.evaluate(simple_daily_system)
        assert isinstance(score, float)

    def test_natural_vs_itself_near_zero(self, simple_daily_system) -> None:
        iha = iha_from_reach(simple_daily_system, "reach")
        bands = bands_from_iha(iha)
        obj = iari_objective(bands, "reach")
        score = obj.evaluate(simple_daily_system)
        assert score == pytest.approx(0.0, abs=1e-10)
