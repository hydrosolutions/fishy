"""flow_indicators : AttributedDailyFlows × IHAProfile → IndicatorRecord (pure).

Compare identified reference and impacted records without changing their source,
creating a reference, or promoting numerical results to scientific acceptance.
"""

from dataclasses import dataclass
from enum import StrEnum

import polars as pl

from fishy.diagnostics.iari import IARIResult, QuantileEstimator, SummaryStatistic, iari
from fishy.diagnostics.iha import IHAProfile, annual_indicators
from fishy.evidence import Provenance, ReferenceKind
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
    if any(sample.provenance.reference_member is None for sample in reference.source_samples):
        raise ValueError("An identified supplied reference member is required")
    return IARIComparison(
        iari(reference.annual, impacted.annual, summary=summary, quantile=quantile),
        reference,
        impacted,
        basis,
    )
