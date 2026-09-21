"""annual_estimate : AnnualReference × ExceedanceProbability → AnnualEstimate (pure).

Annual means use actual elapsed volume/duration. Ranking and the selected
zero-mixture candidate are distinct from scientific acceptance and daily shape.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from fractions import Fraction
from math import exp, isfinite, log, sqrt
from statistics import NormalDist

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    Provenance,
    ReferenceKind,
    permitted_use,
)
from fishy.flows import (
    Coverage,
    FlowSample,
    IntervalUse,
    Presence,
    aggregate_flow,
    check_flow_intervals,
    interval_use,
)
from fishy.quantities import Flow, Number, finite_number
from fishy.spatial import Location
from fishy.time import Interval


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty attribution required")


@dataclass(frozen=True, init=False)
class ExceedanceProbability:
    value: Fraction

    def __init__(self, value: Number) -> None:
        probability = finite_number(value)
        if not 0 < probability < 1:
            raise ValueError("exceedance probability must be strictly between zero and one")
        object.__setattr__(self, "value", probability)


class TrendTreatment(StrEnum):
    COMMON_CLIMATE = "supported_common_climate"
    TRANSFORMED = "supported_climate_transformation"
    UNTREATED = "untreated_genuine_trend"
    UNASSESSED = "unassessed"


@dataclass(frozen=True)
class AnnualExclusion:
    interval: Interval
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.interval, Interval):
            raise TypeError("exclusion requires Interval")
        _text(self.reason)


@dataclass(frozen=True)
class AnnualReference:
    observations: tuple[FlowSample, ...]
    reference_period: Interval
    climate_basis: str
    accounting_start_month: int
    utc_offset_minutes: int
    exclusions: tuple[AnnualExclusion, ...]
    trend: TrendTreatment
    climate_evidence: str

    def __post_init__(self) -> None:
        if not isinstance(self.observations, tuple) or any(not isinstance(s, FlowSample) for s in self.observations):
            raise TypeError("annual observations require an immutable tuple of FlowSample")
        if not isinstance(self.reference_period, Interval) or not isinstance(self.trend, TrendTreatment):
            raise TypeError("typed reference interval and trend required")
        if type(self.accounting_start_month) is not int or not 1 <= self.accounting_start_month <= 12:
            raise ValueError("accounting year starts on first day of a declared month")
        if type(self.utc_offset_minutes) is not int or not -1440 < self.utc_offset_minutes < 1440:
            raise ValueError("fixed UTC offset must be integer minutes within one day")
        _text(self.climate_basis)
        _text(self.climate_evidence)
        if not isinstance(self.exclusions, tuple) or any(not isinstance(e, AnnualExclusion) for e in self.exclusions):
            raise TypeError("exclusions require AnnualExclusion tuple")
        check_flow_intervals(self.observations)
        for sample in self.observations:
            if sample.provenance.reference_kind is None:
                raise ValueError("annual reference must declare natural/observed basis")
            if sample.presence is not Presence.PRESENT or sample.coverage is not Coverage.COMPLETE:
                raise ValueError("annual statistics require complete supported observations, never missing-as-zero")
            if interval_use(sample) is not IntervalUse.ELIGIBLE:
                raise ValueError("excluded warm-up cannot enter annual statistics")
        periods = tuple(s.interval for s in self.observations) + tuple(e.interval for e in self.exclusions)
        for period in periods:
            _check_year(period, self.accounting_start_month, self.utc_offset_minutes)
        ordered = sorted(periods, key=lambda p: p.start)
        if ordered[0].start != self.reference_period.start or ordered[-1].end != self.reference_period.end:
            raise ValueError("accepted and excluded years must account for the reference period")
        if any(a.end != b.start for a, b in zip(ordered, ordered[1:], strict=False)):
            raise ValueError("reference years overlap or a missing year lacks an exclusion")

    @property
    def location(self) -> Location:
        return self.observations[0].location

    @property
    def provenance(self) -> Provenance:
        return self.observations[0].provenance

    @property
    def accepted_years(self) -> tuple[Interval, ...]:
        return tuple(s.interval for s in self.observations)

    @property
    def values(self) -> tuple[Flow, ...]:
        return tuple(s.value for s in self.observations if s.value is not None)


@dataclass(frozen=True)
class ImportedAnnualReference:
    """Source-year identity for a specialist import without copying calibration data."""

    location: Location
    provenance: Provenance
    accepted_years: tuple[Interval, ...]
    reference_period: Interval
    climate_basis: str
    accounting_start_month: int
    utc_offset_minutes: int
    exclusions: tuple[AnnualExclusion, ...]
    trend: TrendTreatment
    climate_evidence: str

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location) or not isinstance(self.provenance, Provenance):
            raise TypeError("import requires typed location/provenance")
        if self.provenance.reference_kind is None:
            raise ValueError("import requires reference basis")
        if not isinstance(self.trend, TrendTreatment) or not isinstance(self.reference_period, Interval):
            raise TypeError("import requires typed trend/reference period")
        _text(self.climate_basis)
        _text(self.climate_evidence)
        if type(self.accounting_start_month) is not int or not 1 <= self.accounting_start_month <= 12:
            raise ValueError("invalid accounting start month")
        if type(self.utc_offset_minutes) is not int or not -1440 < self.utc_offset_minutes < 1440:
            raise ValueError("invalid fixed UTC offset")
        if (
            not isinstance(self.accepted_years, tuple)
            or not self.accepted_years
            or any(not isinstance(y, Interval) for y in self.accepted_years)
        ):
            raise TypeError("import requires complete accepted year intervals")
        if not isinstance(self.exclusions, tuple) or any(not isinstance(e, AnnualExclusion) for e in self.exclusions):
            raise TypeError("import exclusions require AnnualExclusion tuple")
        periods = self.accepted_years + tuple(e.interval for e in self.exclusions)
        for period in periods:
            _check_year(period, self.accounting_start_month, self.utc_offset_minutes)
        ordered = sorted(periods, key=lambda p: p.start)
        if ordered[0].start != self.reference_period.start or ordered[-1].end != self.reference_period.end:
            raise ValueError("import years must account for reference period")
        if any(a.end != b.start for a, b in zip(ordered, ordered[1:], strict=False)):
            raise ValueError("import years overlap or missing year lacks exclusion")


def _check_year(interval: Interval, month: int, offset: int) -> None:
    local = interval.start.astimezone(timezone(timedelta(minutes=offset)))
    if (local.month, local.day, local.hour, local.minute, local.second, local.microsecond) != (month, 1, 0, 0, 0, 0):
        raise ValueError("annual interval must begin at accounting-year midnight")
    end = datetime(local.year + 1, month, 1, tzinfo=local.tzinfo)
    if interval.end != end:
        raise ValueError("annual interval must cover exactly one complete accounting year")


def annual_mean(
    samples: tuple[FlowSample, ...], *, accounting_start_month: int, utc_offset_minutes: int, provenance: Provenance
) -> FlowSample:
    """Aggregate complete subannual or already annual means by actual volume/duration."""
    result = aggregate_flow(samples, provenance=provenance)
    # Validate even unavailable aggregates; a caller cannot relabel a partial year.
    if type(accounting_start_month) is not int or not 1 <= accounting_start_month <= 12:
        raise ValueError("invalid accounting start month")
    if type(utc_offset_minutes) is not int or not -1440 < utc_offset_minutes < 1440:
        raise ValueError("invalid fixed UTC offset")
    _check_year(result.interval, accounting_start_month, utc_offset_minutes)
    return result


class AnnualEstimator(StrEnum):
    EMPIRICAL = "weibull_linear_discharge"
    ZERO_MIXTURE = "stationary_zero_mixture_lognormal"
    IMPORTED_STATIONARY = "imported_stationary"
    IMPORTED_NONSTATIONARY = "imported_nonstationary"


@dataclass(frozen=True)
class YearProbability:
    interval: Interval
    exceedance: ExceedanceProbability


def empirical_membership(reference: AnnualReference) -> tuple[YearProbability, ...]:
    """Midrank probabilities preserve each original annual observation, including ties."""
    descending = sorted((v.value for v in reference.values), reverse=True)
    probabilities = {
        x: ExceedanceProbability(
            Fraction(
                sum(i + 1 for i, v in enumerate(descending) if v == x), descending.count(x) * (len(descending) + 1)
            )
        )
        for x in set(descending)
    }
    return tuple(
        YearProbability(s.interval, probabilities[s.value.value]) for s in reference.observations if s.value is not None
    )


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
class ZeroMixtureFit:
    reference: AnnualReference
    zero_fraction: Fraction
    log_mean: float | None
    log_variance: float | None
    jumps: tuple[DistributionJump, ...]
    reasons: tuple[str, ...]

    @property
    def distribution_distance(self) -> float | None:
        return max(j.distance for j in self.jumps) if self.jumps else None


def fit_zero_mixture(reference: AnnualReference) -> ZeroMixtureFit:
    positive = [v.value for v in reference.values if v.value > 0]
    pi0 = Fraction(len(reference.values) - len(positive), len(reference.values))
    if len(positive) < 2:
        return ZeroMixtureFit(reference, pi0, None, None, (), ("at least two positive observations required",))
    # log(Fraction) can overflow before logarithm; subtract integer logarithms instead.
    logs = [log(v.numerator) - log(v.denominator) for v in positive]
    mu = sum(logs) / len(logs)
    variance = sum((z - mu) ** 2 for z in logs) / len(logs)
    if variance <= 0 or not isfinite(variance):
        return ZeroMixtureFit(reference, pi0, None, None, (), ("positive log standard deviation required",))
    values = sorted(v.value for v in reference.values)
    jumps = []
    for value in sorted(set(values)):
        left = sum(x < value for x in values) / len(values)
        right = sum(x <= value for x in values) / len(values)
        fitted = (
            float(pi0)
            if value == 0
            else float(pi0)
            + float(1 - pi0) * NormalDist(mu, sqrt(variance)).cdf(log(value.numerator) - log(value.denominator))
        )
        jumps.append(DistributionJump(Flow(value), left, right, 0.0 if value == 0 else fitted, fitted))
    return ZeroMixtureFit(
        reference,
        pi0,
        mu,
        variance,
        tuple(jumps),
        ("candidate fit is not tail validation; zero frequency is not proof of perennial flow",),
    )


def fitted_membership(reference: AnnualReference, fit: ZeroMixtureFit) -> tuple[YearProbability, ...]:
    if fit.reference != reference:
        raise ValueError("fitted membership must retain full reference identity")
    if fit.log_variance is None:
        raise ValueError("fitted membership unavailable: " + "; ".join(fit.reasons))
    probabilities = {
        j.discharge.value: ExceedanceProbability(1 - (j.fitted_left + j.fitted_right) / 2) for j in fit.jumps
    }
    return tuple(
        YearProbability(s.interval, probabilities[s.value.value]) for s in reference.observations if s.value is not None
    )


@dataclass(frozen=True)
class AnnualEstimate:
    reference: AnnualReference | ImportedAnnualReference
    target: ExceedanceProbability
    estimator: AnnualEstimator
    profile_version: str
    value: Flow | None
    provenance: Provenance
    neighbours: tuple[RankNeighbour, ...]
    fit: ZeroMixtureFit | None
    reasons: tuple[str, ...]
    derivation: "ImportedDerivation | None" = None

    def __post_init__(self) -> None:
        if not isinstance(self.reference, (AnnualReference, ImportedAnnualReference)) or not isinstance(
            self.target, ExceedanceProbability
        ):
            raise TypeError("typed annual reference and target required")
        if not isinstance(self.estimator, AnnualEstimator) or not isinstance(self.provenance, Provenance):
            raise TypeError("typed annual estimator and provenance required")
        if self.value is not None and not isinstance(self.value, Flow):
            raise TypeError("annual estimate requires Flow")
        _text(self.profile_version)
        if self.value is None and not self.reasons:
            raise ValueError("unavailable estimate requires reasons")
        first = self.reference.provenance
        if any(
            getattr(first, name) != getattr(self.provenance, name)
            for name in ("scenario", "reference_member", "reference_kind")
        ):
            raise ValueError("estimate provenance changes reference identity")

    @property
    def probability_support_distance(self) -> Fraction:
        n = len(self.reference.accepted_years)
        return max(Fraction(1, n + 1) - self.target.value, self.target.value - Fraction(n, n + 1), Fraction())

    @property
    def discharge_support_distance(self) -> Flow | None:
        if self.value is None or isinstance(self.reference, ImportedAnnualReference):
            return None
        values = [v.value for v in self.reference.values]
        return Flow(max(min(values) - self.value.value, self.value.value - max(values), Fraction()))

    def scope(self, intended_use: str) -> EvidenceScope:
        """Target/profile identity prevents accepting P99 with a generic annual finding."""
        p = self.target.value
        product = f"annual_mean:{self.estimator.value}:{self.profile_version}:P={p}"
        return EvidenceScope(
            product,
            self.reference.location.reach.identifier,
            self.provenance.reference_member,
            self.reference.reference_period,
            intended_use,
        )


def empirical_estimate(
    reference: AnnualReference, target: ExceedanceProbability, *, provenance: Provenance, profile_version: str
) -> AnnualEstimate:
    values = sorted(reference.values, key=lambda v: v.value, reverse=True)
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
    return AnnualEstimate(
        reference, target, AnnualEstimator.EMPIRICAL, profile_version, value, provenance, neighbours, None, reasons
    )


def fitted_estimate(
    reference: AnnualReference, target: ExceedanceProbability, *, provenance: Provenance, profile_version: str
) -> AnnualEstimate:
    fit = fit_zero_mixture(reference)
    value = None
    reasons = fit.reasons
    if fit.log_variance is not None and fit.log_mean is not None:
        u = 1 - target.value
        if u <= fit.zero_fraction:
            value = Flow(0)
        else:
            probability = float((u - fit.zero_fraction) / (1 - fit.zero_fraction))
            if not 0 < probability < 1:
                reasons = (*reasons, "target exceeds floating-point quantile resolution")
            else:
                exponent = fit.log_mean + sqrt(fit.log_variance) * NormalDist().inv_cdf(probability)
                try:
                    quantile = exp(exponent)
                except OverflowError:
                    quantile = float("inf")
                if isfinite(quantile) and quantile > 0:
                    value = Flow(quantile)
                else:
                    reasons = (*reasons, "positive quantile outside floating-point range; not substituted with zero")
    return AnnualEstimate(
        reference, target, AnnualEstimator.ZERO_MIXTURE, profile_version, value, provenance, (), fit, reasons
    )


@dataclass(frozen=True)
class ImportedDerivation:
    """Reproducible specialist derivation, not an unexplained model label."""

    equation: str
    parameter_estimation: str
    calibration_data: str
    diagnostics: tuple[str, ...]
    extrapolation: str
    uncertainty_method: str
    reproducibility_reference: str
    covariates: tuple[str, ...] = ()
    evaluation: str | None = None

    def __post_init__(self) -> None:
        for text in (
            self.equation,
            self.parameter_estimation,
            self.calibration_data,
            self.extrapolation,
            self.uncertainty_method,
            self.reproducibility_reference,
        ):
            _text(text)
        for values in (self.diagnostics, self.covariates):
            if not isinstance(values, tuple):
                raise TypeError("diagnostics and covariates require immutable tuples")
            for text in values:
                _text(text)
        if not self.diagnostics:
            raise ValueError("import requires diagnostics")
        if self.evaluation is not None:
            _text(self.evaluation)


def import_annual_estimate(
    reference: AnnualReference | ImportedAnnualReference,
    target: ExceedanceProbability,
    value: Flow,
    *,
    estimator: AnnualEstimator,
    profile_version: str,
    provenance: Provenance,
    derivation: ImportedDerivation,
) -> AnnualEstimate:
    if estimator not in (AnnualEstimator.IMPORTED_STATIONARY, AnnualEstimator.IMPORTED_NONSTATIONARY):
        raise ValueError("import must retain its own estimator identity")
    if not isinstance(derivation, ImportedDerivation):
        raise TypeError("supported import requires reproducible derivation")
    if estimator is AnnualEstimator.IMPORTED_NONSTATIONARY and (
        not derivation.covariates or derivation.evaluation is None
    ):
        raise ValueError("nonstationary import requires covariates and evaluation date/scenario")
    return AnnualEstimate(
        reference,
        target,
        estimator,
        profile_version,
        value,
        provenance,
        (),
        None,
        ("specialist derivation imported; unseen model not independently validated",),
        derivation,
    )


def annual_use_checks(estimate: AnnualEstimate, findings: EvidenceFindings, intended_use: str) -> CheckSummary:
    """Enforce computability, exact provenance/scope, and present-climate trend gates."""
    available = Check(
        "annual_estimate", CheckFinding.PASS if estimate.value is not None else CheckFinding.FAIL, estimate.reasons
    )
    identity = Check(
        "estimate_provenance",
        CheckFinding.PASS if findings.provenance == estimate.provenance else CheckFinding.FAIL,
        () if findings.provenance == estimate.provenance else ("finding does not identify this estimate provenance",),
    )
    trend = estimate.reference.trend
    stationary = estimate.estimator is not AnnualEstimator.IMPORTED_NONSTATIONARY
    present = estimate.provenance.reference_kind is ReferenceKind.PRESENT_CLIMATE_NATURAL
    climate = Check("reference_climate", CheckFinding.PASS)
    if stationary and present and trend in (TrendTreatment.UNTREATED, TrendTreatment.UNASSESSED):
        climate = Check(
            "reference_climate",
            CheckFinding.FAIL if trend is TrendTreatment.UNTREATED else CheckFinding.UNKNOWN,
            ("stationary present-climate use requires supported climate treatment",),
        )
    return CheckSummary((available, identity, climate, permitted_use(findings, estimate.scope(intended_use))))
