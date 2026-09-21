"""sampling_intervals : SamplingPlan × ReplicateSeries* × TailProbability → SamplingResult*.

Also propagate_linear_covariance : LinearFlowCoefficients × FlowCovariance → FlowVariance.
External stationary sampling only; neither operation establishes scientific acceptance.
"""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from fishy.quantities import Flow, Number, finite_number


def _text(*values: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("nonempty evidence declarations are required")


@dataclass(frozen=True)
class SamplingPlan:
    """One shared index schedule for all related quantities; zero-based annual indices.

    Completeness and estimator refitting are external evidence declarations, not
    claims that Fishy inspected the underlying observations or reran a generator.
    """

    years: tuple[int, ...]
    block_length: int
    replicate_count: int
    indices: tuple[tuple[int, ...], ...]
    generator: str
    generator_version: str
    seed: int
    start_method: Literal["uniform"]
    estimator: str
    estimator_version: str
    complete_year_evidence: str
    independence_justification: str | None = None
    dependence_diagnostics: str | None = None
    block_length_sensitivity: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "years", tuple(self.years))
        object.__setattr__(self, "indices", tuple(tuple(row) for row in self.indices))
        n = len(self.years)
        if n < 2 or any(type(year) is not int for year in self.years):
            raise ValueError("at least two integer accounting years required")
        if any(b != a + 1 for a, b in zip(self.years, self.years[1:], strict=False)):
            raise ValueError("annual chronology must be consecutive and ordered")
        if type(self.block_length) is not int or not 1 <= self.block_length < n:
            raise ValueError("integer block length must satisfy 1 <= L < n")
        if type(self.replicate_count) is not int or self.replicate_count < 2:
            raise ValueError("integer replicate count must be at least two")
        if type(self.seed) is not int or self.start_method != "uniform":
            raise ValueError("declare an integer seed and uniform block starts")
        _text(
            self.generator, self.generator_version, self.estimator, self.estimator_version, self.complete_year_evidence
        )
        if self.block_length == 1:
            if self.independence_justification is None:
                raise ValueError("L=1 requires independence justification")
            _text(self.independence_justification)
        else:
            if self.dependence_diagnostics is None or self.block_length_sensitivity is None:
                raise ValueError("L>1 requires dependence diagnostics and block-length sensitivity")
            _text(self.dependence_diagnostics, self.block_length_sensitivity)
        if len(self.indices) != self.replicate_count:
            raise ValueError("index schedule must retain every replicate")
        for row in self.indices:
            if len(row) != n or any(type(i) is not int or not 0 <= i < n for i in row):
                raise ValueError("replicate indices must have chronological population length and valid indices")
            for offset in range(0, n, self.block_length):
                for step in range(1, min(self.block_length, n - offset)):
                    if row[offset + step] != (row[offset] + step) % n:
                        raise ValueError("indices must be concatenated circular moving blocks truncated to n")


@dataclass(frozen=True)
class ReplicateFailure:
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if not self.reasons:
            raise ValueError("failed replicate requires reasons")
        _text(*self.reasons)


@dataclass(frozen=True)
class ReplicateSeries:
    """Estimates in shared-plan replicate order, with explicit estimator attribution."""

    quantity: str
    estimator: str
    estimator_version: str
    refit_evidence: str
    indices: tuple[tuple[int, ...], ...]
    outcomes: tuple[Flow | ReplicateFailure, ...]

    def __post_init__(self) -> None:
        _text(self.quantity, self.estimator, self.estimator_version, self.refit_evidence)
        object.__setattr__(self, "indices", tuple(tuple(row) for row in self.indices))
        object.__setattr__(self, "outcomes", tuple(self.outcomes))
        if any(not isinstance(item, Flow | ReplicateFailure) for item in self.outcomes):
            raise TypeError("replicates require Flow estimates or explicit failures")


@dataclass(frozen=True)
class SamplingInterval:
    lower: Flow
    upper: Flow
    confidence: Fraction
    scope: Literal["conditional stationary sampling"] = "conditional stationary sampling"


@dataclass(frozen=True)
class SamplingResult:
    plan: SamplingPlan
    series: ReplicateSeries
    alpha: Fraction
    interval: SamplingInterval | None

    @property
    def failures(self) -> tuple[tuple[int, ReplicateFailure], ...]:
        """Zero-based replicate identities and all supplied reasons."""
        return tuple((i, value) for i, value in enumerate(self.series.outcomes) if isinstance(value, ReplicateFailure))

    @property
    def failed_count(self) -> int:
        return len(self.failures)


