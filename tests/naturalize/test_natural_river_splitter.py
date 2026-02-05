"""Tests for NaturalRiverSplitter."""

import sys
from dataclasses import FrozenInstanceError, dataclass
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# Mock taqsim modules before importing fishy to avoid ModuleNotFoundError
# This must happen before any fishy imports
_taqsim_mock = ModuleType("taqsim")
_taqsim_mock.system = MagicMock()
_taqsim_mock.node = MagicMock()
_taqsim_mock.edge = MagicMock()
sys.modules.setdefault("taqsim", _taqsim_mock)
sys.modules.setdefault("taqsim.system", _taqsim_mock.system)
sys.modules.setdefault("taqsim.node", _taqsim_mock.node)
sys.modules.setdefault("taqsim.edge", _taqsim_mock.edge)

from fishy.naturalize.natural_river_splitter import NaturalRiverSplitter  # noqa: E402

# NATURAL_TAG constant - must match the value in types.py
NATURAL_TAG = "natural"


# Mock Splitter for testing split() method
@dataclass
class MockSplitter:
    """Mock Splitter node for testing."""

    id: str = "mock_splitter"


class TestConstruction:
    """Tests for NaturalRiverSplitter construction and validation."""

    def test_valid_fixed_ratios(self) -> None:
        """Fixed ratios summing to 1.0 should succeed."""
        rule = NaturalRiverSplitter(ratios={"a": 0.6, "b": 0.4})
        assert rule.ratios == {"a": 0.6, "b": 0.4}
        assert rule.cyclical is False
        assert not rule.is_time_varying

    def test_valid_single_branch(self) -> None:
        """Single branch with ratio 1.0 should succeed."""
        rule = NaturalRiverSplitter(ratios={"main": 1.0})
        assert rule.ratios == {"main": 1.0}

    def test_valid_time_varying_ratios(self) -> None:
        """Time-varying ratios summing to 1.0 at each timestep should succeed."""
        rule = NaturalRiverSplitter(
            ratios={
                "a": (0.6, 0.5, 0.7),
                "b": (0.4, 0.5, 0.3),
            }
        )
        assert rule.is_time_varying
        assert rule.num_timesteps == 3

    def test_valid_cyclical_ratios(self) -> None:
        """Cyclical time-varying ratios should succeed."""
        rule = NaturalRiverSplitter(
            ratios={
                "a": (0.6, 0.5),
                "b": (0.4, 0.5),
            },
            cyclical=True,
        )
        assert rule.cyclical is True

    def test_invalid_empty_ratios(self) -> None:
        """Empty ratios should raise ValueError."""
        with pytest.raises(ValueError, match="ratios cannot be empty"):
            NaturalRiverSplitter(ratios={})

    def test_invalid_sum_not_one_fixed(self) -> None:
        """Fixed ratios not summing to 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            NaturalRiverSplitter(ratios={"a": 0.6, "b": 0.3})

    def test_invalid_sum_not_one_time_varying(self) -> None:
        """Time-varying ratios not summing to 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            NaturalRiverSplitter(
                ratios={
                    "a": (0.6, 0.5),
                    "b": (0.3, 0.5),  # Sum is 0.9 at t=0
                }
            )

    def test_invalid_negative_ratio(self) -> None:
        """Negative ratios should raise ValueError."""
        with pytest.raises(ValueError, match=r"must be in \[0\.0, 1\.0\]"):
            NaturalRiverSplitter(ratios={"a": -0.1, "b": 1.1})

    def test_invalid_ratio_greater_than_one(self) -> None:
        """Ratios > 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match=r"must be in \[0\.0, 1\.0\]"):
            NaturalRiverSplitter(ratios={"a": 1.5, "b": -0.5})

    def test_invalid_mixed_types(self) -> None:
        """Mixed fixed and time-varying ratios should raise ValueError."""
        with pytest.raises(ValueError, match="same type"):
            NaturalRiverSplitter(
                ratios={
                    "a": 0.6,
                    "b": (0.4, 0.5),  # Mixed types
                }
            )

    def test_invalid_mismatched_tuple_lengths(self) -> None:
        """Time-varying ratios with different lengths should raise ValueError."""
        with pytest.raises(ValueError, match="same length"):
            NaturalRiverSplitter(
                ratios={
                    "a": (0.6, 0.5, 0.7),
                    "b": (0.4, 0.5),  # Different length
                }
            )

    def test_invalid_empty_tuple(self) -> None:
        """Empty ratio tuple should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            NaturalRiverSplitter(
                ratios={
                    "a": (),
                    "b": (),
                }
            )


