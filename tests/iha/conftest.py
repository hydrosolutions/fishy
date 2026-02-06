"""Shared fixtures for IHA tests."""

import sys
from types import ModuleType


class _StubModule(ModuleType):
    """Module stub that returns a dummy class for any attribute access."""

    def __getattr__(self, name: str) -> type:
        return type(name, (), {})


# Stub taqsim before fishy.__init__ tries to import fishy.naturalize.
# The IHA subpackage has no dependency on taqsim, but importing
# fishy.iha.* triggers the top-level fishy package which eagerly
# imports fishy.naturalize (which requires taqsim).
if "taqsim" not in sys.modules:
    for _name in ("taqsim", "taqsim.node", "taqsim.edge", "taqsim.system"):
        sys.modules.setdefault(_name, _StubModule(_name))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

DATES_2023 = np.arange("2023-01-01", "2024-01-01", dtype="datetime64[D]")


@pytest.fixture
def constant_flow() -> dict:
    return {
        "q": np.full(365, 10.0),
        "dates": DATES_2023.copy(),
        "expected": {
            "monthly_means": dict.fromkeys(range(1, 13), 10.0),
            "MIN_1DAY": 10.0,
            "MAX_1DAY": 10.0,
            "MIN_3DAY": 10.0,
            "MAX_3DAY": 10.0,
            "MIN_7DAY": 10.0,
            "MAX_7DAY": 10.0,
            "MIN_30DAY": 10.0,
            "MAX_30DAY": 10.0,
            "MIN_90DAY": 10.0,
            "MAX_90DAY": 10.0,
            "BFI": 1.0,
            "ZERO_FLOW_DAYS": 0,
            "RISE_RATE": 0.0,
            "FALL_RATE": 0.0,
            "REVERSALS": 0,
        },
    }


@pytest.fixture
def step_flow() -> dict:
    q = np.array([5.0] * 100 + [20.0] * 165 + [5.0] * 100)
    return {
        "q": q,
        "dates": DATES_2023.copy(),
        "expected": {
            "MIN_1DAY": 5.0,
            "MAX_1DAY": 20.0,
            "DATE_OF_MIN": 1,
            "DATE_OF_MAX": 101,
        },
    }


@pytest.fixture
def seasonal_sine() -> dict:
    q = 50.0 + 40.0 * np.sin(2 * np.pi * np.arange(365) / 365 - np.pi / 2)
    return {
        "q": q,
        "dates": DATES_2023.copy(),
        "expected": {
            "MAX_1DAY": pytest.approx(90.0, abs=0.5),
            "MIN_1DAY": pytest.approx(10.0, abs=0.5),
            "DATE_OF_MAX": pytest.approx(183, abs=2),
        },
    }


@pytest.fixture
def triangle_wave() -> dict:
    q = np.concatenate([np.linspace(10, 100, 100), np.linspace(100, 10, 265)])
    return {
        "q": q,
        "dates": DATES_2023.copy(),
        "expected": {
            "REVERSALS": 1,
            "RISE_RATE": pytest.approx(90.0 / 99.0, rel=1e-4),
            "FALL_RATE": pytest.approx(-90.0 / 264.0, rel=1e-4),
        },
    }


@pytest.fixture
def pulse_flow() -> dict:
    tile = np.tile(
        np.concatenate([np.full(10, 5.0), np.full(10, 50.0)]),
        365 // 20,
    )
    q = np.concatenate([tile, np.full(5, 5.0)])
    return {
        "q": q,
        "dates": DATES_2023.copy(),
        "expected": {
            "LOW_PULSE_COUNT": 19,
            "HIGH_PULSE_COUNT": 18,
            "HIGH_PULSE_DURATION": 10.0,
        },
    }


@pytest.fixture
def zero_flow() -> dict:
    return {
        "q": np.zeros(365),
        "dates": DATES_2023.copy(),
        "expected": {
            "monthly_means": dict.fromkeys(range(1, 13), 0.0),
            "BFI": np.nan,
            "ZERO_FLOW_DAYS": 365,
            "RISE_RATE": 0.0,
            "FALL_RATE": 0.0,
            "REVERSALS": 0,
        },
    }


@pytest.fixture
def ramp_flow() -> dict:
    q = np.linspace(1, 100, 365)
    return {
        "q": q,
        "dates": DATES_2023.copy(),
        "expected": {
            "RISE_RATE": pytest.approx(99.0 / 364.0, rel=1e-4),
            "FALL_RATE": 0.0,
            "REVERSALS": 0,
        },
    }