def _quantile(values: list[Fraction], probability: Fraction) -> Flow:
    index = (len(values) - 1) * probability
    lo = index.numerator // index.denominator
    hi = min(lo + 1, len(values) - 1)
    return Flow(values[lo] + (index - lo) * (values[hi] - values[lo]))


def sampling_intervals(
    plan: SamplingPlan,
    series: tuple[ReplicateSeries, ...],
    alpha: Number,
) -> tuple[SamplingResult, ...]:
    """Check caller results and compute type-7 intervals, never refit or resample.

    Failure blocks that quantity's interval; it does not discard successes or
    disable a separately supported related quantity.
    """
    tail = finite_number(alpha)
    if not 0 < tail < 1:
        raise ValueError("alpha must lie strictly between zero and one")
    if not series or len({item.quantity for item in series}) != len(series):
        raise ValueError("supply nonempty uniquely identified quantities")
    results = []
    for item in series:
        if item.indices != plan.indices:
            raise ValueError("related quantities must use the same sampled year indices")
        if (item.estimator, item.estimator_version) != (plan.estimator, plan.estimator_version):
            raise ValueError("each replicate must refit the same declared estimator/version")
        if len(item.outcomes) != plan.replicate_count:
            raise ValueError("all replicate outcomes, including failures, must be retained")
        values = sorted(value.value for value in item.outcomes if isinstance(value, Flow))
        interval = None
        if len(values) == plan.replicate_count:
            interval = SamplingInterval(_quantile(values, tail / 2), _quantile(values, 1 - tail / 2), 1 - tail)
        results.append(SamplingResult(plan, item, tail, interval))
    return tuple(results)


@dataclass(frozen=True, init=False)
class FlowCovariance:
    """Exact symmetric PSD covariance, normalised to (m3/s)^2.

    All variables must be flows in the declared common unit. Mixed variable
    dimensions require a different, explicitly supported propagation model.
    """

    matrix: tuple[tuple[Fraction, ...], ...]
    source: str

    def __init__(self, matrix: tuple[tuple[Number, ...], ...], unit: str, source: str) -> None:
        _text(source)
        if unit not in ("(m3/s)^2", "(l/s)^2"):
            raise ValueError("covariance must have compatible squared-flow units")
        divisor = 1000000 if unit == "(l/s)^2" else 1
        values = tuple(tuple(finite_number(value) / divisor for value in row) for row in matrix)
        n = len(values)
        if not n or any(len(row) != n for row in values):
            raise ValueError("covariance must be nonempty and square")
        if any(values[i][j] != values[j][i] for i in range(n) for j in range(n)):
            raise ValueError("covariance must be exactly symmetric")
        # Exact Schur complements: a zero diagonal of a PSD matrix has a zero row.
        work = [list(row) for row in values]
        for k in range(n):
            pivot = work[k][k]
            if pivot < 0 or (pivot == 0 and any(work[k][j] != 0 for j in range(k + 1, n))):
                raise ValueError("covariance must be positive semidefinite")
            if pivot:
                for i in range(k + 1, n):
                    for j in range(k + 1, n):
                        work[i][j] -= work[i][k] * work[k][j] / pivot
        object.__setattr__(self, "matrix", values)
        object.__setattr__(self, "source", source)


@dataclass(frozen=True, init=False)
class LinearFlowCoefficients:
    """Dimensionless signed coefficients of a linear balance of flows."""

    values: tuple[Fraction, ...]

    def __init__(self, values: tuple[Number, ...]) -> None:
        if not values:
            raise ValueError("linear balance requires coefficients")
        object.__setattr__(self, "values", tuple(finite_number(value) for value in values))


@dataclass(frozen=True)
class FlowVariance:
    squared_m3_per_s: Fraction
    covariance: FlowCovariance
    coefficients: LinearFlowCoefficients


def propagate_linear_covariance(coefficients: LinearFlowCoefficients, covariance: FlowCovariance) -> FlowVariance:
    """Return cᵀΣc, not a verdict half-width or a nonlinear uncertainty model."""
    c = coefficients.values
    if len(c) != len(covariance.matrix):
        raise ValueError("coefficient and covariance dimensions must match")
    variance = sum((a * covariance.matrix[i][j] * b for i, a in enumerate(c) for j, b in enumerate(c)), Fraction())
    return FlowVariance(variance, covariance, coefficients)