class TestTagsAndMetadata:
    """Tests for tags and metadata access."""

    def test_has_natural_tag(self) -> None:
        """Should have NATURAL_TAG in __tags__."""
        assert NATURAL_TAG in NaturalRiverSplitter.__tags__

    def test_tags_method(self) -> None:
        """tags() method should return __tags__."""
        rule = NaturalRiverSplitter(ratios={"a": 1.0})
        assert rule.tags() == NaturalRiverSplitter.__tags__
        assert NATURAL_TAG in rule.tags()

    def test_metadata_method(self) -> None:
        """metadata() method should return __metadata__."""
        rule = NaturalRiverSplitter(ratios={"a": 1.0})
        meta = rule.metadata()
        assert "description" in meta
        assert meta.get("preserves_natural_flow") is True


class TestSplitBehavior:
    """Tests for the split() method."""

    def test_split_fixed_ratios(self) -> None:
        """Split with fixed ratios should distribute correctly."""
        rule = NaturalRiverSplitter(ratios={"a": 0.6, "b": 0.4})
        node = MockSplitter()

        result = rule.split(node, amount=100.0, t=0)

        assert result == {"a": 60.0, "b": 40.0}

    def test_split_fixed_ratios_same_at_any_timestep(self) -> None:
        """Fixed ratios should give same result at any timestep."""
        rule = NaturalRiverSplitter(ratios={"a": 0.7, "b": 0.3})
        node = MockSplitter()

        result_t0 = rule.split(node, amount=100.0, t=0)
        result_t5 = rule.split(node, amount=100.0, t=5)
        result_t100 = rule.split(node, amount=100.0, t=100)

        assert result_t0 == result_t5 == result_t100 == {"a": 70.0, "b": 30.0}

    def test_split_zero_amount(self) -> None:
        """Split with zero amount should return zeros."""
        rule = NaturalRiverSplitter(ratios={"a": 0.6, "b": 0.4})
        node = MockSplitter()

        result = rule.split(node, amount=0.0, t=0)

        assert result == {"a": 0.0, "b": 0.0}

    def test_split_time_varying(self) -> None:
        """Time-varying ratios should give different results per timestep."""
        rule = NaturalRiverSplitter(
            ratios={
                "a": (0.6, 0.5, 0.7),
                "b": (0.4, 0.5, 0.3),
            }
        )
        node = MockSplitter()

        result_t0 = rule.split(node, amount=100.0, t=0)
        result_t1 = rule.split(node, amount=100.0, t=1)
        result_t2 = rule.split(node, amount=100.0, t=2)

        assert result_t0 == {"a": 60.0, "b": 40.0}
        assert result_t1 == {"a": 50.0, "b": 50.0}
        assert result_t2 == {"a": 70.0, "b": 30.0}

    def test_split_time_varying_clamps_when_not_cyclical(self) -> None:
        """Non-cyclical time-varying should clamp to last value when t >= len."""
        rule = NaturalRiverSplitter(
            ratios={
                "a": (0.6, 0.5),
                "b": (0.4, 0.5),
            },
            cyclical=False,
        )
        node = MockSplitter()

        # t=2 and beyond should use the last values (t=1)
        result_t2 = rule.split(node, amount=100.0, t=2)
        result_t10 = rule.split(node, amount=100.0, t=10)

        assert result_t2 == {"a": 50.0, "b": 50.0}
        assert result_t10 == {"a": 50.0, "b": 50.0}

    def test_split_cyclical_wraps_around(self) -> None:
        """Cyclical ratios should wrap around when t >= len."""
        rule = NaturalRiverSplitter(
            ratios={
                "a": (0.6, 0.5),
                "b": (0.4, 0.5),
            },
            cyclical=True,
        )
        node = MockSplitter()

        # t=0 and t=2 should be the same (wrap around)
        result_t0 = rule.split(node, amount=100.0, t=0)
        result_t2 = rule.split(node, amount=100.0, t=2)
        result_t4 = rule.split(node, amount=100.0, t=4)

        assert result_t0 == result_t2 == result_t4 == {"a": 60.0, "b": 40.0}

        # t=1 and t=3 should be the same
        result_t1 = rule.split(node, amount=100.0, t=1)
        result_t3 = rule.split(node, amount=100.0, t=3)

        assert result_t1 == result_t3 == {"a": 50.0, "b": 50.0}


class TestImmutability:
    """Tests for frozen dataclass behavior."""

    def test_frozen_ratios_cannot_be_modified(self) -> None:
        """Attempting to modify ratios should raise FrozenInstanceError."""
        rule = NaturalRiverSplitter(ratios={"a": 0.6, "b": 0.4})

        with pytest.raises(FrozenInstanceError):
            rule.ratios = {"c": 1.0}  # type: ignore

    def test_frozen_cyclical_cannot_be_modified(self) -> None:
        """Attempting to modify cyclical should raise FrozenInstanceError."""
        rule = NaturalRiverSplitter(ratios={"a": 1.0})

        with pytest.raises(FrozenInstanceError):
            rule.cyclical = True  # type: ignore
