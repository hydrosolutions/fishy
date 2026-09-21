"""duration_threshold : DurationReference × LowFlowReturnPeriod × Estimator → DurationThreshold (pure).

Annual/seasonal minima retain complete-block provenance. Shared discharge
statistics do not relabel these minima as annual mean discharge.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from hashlib import sha256

from fishy.annual_statistics import ImportedDerivation, TrendTreatment
from fishy.discharge_distribution import (
    DischargeFit,
    ExceedanceProbability,
    RankNeighbour,
    empirical_quantile,
    fitted_quantile,
)
from fishy.duration_windows import (
    DurationWindowRule,
    DurationWindows,
    WindowUncertaintySupport,
    check_fixed_days,
    duration_windows,
)
from fishy.evidence import EvidenceScope, Provenance
from fishy.flows import Coverage, FlowSample
from fishy.low_flow_frequency import LowFlowReturnPeriod
from fishy.quantities import Flow, FlowBounds
from fishy.scientific_acceptance import HydrologicalProduct, HydrologicalProductKind, TemporalResolution, UsePurpose
from fishy.spatial import Location
from fishy.time import Interval


class DurationEstimator(StrEnum):
    EMPIRICAL = "weibull_linear_discharge"
    ZERO_MIXTURE = "stationary_zero_mixture_lognormal"
    IMPORTED = "supported_import"


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty attribution required")


def _identity(value: object) -> str:
    return sha256(repr(value).encode()).hexdigest()


@dataclass(frozen=True)
class DurationMinimum:
    block: Interval
    value: Flow | None
    windows: DurationWindows | None
    derivation: ImportedDerivation | None
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.block, Interval):
            raise TypeError("minimum requires reference block")
        if self.windows is not None and not isinstance(self.windows, DurationWindows):
            raise TypeError("computed minimum requires DurationWindows")
        if self.derivation is not None and not isinstance(self.derivation, ImportedDerivation):
            raise TypeError("imported minimum requires ImportedDerivation")
        if not isinstance(self.reasons, tuple) or any(not isinstance(r, str) or not r.strip() for r in self.reasons):
            raise TypeError("minimum reasons require immutable nonempty strings")
        if self.value is not None and not isinstance(self.value, Flow):
            raise TypeError("minimum requires Flow")
        if self.windows is not None:
            if self.derivation is not None:
                raise ValueError("computed minima cannot masquerade as imported minima")
            inputs = tuple(
                sorted({s for w in self.windows.windows for s in w.contributors}, key=lambda s: s.interval.start)
            )
            recomputed = duration_windows(
                inputs,
                self.windows.period,
                self.windows.rule,
                location=self.windows.location,
                provenance=self.windows.provenance,
                predecessor_basis=self.windows.predecessor_basis,
                uncertainty_support=self.windows.uncertainty_support,
            )
            if recomputed != self.windows:
                raise ValueError("minimum window diagnostics differ from their actual interval evidence")
            expected = self.windows.minimum if self.windows.coverage is Coverage.COMPLETE else None
            if self.value != expected:
                raise ValueError("minimum must use every eligible complete block window")
        elif self.value is not None and not isinstance(self.derivation, ImportedDerivation):
            raise ValueError("imported/reconstructed minimum requires reproducible derivation")
        if self.value is None and not self.reasons:
            raise ValueError("excluded block requires reason")


@dataclass(frozen=True)
class DurationReference:
    rule: DurationWindowRule
    period: Interval
    location: Location
    provenance: Provenance
    minima: tuple[DurationMinimum, ...]
    climate_basis: str
    trend: TrendTreatment
    climate_evidence: str
    dependence: str

    def __post_init__(self) -> None:
        if not isinstance(self.rule, DurationWindowRule) or not isinstance(self.period, Interval):
            raise TypeError("typed reference rule and period required")
        if not isinstance(self.location, Location) or not isinstance(self.provenance, Provenance):
            raise TypeError("typed location/provenance required")
        if self.provenance.reference_kind is None or not isinstance(self.trend, TrendTreatment):
            raise ValueError("reference requires natural/observed meaning and trend treatment")
        for text in (self.climate_basis, self.climate_evidence, self.dependence):
            _text(text)
        if not isinstance(self.minima, tuple) or any(not isinstance(m, DurationMinimum) for m in self.minima):
            raise TypeError("immutable duration minima required")
        expected = reference_blocks(self.period, self.rule)
        if tuple(m.block for m in self.minima) != expected:
            raise ValueError("every declared reference block must be retained, including exclusions")
        for minimum in self.minima:
            if minimum.value is not None and (
                minimum.block.start < self.period.start or minimum.block.end > self.period.end
            ):
                raise ValueError("partial reference block cannot supply a complete minimum")
            if minimum.windows is not None and (
                minimum.windows.period != minimum.block
                or minimum.windows.rule != self.rule
                or minimum.windows.location != self.location
                or minimum.windows.provenance != self.provenance
            ):
                raise ValueError("minimum window identity differs from reference")

    @property
    def values(self) -> tuple[Flow, ...]:
        return tuple(m.value for m in self.minima if m.value is not None)

    @property
    def identity(self) -> str:
        return "duration-reference-v1:" + _identity(self)


def reference_blocks(period: Interval, rule: DurationWindowRule) -> tuple[Interval, ...]:
    check_fixed_days(period, rule)
    blocks = []
    day = period.start
    while day < period.end:
        block = rule.block(day)
        if block is not None and block not in blocks:
            blocks.append(block)
        day += timedelta(days=1)
    return tuple(blocks)


def construct_duration_reference(
    samples: tuple[FlowSample, ...],
    period: Interval,
    rule: DurationWindowRule,
    *,
    location: Location,
    provenance: Provenance,
    predecessor_basis: str | None,
    climate_basis: str,
    trend: TrendTreatment,
    climate_evidence: str,
    dependence: str,
    uncertainty_support: WindowUncertaintySupport | None = None,
) -> DurationReference:
    minima = []
    for block in reference_blocks(period, rule):
        if block.start < period.start or block.end > period.end:
            minima.append(DurationMinimum(block, None, None, None, ("partial declared reference block excluded",)))
            continue
        windows = duration_windows(
            samples,
            block,
            rule,
            location=location,
            provenance=provenance,
            predecessor_basis=predecessor_basis,
            uncertainty_support=uncertainty_support,
        )
        complete = windows.coverage is Coverage.COMPLETE
        minima.append(
            DurationMinimum(
                block,
                windows.minimum if complete else None,
                windows,
                None,
                () if complete else ("incomplete reference block excluded; no fully observed minimum",),
            )
        )
    return DurationReference(
        rule, period, location, provenance, tuple(minima), climate_basis, trend, climate_evidence, dependence
    )


@dataclass(frozen=True)
class DurationThreshold:
    reference: DurationReference
    return_period: LowFlowReturnPeriod
    estimator: DurationEstimator
    profile_version: str
    value: Flow | None
    uncertainty: FlowBounds | None
    neighbours: tuple[RankNeighbour, ...]
    fit: DischargeFit | None
    derivation: ImportedDerivation | None
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.reference, DurationReference) or not isinstance(self.return_period, LowFlowReturnPeriod):
            raise TypeError("typed duration reference and return period required")
        if not isinstance(self.estimator, DurationEstimator):
            raise TypeError("typed duration estimator required")
        _text(self.profile_version)
        if self.value is not None and not isinstance(self.value, Flow):
            raise TypeError("threshold requires Flow")
        if self.uncertainty is not None and (
            not isinstance(self.uncertainty, FlowBounds)
            or self.value is None
            or not self.uncertainty.lower.value <= self.value.value <= self.uncertainty.upper.value
        ):
            raise ValueError("threshold point must lie inside supported uncertainty")
        if self.estimator is DurationEstimator.IMPORTED:
            if not isinstance(self.derivation, ImportedDerivation) or self.neighbours or self.fit is not None:
                raise ValueError("import retains its own derivation, never native rank/fit evidence")
            if self.reference.trend is TrendTreatment.UNTREATED and (
                not self.derivation.covariates or self.derivation.evaluation is None
            ):
                raise ValueError("untreated climate needs covariate/evaluation-specific imported treatment")
        else:
            expected = _estimate(self.reference, self.return_period, self.estimator)
            if (self.value, self.neighbours, self.fit, self.reasons) != expected or self.derivation is not None:
                raise ValueError("duration threshold differs from its computed population/estimator")
        if self.value is None and not self.reasons:
            raise ValueError("unavailable threshold requires reason")

    @property
    def identity(self) -> str:
        return "duration-threshold-v1:" + _identity(self)

    def product(self, purpose: UsePurpose) -> HydrologicalProduct:
        r = self.reference
        scope = EvidenceScope(
            self.identity, r.location.reach.identifier, r.provenance.reference_member, r.period, purpose.value
        )
        return HydrologicalProduct(
            scope,
            r.provenance,
            HydrologicalProductKind.DURATION_MINIMUM,
            f"{r.rule.duration_days}-day {r.rule.domain.value} minimum: {self.estimator.value}",
            "m3/s",
            f"fixed 86400-second days; UTC offset {r.rule.utc_offset_minutes}; accounting month {r.rule.accounting_start_month}",
            TemporalResolution.ANNUAL,
            purpose,
            self.return_period.exceedance_probability,
            r.rule.duration_days,
            r.location,
            r.climate_basis,
            f"{r.rule.domain.value}: {r.rule.season!r}",
            r.identity,
            self.identity,
            self.value,
            tuple(m.block for m in r.minima if m.value is not None),
            self.return_period,
        )


def _estimate(
    reference: DurationReference, recurrence: LowFlowReturnPeriod, estimator: DurationEstimator
) -> tuple[Flow | None, tuple[RankNeighbour, ...], DischargeFit | None, tuple[str, ...]]:
    if not reference.values:
        return None, (), None, ("no eligible complete reference minima",)
    target = ExceedanceProbability(recurrence.exceedance_probability)
    if estimator is DurationEstimator.EMPIRICAL:
        value, neighbours, reasons = empirical_quantile(reference.values, target)
        return value, neighbours, None, reasons
    value, fit, reasons = fitted_quantile(reference.values, target)
    return value, (), fit, reasons


def estimate_duration_threshold(
    reference: DurationReference,
    return_period: LowFlowReturnPeriod,
    *,
    estimator: DurationEstimator,
    profile_version: str,
    uncertainty: FlowBounds | None = None,
) -> DurationThreshold:
    if estimator not in (DurationEstimator.EMPIRICAL, DurationEstimator.ZERO_MIXTURE):
        raise ValueError("native duration estimate requires empirical or zero-mixture estimator")
    value, neighbours, fit, reasons = _estimate(reference, return_period, estimator)
    return DurationThreshold(
        reference, return_period, estimator, profile_version, value, uncertainty, neighbours, fit, None, reasons
    )


def import_duration_threshold(
    reference: DurationReference,
    return_period: LowFlowReturnPeriod,
    value: Flow,
    *,
    profile_version: str,
    derivation: ImportedDerivation,
    uncertainty: FlowBounds | None,
) -> DurationThreshold:
    return DurationThreshold(
        reference,
        return_period,
        DurationEstimator.IMPORTED,
        profile_version,
        value,
        uncertainty,
        (),
        None,
        derivation,
        ("specialist import; model not independently validated here",),
    )
