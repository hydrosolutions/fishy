"""Real public FlowSample-to-diagnostics boundary without a simulator."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from fishy.diagnostics.iari import QuantileEstimator, SummaryStatistic
from fishy.diagnostics.iha import CentralStatistic, IHAProfile, PulseThresholds, RateBoundary
from fishy.diagnostics.records import ComparisonBasis, compare_iari, flow_indicators
from fishy.evidence import CorrectionState, ProductionMethod, Provenance, ReferenceKind
from fishy.flows import FlowSample, Presence
from fishy.quantities import Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def samples(begin=2001, end=2021):
    location = Location(Reach("reach", "v1", WaterBody("river", "v1")), CalculationSection("section", "v1"), "map-v1")
    provenance = Provenance(
        "synthetic dated observations",
        "reference",
        "member-a",
        "test-v1",
        "data-v1",
        "config-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
    )
    start = datetime(begin, 1, 1, tzinfo=UTC)
    finish = datetime(end, 1, 1, tzinfo=UTC)
    result = []
    while start < finish:
        index = (start - datetime(start.year, 1, 1, tzinfo=UTC)).days
        value = [10, 5, 15, 10, 0, 10, 20, 10][index % 8]
        result.append(
            FlowSample(location, Interval(start, start + timedelta(days=1)), Flow(value), Presence.PRESENT, provenance)
        )
        start += timedelta(days=1)
    return tuple(result)


def profile():
    return IHAProfile(CentralStatistic.MEAN, PulseThresholds(Flow(4), Flow(18)), RateBoundary.WITHIN_YEAR)


def test_sufficient_record_public_path_keeps_identity_and_complete_numerical_iari():
    original = samples()
    reference = flow_indicators(original, profile())
    changed_source = replace(
        original[0].provenance,
        scenario="managed",
        reference_member="managed-member",
        reference_kind=ReferenceKind.MANAGED,
    )
    impacted = flow_indicators(tuple(replace(sample, provenance=changed_source) for sample in original), profile())
    result = compare_iari(
        reference,
        impacted,
        basis=ComparisonBasis.MATCHED_PERIOD,
        summary=SummaryStatistic.MEDIAN,
        quantile=QuantileEstimator.LINEAR,
    )
    assert result.result.total == pytest.approx(0.0)
    assert result.reference.provenance is original[0].provenance
    assert result.impacted.provenance.scenario == "managed"
    assert result.reference.annual.height == 20 * 33
    assert result.reference.period.end == datetime(2021, 1, 1, tzinfo=UTC)


def test_daily_operator_rejects_partial_year_not_general_input():
    original = samples(2001, 2002)
    assert original[0].value == Flow(10)
    with pytest.raises(ValueError, match="Complete calendar years"):
        flow_indicators(original[:2], profile())


def test_missing_not_skipped_and_map_profile_comparison_rejected():
    original = samples(2001, 2002)
    missing = replace(original[10], value=None, presence=Presence.MISSING, reasons=("no observation",))
    with pytest.raises(ValueError, match="unavailable"):
        flow_indicators((*original[:10], missing, *original[11:]), profile())
    record = flow_indicators(original, profile())
    mismatch = replace(record, location=replace(record.location, mapping_version="different"))
    with pytest.raises(ValueError, match="location/mapping"):
        compare_iari(
            record,
            mismatch,
            basis=ComparisonBasis.MATCHED_PERIOD,
            summary=SummaryStatistic.MEAN,
            quantile=QuantileEstimator.LINEAR,
        )
    with pytest.raises(ValueError, match="definitions"):
        compare_iari(
            record,
            replace(record, profile=replace(profile(), central_statistic=CentralStatistic.MEDIAN)),
            basis=ComparisonBasis.MATCHED_PERIOD,
            summary=SummaryStatistic.MEAN,
            quantile=QuantileEstimator.LINEAR,
        )


def test_future_stress_cannot_be_relabelled_reference():
    record = flow_indicators(samples(2001, 2002), profile())
    future = replace(
        record,
        source_samples=tuple(
            replace(sample, provenance=replace(sample.provenance, reference_kind=ReferenceKind.FUTURE_CLIMATE_STRESS))
            for sample in record.source_samples
        ),
    )
    with pytest.raises(ValueError, match="Future-climate"):
        compare_iari(
            future,
            record,
            basis=ComparisonBasis.MATCHED_PERIOD,
            summary=SummaryStatistic.MEAN,
            quantile=QuantileEstimator.LINEAR,
        )


def test_historical_basis_does_not_accept_matched_periods():
    record = flow_indicators(samples(), profile())
    with pytest.raises(ValueError, match="Historical baseline"):
        compare_iari(
            record,
            record,
            basis=ComparisonBasis.HISTORICAL_BASELINE,
            summary=SummaryStatistic.MEDIAN,
            quantile=QuantileEstimator.LINEAR,
        )


def test_corrected_observation_history_remains_attributable_per_day():
    original = samples(2001, 2002)
    corrected = replace(
        original[40],
        provenance=replace(
            original[40].provenance,
            source="corrected rating",
            data_version="data-v2",
            correction_state=CorrectionState.CORRECTED,
        ),
    )
    record = flow_indicators((*original[:40], corrected, *original[41:]), profile())
    assert record.source_samples[40] is corrected
    assert record.source_samples[39].provenance.correction_state is CorrectionState.ORIGINAL
    with pytest.raises(ValueError, match="Heterogeneous"):
        _ = record.provenance
