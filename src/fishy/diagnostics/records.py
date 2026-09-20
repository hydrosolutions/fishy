"""flow_indicators : AttributedDailyFlows × IHAProfile → IndicatorRecord (pure).

Compare identified reference and impacted records without changing their source,
creating a reference, or promoting numerical results to scientific acceptance.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

import polars as pl

from fishy.diagnostics.iari import (
    BasinPrecipitationSPI12,
    IARIResult,
    QuantileEstimator,
    SummaryStatistic,
    iari,
    monthly_iari,
)
from fishy.diagnostics.iha import IHAProfile, annual_indicators
from fishy.evidence import CorrectionState, Provenance, ReferenceKind
from fishy.flows import FlowSample, daily_discharge
from fishy.spatial import Location
from fishy.time import Interval


class ComparisonBasis(StrEnum):
    MATCHED_PERIOD = "matched_period"
    HISTORICAL_BASELINE = "historical_baseline"


@dataclass(frozen=True)
class IndicatorRecord:
    """Annual numerical table with its exact source, coverage and conventions."""

    annual: pl.DataFrame
    source_samples: tuple[FlowSample, ...]
    location: Location
    period: Interval
    profile: IHAProfile

    def __post_init__(self) -> None:
        if not isinstance(self.source_samples, tuple) or not self.source_samples:
            raise ValueError("Indicator record requires nonempty immutable source history")
        if any(not isinstance(sample, FlowSample) for sample in self.source_samples):
            raise TypeError("Source history requires FlowSample records")
        if not isinstance(self.profile, IHAProfile):
            raise TypeError("Indicator record requires IHAProfile")
        # Reuse the real daily evidence boundary: no metadata-only qualification
        # can restore excluded, missing or incompatible source samples.
        dates = daily_discharge(self.source_samples)["date"].to_list()
        ordered = sorted(self.source_samples, key=lambda sample: sample.interval.start)
        if self.location != ordered[0].location:
            raise ValueError("Indicator location contradicts source history")
        if self.period != Interval(ordered[0].interval.start, ordered[-1].interval.end):
            raise ValueError("Indicator period contradicts source history")
        if any((right - left).days != 1 for left, right in zip(dates, dates[1:], strict=False)):
            raise ValueError("Indicator source history must contain dense daily coverage")
        if (dates[0].month, dates[0].day) != (1, 1) or (dates[-1].month, dates[-1].day) != (12, 31):
            raise ValueError("Indicator source history requires complete calendar years")
        if (
            not isinstance(self.annual, pl.DataFrame)
            or "year" not in self.annual.columns
            or set(self.annual["year"].to_list()) != {day.year for day in dates}
        ):
            raise ValueError("Annual table years contradict source history")

    @property
    def provenance(self) -> Provenance:
        """Convenience only for homogeneous histories; source_samples are authoritative."""
        sources = tuple(dict.fromkeys(sample.provenance for sample in self.source_samples))
        if len(sources) != 1:
            raise ValueError("Heterogeneous source history: inspect source_samples by interval")
        return sources[0]


@dataclass(frozen=True)
class IARIComparison:
    result: IARIResult
    reference: IndicatorRecord
    impacted: IndicatorRecord
    basis: ComparisonBasis


def flow_indicators(samples: tuple[FlowSample, ...], profile: IHAProfile) -> IndicatorRecord:
    """Consume supported observations, imports or physical interval projections.

    Only this diagnostic boundary requires complete dense calendar years. The
    general FlowSample input and supplied-duty assessment do not impose that gate.
    """
    daily = daily_discharge(samples)
    ordered = sorted(samples, key=lambda sample: sample.interval.start)
    first = ordered[0]
    annual = annual_indicators(daily, profile)
    return IndicatorRecord(
        annual,
        tuple(ordered),
        first.location,
        Interval(first.interval.start, ordered[-1].interval.end),
        profile,
    )


def compare_iari(
    reference: IndicatorRecord,
    impacted: IndicatorRecord,
    *,
    basis: ComparisonBasis,
    summary: SummaryStatistic,
    quantile: QuantileEstimator,
) -> IARIComparison:
    """Compare compatible IHA records using the original daily ISPRA profile.

    Historical before/after records and matched-period model/observation records
    are distinct explicit choices. Future stress series are not natural baselines.
    """
    if not isinstance(basis, ComparisonBasis):
        raise TypeError("Comparison basis must be explicit")
    if reference.location != impacted.location:
        raise ValueError("Reference and impacted location/mapping versions differ")
    if reference.profile != impacted.profile:
        raise ValueError("Annual definitions and reference pulse thresholds must match")
    if basis is ComparisonBasis.MATCHED_PERIOD and reference.period != impacted.period:
        raise ValueError("Matched-period comparison requires identical exact coverage")
    if basis is ComparisonBasis.HISTORICAL_BASELINE and reference.period.end > impacted.period.start:
        raise ValueError("Historical baseline must precede the impacted assessment period")
    if any(
        sample.provenance.reference_kind is ReferenceKind.FUTURE_CLIMATE_STRESS for sample in reference.source_samples
    ):
        raise ValueError("Future-climate stress cannot become a natural reference")
    if any(
        sample.provenance.reference_kind
        not in (ReferenceKind.PRESENT_CLIMATE_NATURAL, ReferenceKind.NATURALISED_HISTORICAL)
        for sample in reference.source_samples
    ):
        raise ValueError("An explicitly qualified natural reference is required")
    if any(sample.provenance.reference_member is None for sample in reference.source_samples):
        raise ValueError("An identified supplied reference member is required")
    return IARIComparison(
        iari(reference.annual, impacted.annual, summary=summary, quantile=quantile),
        reference,
        impacted,
        basis,
    )


@dataclass(frozen=True)
class RegimeAttribution:
    """Located, dated evidence identity for externally supplied regime statistics."""

    location: Location
    period: Interval
    provenance: Provenance

    def __post_init__(self) -> None:
        for value, expected in ((self.location, Location), (self.period, Interval), (self.provenance, Provenance)):
            if not isinstance(value, expected):
                raise TypeError("Regime attribution requires typed location, interval and provenance")


@dataclass(frozen=True)
class MonthlyIARIComparison:
    result: IARIResult
    reference: RegimeAttribution
    impacted: RegimeAttribution
    reference_monthly: pl.DataFrame
    impacted_monthly: pl.DataFrame
    basis: ComparisonBasis


def _compatible_attribution(reference: RegimeAttribution, impacted: RegimeAttribution, basis: ComparisonBasis) -> None:
    if any(item.provenance.correction_state is CorrectionState.MISSING for item in (reference, impacted)):
        raise ValueError("Imported diagnostic evidence is marked missing")
    if not isinstance(basis, ComparisonBasis):
        raise TypeError("Comparison basis must be explicit")
    if reference.location != impacted.location:
        raise ValueError("Reference and impacted location/mapping versions differ")
    if reference.provenance.reference_kind not in (
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
        ReferenceKind.NATURALISED_HISTORICAL,
    ):
        raise ValueError("An explicitly qualified natural reference is required")
    if reference.provenance.reference_member is None:
        raise ValueError("An identified supplied reference member is required")
    if basis is ComparisonBasis.MATCHED_PERIOD and reference.period != impacted.period:
        raise ValueError("Matched-period comparison requires identical exact coverage")
    if basis is ComparisonBasis.HISTORICAL_BASELINE and reference.period.end > impacted.period.start:
        raise ValueError("Historical baseline must precede the impacted assessment period")


def _monthly_period(frame: pl.DataFrame, attribution: RegimeAttribution) -> None:
    years = frame["year"].to_list()
    start = datetime(min(years), 1, 1, tzinfo=UTC)
    end = datetime(max(years) + 1, 1, 1, tzinfo=UTC)
    if attribution.period != Interval(start, end):
        raise ValueError("Monthly input years disagree with attributed exact coverage")


def compare_monthly_iari(
    reference_monthly: pl.DataFrame,
    impacted_monthly: pl.DataFrame,
    *,
    reference: RegimeAttribution,
    impacted: RegimeAttribution,
    basis: ComparisonBasis,
    summary: SummaryStatistic,
    quantile: QuantileEstimator,
    spi: BasinPrecipitationSPI12 | None = None,
) -> MonthlyIARIComparison:
    """Assess identified monthly evidence and retain the SPI correction operand."""
    _compatible_attribution(reference, impacted, basis)
    result = monthly_iari(reference_monthly, impacted_monthly, summary=summary, quantile=quantile, spi=spi)
    _monthly_period(reference_monthly, reference)
    _monthly_period(impacted_monthly, impacted)
    _admit_selected_period(reference, _year_period(result.reference_years))
    _admit_selected_period(impacted, _year_period(result.impacted_years))
    return MonthlyIARIComparison(
        result, reference, impacted, reference_monthly.clone(), impacted_monthly.clone(), basis
    )


def _admit_selected_period(attribution: RegimeAttribution, selected: Interval) -> None:
    if any(
        excluded.start < selected.end and selected.start < excluded.end
        for excluded in attribution.provenance.excluded_warmup
    ):
        raise ValueError("Imported diagnostic selected evidence overlaps excluded warm-up")


def _year_period(years: tuple[int, ...]) -> Interval:
    return Interval(datetime(min(years), 1, 1, tzinfo=UTC), datetime(max(years) + 1, 1, 1, tzinfo=UTC))
