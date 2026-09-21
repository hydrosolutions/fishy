"""discharge_quantile : DischargePopulation × ExceedanceProbability → QuantileEvidence (pure).

Shared statistical operators; callers retain whether values are annual means or
annual/seasonal duration minima. A fit confers no scientific acceptance.
"""

from dataclasses import dataclass
from fractions import Fraction
from math import exp, isfinite, log, sqrt
from statistics import NormalDist

from fishy.quantities import Flow, Number, finite_number


@dataclass(frozen=True, init=False)
class ExceedanceProbability:
    value: Fraction

    def __init__(self, value: Number) -> None:
        probability = finite_number(value)
        if not 0 < probability < 1:
            raise ValueError("exceedance probability must be strictly between zero and one")
        object.__setattr__(self, "value", probability)


@dataclass(frozen=True)
class RankNeighbour:
    rank: int
    probability: ExceedanceProbability
    discharge: Flow


@dataclass(frozen=True)
class DistributionJump:
    discharge: Flow
    empirical_left: float
    empirical_right: float
    fitted_left: float
    fitted_right: float

    @property
    def distance(self) -> float:
        return max(abs(self.empirical_left - self.fitted_left), abs(self.empirical_right - self.fitted_right))


@dataclass(frozen=True)
class DischargeFit:
    zero_fraction: Fraction
    log_mean: float | None
    log_variance: float | None
    jumps: tuple[DistributionJump, ...]
    reasons: tuple[str, ...]

    @property
    def distribution_distance(self) -> float | None:
        return max(j.distance for j in self.jumps) if self.jumps else None


def fit_discharge_distribution(values: tuple[Flow, ...]) -> DischargeFit:
    if not values or any(not isinstance(v, Flow) for v in values):
        raise ValueError("nonempty Flow population required")
    positive = [v.value for v in values if v.value > 0]
    pi0 = Fraction(len(values) - len(positive), len(values))
    if len(positive) < 2:
        return DischargeFit(pi0, None, None, (), ("at least two positive observations required",))
    # log(Fraction) can overflow before logarithm; subtract integer logarithms instead.
    logs = [log(v.numerator) - log(v.denominator) for v in positive]
    mu = sum(logs) / len(logs)
    variance = sum((z - mu) ** 2 for z in logs) / len(logs)
    if variance <= 0 or not isfinite(variance):
        return DischargeFit(pi0, None, None, (), ("positive log standard deviation required",))
    ordered = sorted(v.value for v in values)
    jumps = []
    for value in sorted(set(ordered)):
        left = sum(x < value for x in ordered) / len(ordered)
        right = sum(x <= value for x in ordered) / len(ordered)
        fitted = (
            float(pi0)
            if value == 0
            else float(pi0)
            + float(1 - pi0) * NormalDist(mu, sqrt(variance)).cdf(log(value.numerator) - log(value.denominator))
        )
        jumps.append(DistributionJump(Flow(value), left, right, 0.0 if value == 0 else fitted, fitted))
    return DischargeFit(
        pi0,
        mu,
        variance,
        tuple(jumps),
        ("candidate fit is not tail validation; zero frequency is not proof of perennial flow",),
    )


def empirical_quantile(
    population: tuple[Flow, ...], target: ExceedanceProbability
) -> tuple[Flow | None, tuple[RankNeighbour, ...], tuple[str, ...]]:
    values = sorted(population, key=lambda v: v.value, reverse=True)
    n = len(values)
    rank = target.value * (n + 1)
    neighbours: tuple[RankNeighbour, ...] = ()
    value = None
    reasons: tuple[str, ...] = ()
    if not 1 <= rank <= n:
        reasons = ("not computable by ranking: target outside Weibull support",)
    else:
        lower = rank.numerator // rank.denominator
        upper = lower if rank.denominator == 1 else lower + 1
        neighbours = tuple(
            RankNeighbour(i, ExceedanceProbability(Fraction(i, n + 1)), values[i - 1])
            for i in dict.fromkeys((lower, upper))
        )
        value = Flow(values[lower - 1].value + (rank - lower) * (values[upper - 1].value - values[lower - 1].value))
    return value, neighbours, reasons


def fitted_quantile(
    population: tuple[Flow, ...], target: ExceedanceProbability
) -> tuple[Flow | None, DischargeFit, tuple[str, ...]]:
    fit = fit_discharge_distribution(population)
    value = None
    reasons = fit.reasons
    if fit.log_variance is not None and fit.log_mean is not None:
        u = 1 - target.value
        if u <= fit.zero_fraction:
            value = Flow(0)
        else:
            lower_probability = (u - fit.zero_fraction) / (1 - fit.zero_fraction)
            upper_probability = target.value / (1 - fit.zero_fraction)
            probability = float(min(lower_probability, upper_probability))
            if not 0 < probability < 1:
                reasons = (*reasons, "target exceeds floating-point quantile resolution")
            else:
                normal = NormalDist().inv_cdf(probability)
                if upper_probability < lower_probability:
                    normal = -normal
                exponent = fit.log_mean + sqrt(fit.log_variance) * normal
                try:
                    quantile = exp(exponent)
                except OverflowError:
                    quantile = float("inf")
                if isfinite(quantile) and quantile > 0:
                    value = Flow(quantile)
                else:
                    reasons = (*reasons, "positive quantile outside floating-point range; not substituted with zero")
    return value, fit, reasons
