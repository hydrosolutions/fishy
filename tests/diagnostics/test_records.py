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


@pytest.mark.parametrize("kind", [ReferenceKind.MANAGED, ReferenceKind.OBSERVED, None])
def test_unqualified_series_cannot_be_used_as_natural_reference(kind):
    original = samples()
    source = replace(original[0].provenance, reference_kind=kind)
    record = flow_indicators(tuple(replace(sample, provenance=source) for sample in original), profile())
    with pytest.raises(ValueError, match="natural reference"):
        compare_iari(
            record,
            record,
            basis=ComparisonBasis.MATCHED_PERIOD,
            summary=SummaryStatistic.MEDIAN,
            quantile=QuantileEstimator.LINEAR,
        )


def test_observed_production_with_explicit_natural_qualification_remains_supported():
    original = samples()
    source = replace(original[0].provenance, production_method=ProductionMethod.OBSERVED)
    record = flow_indicators(tuple(replace(sample, provenance=source) for sample in original), profile())
    result = compare_iari(
        record,
        record,
        basis=ComparisonBasis.MATCHED_PERIOD,
        summary=SummaryStatistic.MEDIAN,
        quantile=QuantileEstimator.LINEAR,
    )
    assert result.result.total == 0
    assert result.reference.provenance.production_method is ProductionMethod.OBSERVED


def test_attributed_dhram_keeps_raw_changes_and_both_regimes():
    from fishy.diagnostics.dhram import HydrologicalChanges, SupplementaryEvidence, SupplementaryFinding
    from fishy.diagnostics.records import RegimeAttribution, assess_dhram

    first = samples(2001, 2002)[0]
    period = Interval(datetime(2001, 1, 1, tzinfo=UTC), datetime(2002, 1, 1, tzinfo=UTC))
    reference = RegimeAttribution(first.location, period, first.provenance)
    impacted = replace(
        reference,
        provenance=replace(
            first.provenance, source="managed import", scenario="managed", reference_kind=ReferenceKind.MANAGED
        ),
    )
    changes = HydrologicalChanges((1.0,) * 10, ("",) * 10, "external documented historical profile")
    evidence = SupplementaryEvidence(SupplementaryFinding.UNKNOWN, SupplementaryFinding.EXCLUDED, "operational report")
    result = assess_dhram(
        changes, evidence, reference=reference, impacted=impacted, basis=ComparisonBasis.MATCHED_PERIOD
    )
    assert result.result.changes is changes
    assert result.result.supplementary is evidence
    assert result.reference is reference and result.impacted is impacted
    assert result.result.classification is None
    with pytest.raises(ValueError, match="location/mapping"):
        assess_dhram(
            changes,
            evidence,
            reference=reference,
            impacted=replace(impacted, location=replace(first.location, mapping_version="v2")),
            basis=ComparisonBasis.MATCHED_PERIOD,
        )


def test_monthly_attribution_retains_inputs_years_and_spi():
    import polars as pl
    from polars.testing import assert_frame_equal

    from fishy.diagnostics.iari import BasinPrecipitationSPI12
    from fishy.diagnostics.records import RegimeAttribution, compare_monthly_iari

    first = samples(2001, 2002)[0]
    reference_frame = pl.DataFrame(
        [(year, month, float(year - 1979)) for year in range(1980, 2000) for month in range(1, 13)],
        schema={"year": pl.Int32, "month": pl.Int32, "discharge_m3_s": pl.Float64},
        orient="row",
    )
    impacted_frame = pl.DataFrame(
        [(2000, month, 25.0) for month in range(1, 13)], schema=reference_frame.schema, orient="row"
    )
    reference = RegimeAttribution(
        first.location, Interval(datetime(1980, 1, 1, tzinfo=UTC), datetime(2000, 1, 1, tzinfo=UTC)), first.provenance
    )
    impacted = RegimeAttribution(
        first.location,
        Interval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2001, 1, 1, tzinfo=UTC)),
        replace(first.provenance, source="current monthly import", reference_kind=ReferenceKind.MANAGED),
    )
    spi = BasinPrecipitationSPI12(-2)
    result = compare_monthly_iari(
        reference_frame,
        impacted_frame,
        reference=reference,
        impacted=impacted,
        basis=ComparisonBasis.HISTORICAL_BASELINE,
        summary=SummaryStatistic.MEAN,
        quantile=QuantileEstimator.LINEAR,
        spi=spi,
    )
    assert result.result.precipitation_spi is spi and result.result.correction_factor == 0.5
    assert result.result.total == pytest.approx((25 - 15.25) / 9.5 * 0.5)
    assert result.reference is reference and result.impacted is impacted
    assert_frame_equal(result.reference_monthly, reference_frame)
    assert_frame_equal(result.impacted_monthly, impacted_frame)
    with pytest.raises(ValueError, match="coverage"):
        compare_monthly_iari(
            reference_frame,
            impacted_frame,
            reference=reference,
            impacted=replace(
                impacted, period=Interval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2002, 1, 1, tzinfo=UTC))
            ),
            basis=ComparisonBasis.HISTORICAL_BASELINE,
            summary=SummaryStatistic.MEAN,
            quantile=QuantileEstimator.LINEAR,
            spi=spi,
        )
