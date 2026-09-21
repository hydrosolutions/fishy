"""low_flow_frequency : LowFlowReturnPeriod → AnnualMinimumTailProbability (pure).

The recurrence identity applies to a declared annual or seasonal minimum
population, not daily exceedance or permission to breach a flow requirement.
"""

from dataclasses import dataclass
from fractions import Fraction

from fishy.quantities import Number, finite_number


@dataclass(frozen=True, init=False)
class LowFlowReturnPeriod:
    """Finite recurrence interval in years, strictly greater than one year."""

    years: Fraction

    def __init__(self, years: Number) -> None:
        value = finite_number(years)
        if value <= 1:
            raise ValueError("low-flow return period must exceed one year")
        object.__setattr__(self, "years", value)

    @property
    def nonexceedance_probability(self) -> Fraction:
        """Lower-tail probability u = 1/Tr for the selected minimum population."""
        return 1 / self.years

    @property
    def exceedance_probability(self) -> Fraction:
        """Exact complementary probability P = 1-u, not daily exceedance."""
        return 1 - self.nonexceedance_probability
