"""statutory_minimum : Q347Flow → StartingResidualFlow (literal Swiss Art. 31(1))."""

from dataclasses import dataclass
from fractions import Fraction

from fishy.low_flow import Q347Estimate
from fishy.quantities import Flow

SOURCE = "GSchG 2025-08-01 Art. 31(1); literal anchors and marginal rates"


def statutory_minimum(q347: Flow) -> Flow:
    """Uncapped exact table arithmetic, not a permit or an intake prescription."""
    if not isinstance(q347, Flow):
        raise TypeError("Q347 requires Flow")
    q = q347.value * 1000
    if q <= 60:
        result = Fraction(50)
    elif q < 160:
        result = 50 + Fraction("0.8") * (q - 60)
    elif q < 500:
        result = 130 + Fraction("0.44") * (q - 160)
    elif q < 2500:
        result = 280 + Fraction("0.31") * (q - 500)
    elif q < 10000:
        result = 900 + Fraction("0.213") * (q - 2500)
    elif q < 60000:
        result = 2500 + Fraction("0.15") * (q - 10000)
    else:
        result = Fraction(10000)
    return Flow(result, "l/s")


@dataclass(frozen=True)
class StartingMinimum:
    q347: Q347Estimate
    value: Flow
    source: str = SOURCE

    def __post_init__(self) -> None:
        if not isinstance(self.q347, Q347Estimate) or self.value != statutory_minimum(self.q347.value):
            raise ValueError("starting minimum must preserve the literal Q347 table")
        if self.source != SOURCE:
            raise ValueError("literal table source cannot be replaced")


def attributed_starting_minimum(estimate: Q347Estimate) -> StartingMinimum:
    return StartingMinimum(estimate, statutory_minimum(estimate.value))
