"""mean_discharge : WaterVolume × GregorianInterval → Flow; units normalise exactly."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction

from fishy.time import Interval

type Number = Fraction | Decimal | int | float | str


def finite_number(value: Number) -> Fraction:
    """Parse decimal display floats without carrying binary arithmetic artefacts."""
    if isinstance(value, bool):
        raise TypeError("a physical amount cannot be boolean")
    if isinstance(value, Fraction):
        return value
    try:
        return Fraction(str(value))
    except (ValueError, OverflowError, ZeroDivisionError) as error:
        raise ValueError("physical amount must be finite") from error


@dataclass(frozen=True, init=False)
class Flow:
    """Nonnegative interval mean discharge, canonically m3/s."""

    value: Fraction

    def __init__(self, value: Number, unit: str = "m3/s") -> None:
        if unit not in ("m3/s", "l/s"):
            raise ValueError(f"unsupported discharge unit {unit!r}")
        amount = finite_number(value) / (1000 if unit == "l/s" else 1)
        if amount < 0:
            raise ValueError("nonnegative-flow profile refuses negative discharge")
        object.__setattr__(self, "value", amount)


@dataclass(frozen=True, init=False)
class Elevation:
    """Signed elevation above sea level, canonically metres."""

    metres: Fraction

    def __init__(self, metres: Number) -> None:
        object.__setattr__(self, "metres", finite_number(metres))


@dataclass(frozen=True, init=False)
class Volume:
    """Nonnegative water volume, canonically m3."""

    value: Fraction

    def __init__(self, value: Number, unit: str = "m3") -> None:
        if unit not in ("m3", "l"):
            raise ValueError(f"unsupported volume unit {unit!r}")
        amount = finite_number(value) / (1000 if unit == "l" else 1)
        if amount < 0:
            raise ValueError("water volume cannot be negative")
        object.__setattr__(self, "value", amount)


@dataclass(frozen=True)
class FlowBounds:
    lower: Flow
    upper: Flow
    meaning: str
    source: str
    dependence: str

    def __post_init__(self) -> None:
        if not isinstance(self.lower, Flow) or not isinstance(self.upper, Flow):
            raise TypeError("uncertainty bounds require Flow")
        if self.upper.value < self.lower.value:
            raise ValueError("uncertainty bounds must be ordered")
        if not all(isinstance(s, str) and s.strip() for s in (self.meaning, self.source, self.dependence)):
            raise ValueError("uncertainty requires meaning, source and dependence; precision is not uncertainty")


class StateVariable(StrEnum):
    STAGE = "stage"
    VELOCITY = "velocity"
    EXCHANGE = "exchange"
    TEMPERATURE = "temperature"


@dataclass(frozen=True, init=False)
class SignedState:
    """Supported signed specialist quantity; no inferred discharge-state relation."""

    variable: StateVariable
    value: Fraction
    unit: str
    domain: str

    def __init__(self, variable: StateVariable, value: Number, unit: str, domain: str) -> None:
        units = {
            StateVariable.STAGE: "m",
            StateVariable.VELOCITY: "m/s",
            StateVariable.EXCHANGE: "m3/s",
            StateVariable.TEMPERATURE: "degC",
        }
        if not isinstance(variable, StateVariable) or unit != units[variable]:
            raise ValueError("incompatible state variable/unit")
        if not isinstance(domain, str) or not domain.strip():
            raise ValueError("signed state requires a declared domain/sign convention")
        object.__setattr__(self, "variable", variable)
        object.__setattr__(self, "value", finite_number(value))
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "domain", domain)


def mean_discharge(volume: Volume, interval: Interval) -> Flow:
    return Flow(volume.value / interval.seconds)


def interval_volume(flow: Flow, interval: Interval) -> Volume:
    return Volume(flow.value * interval.seconds)
