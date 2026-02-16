"""Tests for IARI objective factory."""

import numpy as np
import pytest
from taqsim.objective import Objective

from fishy.iari._deviation import bands_from_iha
from fishy.iari.objective import composite_iari_objective, iari_objective
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


class TestCompositeIARIObjective:
    # ---- Tests that do NOT need a system fixture ----

    def test_returns_objective(self) -> None:
        bands = NaturalBands(
            q25=np.zeros(33),
            q75=np.ones(33),
            pulse_thresholds=PulseThresholds(low=5.0, high=50.0),
        )
        obj = composite_iari_objective({"r": bands})
        assert isinstance(obj, Objective)

    def test_default_name(self) -> None:
        bands = NaturalBands(
            q25=np.zeros(33),
            q75=np.ones(33),
            pulse_thresholds=PulseThresholds(low=5.0, high=50.0),
        )
        obj = composite_iari_objective({"r": bands})
        assert obj.name == "iari"

    def test_custom_name(self) -> None:
        bands = NaturalBands(
            q25=np.zeros(33),
            q75=np.ones(33),
            pulse_thresholds=PulseThresholds(low=5.0, high=50.0),
        )
        obj = composite_iari_objective({"r": bands}, name="my.iari")
        assert obj.name == "my.iari"

    def test_direction_is_minimize(self) -> None:
        bands = NaturalBands(
            q25=np.zeros(33),
            q75=np.ones(33),
            pulse_thresholds=PulseThresholds(low=5.0, high=50.0),
        )
        obj = composite_iari_objective({"r": bands})
        assert obj.direction == "minimize"

    def test_priority_passed_through(self) -> None:
        bands = NaturalBands(
            q25=np.zeros(33),
            q75=np.ones(33),
            pulse_thresholds=PulseThresholds(low=5.0, high=50.0),
        )
        obj = composite_iari_objective({"r": bands}, priority=5)
        assert obj.priority == 5

    def test_empty_bands_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            composite_iari_objective({})

    def test_weight_keys_mismatch_raises(self) -> None:
        bands_a = NaturalBands(
            q25=np.zeros(33),
            q75=np.ones(33),
            pulse_thresholds=PulseThresholds(low=5.0, high=50.0),
        )
        bands_b = NaturalBands(
            q25=np.zeros(33),
            q75=np.ones(33),
            pulse_thresholds=PulseThresholds(low=5.0, high=50.0),
        )
        with pytest.raises(ValueError, match="must match"):
            composite_iari_objective(
                {"a": bands_a, "b": bands_b},
                weights={"a": 1.0, "c": 1.0},
            )

    def test_negative_weight_raises(self) -> None:
        bands = NaturalBands(
            q25=np.zeros(33),
            q75=np.ones(33),
            pulse_thresholds=PulseThresholds(low=5.0, high=50.0),
        )
        with pytest.raises(ValueError, match="positive"):
            composite_iari_objective({"r": bands}, weights={"r": -1.0})

    # ---- Tests that need system fixtures ----

    def test_evaluate_returns_float(self, multi_reach_system, multi_reach_bands) -> None:
        obj = composite_iari_objective(multi_reach_bands)
        score = obj.evaluate(multi_reach_system)
        assert isinstance(score, float)

    def test_natural_vs_itself_near_zero(self, multi_reach_system, multi_reach_bands) -> None:
        obj = composite_iari_objective(multi_reach_bands)
        score = obj.evaluate(multi_reach_system)
        assert score == pytest.approx(0.0, abs=1e-10)

    def test_single_reach_matches_iari_objective(self, simple_daily_system) -> None:
        iha = iha_from_reach(simple_daily_system, "reach")
        bands = bands_from_iha(iha)
        single_obj = iari_objective(bands, "reach")
        composite_obj = composite_iari_objective({"reach": bands})
        assert composite_obj.evaluate(simple_daily_system) == pytest.approx(single_obj.evaluate(simple_daily_system))

    def test_equal_weights_is_arithmetic_mean(self, multi_reach_system, multi_reach_bands) -> None:
        individual = {
            rid: iari_objective(multi_reach_bands[rid], rid).evaluate(multi_reach_system)
            for rid in ["reach1", "reach2", "reach3"]
        }
        expected = sum(individual.values()) / len(individual)
        obj = composite_iari_objective(multi_reach_bands)
        assert obj.evaluate(multi_reach_system) == pytest.approx(expected)

    def test_weighted_mean_computation(self, multi_reach_system, multi_reach_bands) -> None:
        individual = {
            rid: iari_objective(multi_reach_bands[rid], rid).evaluate(multi_reach_system)
            for rid in ["reach1", "reach2", "reach3"]
        }
        weights = {"reach1": 3.0, "reach2": 1.0, "reach3": 1.0}
        expected = (3.0 * individual["reach1"] + 1.0 * individual["reach2"] + 1.0 * individual["reach3"]) / 5.0
        obj = composite_iari_objective(multi_reach_bands, weights=weights)
        assert obj.evaluate(multi_reach_system) == pytest.approx(expected)

    def test_weights_normalized(self, multi_reach_system, multi_reach_bands) -> None:
        sub_bands = {k: multi_reach_bands[k] for k in ["reach1", "reach2"]}
        obj_a = composite_iari_objective(sub_bands, weights={"reach1": 2, "reach2": 8})
        obj_b = composite_iari_objective(sub_bands, weights={"reach1": 0.2, "reach2": 0.8})
        assert obj_a.evaluate(multi_reach_system) == pytest.approx(obj_b.evaluate(multi_reach_system))

    def test_score_is_non_negative(self, multi_reach_system, multi_reach_bands) -> None:
        obj = composite_iari_objective(multi_reach_bands)
        score = obj.evaluate(multi_reach_system)
        assert score >= 0.0

    def test_subset_of_reaches(self, multi_reach_system, multi_reach_bands) -> None:
        sub_bands = {k: multi_reach_bands[k] for k in ["reach1", "reach3"]}
        obj = composite_iari_objective(sub_bands)
        score = obj.evaluate(multi_reach_system)
        assert isinstance(score, float)
        assert score >= 0.0
