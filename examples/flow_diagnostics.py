"""Synthetic supplied flows → annual IHA and IARI (pure example).

Run with uv run python examples/flow_diagnostics.py. No basin validation claimed.
"""

from datetime import UTC, datetime, timedelta

from fishy.diagnostics.iari import QuantileEstimator, SummaryStatistic
from fishy.diagnostics.iha import CentralStatistic, IHAProfile, PulseThresholds, RateBoundary
from fishy.diagnostics.records import ComparisonBasis, compare_iari, flow_indicators
from fishy.evidence import CorrectionState, ProductionMethod, Provenance, ReferenceKind
from fishy.flows import FlowSample, Presence
from fishy.quantities import Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def main() -> None:
    location = Location(
        Reach("river-reach", "v1", WaterBody("river", "v1")), CalculationSection("section", "v1"), "mapping-v1"
    )
    reference_source = Provenance(
        "synthetic waveform",
        "reference",
        "reference-a",
        "example-v1",
        "data-v1",
        "config-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
    )
    impacted_source = Provenance(
        "synthetic waveform",
        "managed",
        "managed-a",
        "example-v1",
        "data-v1",
        "config-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
        ReferenceKind.MANAGED,
    )
    reference_samples, impacted_samples = [], []
    start, finish = datetime(2001, 1, 1, tzinfo=UTC), datetime(2021, 1, 1, tzinfo=UTC)
    while start < finish:
        day = (start - datetime(start.year, 1, 1, tzinfo=UTC)).days
        value = Flow([10, 5, 15, 10, 0, 10, 20, 10][day % 8])
        interval = Interval(start, start + timedelta(days=1))
        reference_samples.append(FlowSample(location, interval, value, Presence.PRESENT, reference_source))
        impacted_samples.append(FlowSample(location, interval, value, Presence.PRESENT, impacted_source))
        start = interval.end
    profile = IHAProfile(CentralStatistic.MEAN, PulseThresholds(Flow(4), Flow(18)), RateBoundary.WITHIN_YEAR)
    reference = flow_indicators(tuple(reference_samples), profile)
    impacted = flow_indicators(tuple(impacted_samples), profile)
    comparison = compare_iari(
        reference,
        impacted,
        basis=ComparisonBasis.MATCHED_PERIOD,
        summary=SummaryStatistic.MEDIAN,
        quantile=QuantileEstimator.LINEAR,
    )
    print(f"Annual IHA rows: {reference.annual.height}; IARI: {comparison.result.total}")
    assert reference.annual.height == 660 and comparison.result.total == 0


if __name__ == "__main__":
    main()
