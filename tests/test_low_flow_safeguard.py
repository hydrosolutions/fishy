"""Derived synthetic D.5/M1–M15 checks; fixtures are not adopted policy or basin evidence."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from fractions import Fraction
from functools import lru_cache
from math import exp
from zoneinfo import ZoneInfo

import pytest

from fishy.annual_statistics import ImportedDerivation, TrendTreatment
from fishy.duration_minima import (
    DurationEstimator,
    DurationMinimum,
    construct_duration_reference,
    estimate_duration_threshold,
    import_duration_threshold,
)
from fishy.duration_windows import (
    ContinuousSeason,
    DurationWindowRule,
    WindowDomain,
    WindowUncertaintySupport,
    duration_windows,
)
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    Completeness,
    CorrectionState,
    ProductionMethod,
    Provenance,
    ReferenceKind,
)
from fishy.flows import Coverage, FlowSample, Presence
from fishy.low_flow_frequency import LowFlowReturnPeriod
from fishy.low_flow_safeguard import AssessmentStage, CandidateReferenceRelation, assess_low_flow
from fishy.quantities import Flow, FlowBounds
from fishy.scientific_acceptance import UsePurpose, assess_scientific_use
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval
from tests.test_scientific_acceptance import supplied

LOCATION = Location(Reach("river-reach", "1", WaterBody("river", "1")), CalculationSection("control", "1"), "1")
PROVENANCE = Provenance(
    "synthetic duration fixtures",
    "hypothetical",
    "member-a",
    "test",
    "1",
    "1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
    ReferenceKind.PRESENT_CLIMATE_NATURAL,
)
SUPPORT = WindowUncertaintySupport(
    "joint enclosing support; singleton values are fixed synthetic assumptions",
    "synthetic fixture",
    "all intervals jointly bounded; no marginal-confidence independence inference",
)
DERIVATION = ImportedDerivation(
    "supplied hypothetical threshold, or inverse empirical CDF as explicitly labelled",
    "fixture stipulation",
    "declared complete reference minima",
    ("synthetic, not independently validated",),
    "none claimed",
    "explicit synthetic bounds or missing",
    "D.5 synthetic acceptance cases",
)


def date(year, month=1, day=1):
    return datetime(year, month, day, tzinfo=UTC)


def year_period(year):
    return Interval(date(year), date(year + 1))


def rule(days=7, season=None, month=1, offset=0):
    return DurationWindowRule(
        days,
        WindowDomain.ANNUAL if season is None else WindowDomain.SEASONAL,
        month,
        offset,
        season,
        "explicit hypothetical duration/domain; no national default",
    )


def bounds(lo, hi=None):
    return FlowBounds(
        Flow(lo), Flow(lo if hi is None else hi), "synthetic supported enclosure", "fixture", "joint support"
    )


def samples(start, values, uncertainty=None, provenance=PROVENANCE):
    return tuple(
        FlowSample(
            LOCATION,
            Interval(start + timedelta(days=i), start + timedelta(days=i + 1)),
            None if v is None else Flow(v),
            Presence.MISSING if v is None else Presence.PRESENT,
            provenance,
            uncertainty=None if v is None else uncertainty,
            reasons=("missing fixture slot",) if v is None else (),
        )
        for i, v in enumerate(values)
    )


DEFAULT_RULE = rule()


@lru_cache
def reference(window_rule=DEFAULT_RULE):
    # Four complete calendar years, including leap 2004. Descending levels ensure
    # cross-year windows do not make the following year's minimum smaller.
    data = samples(date(2000, 12, 26), [4] * 6)
    for year, value in zip(range(2001, 2005), (4, 3, 2, 1), strict=True):
        period = year_period(year)
        data += samples(period.start, [value] * int(period.seconds / 86400))
    return construct_duration_reference(
        data,
        Interval(date(2001), date(2005)),
        window_rule,
        location=LOCATION,
        provenance=PROVENANCE,
        predecessor_basis="six actually supplied synthetic reference days",
        climate_basis="stipulated common reference climate",
        trend=TrendTreatment.COMMON_CLIMATE,
        climate_evidence="hypothetical",
        dependence="shared reconstruction errors retained; no independent-day claim",
    )


def threshold(window_rule=DEFAULT_RULE, value=10, uncertainty=None):
    return import_duration_threshold(
        reference(window_rule),
        LowFlowReturnPeriod(2),
        Flow(value),
        profile_version="hypothetical-import-v1",
        derivation=DERIVATION,
        uncertainty=uncertainty,
    )


def assess(
    data,
    period,
    test=None,
    *,
    stage=AssessmentStage.FINAL,
    candidate_basis="explicit fixed synthetic candidate",
    provenance=PROVENANCE,
    predecessor_basis="explicit supported synthetic context",
    scientific_assessment=None,
    uncertainty_support=SUPPORT,
    reference_relation=None,
):
    return assess_low_flow(
        data,
        period,
        threshold() if test is None else test,
        stage=stage,
        candidate_basis=candidate_basis,
        provenance=provenance,
        predecessor_basis=predecessor_basis,
        scientific_assessment=scientific_assessment,
        uncertainty_support=uncertainty_support,
        reference_relation=reference_relation,
    )


def test_m1_seven_day_mean_is_not_daily_floor():
    season = ContinuousSeason("named week", 1, 1, 1, 8)
    data = samples(date(2020), (4, 8, 12, 14, 12, 10, 10))
    result = assess(data, Interval(date(2020), date(2020, 1, 8)), threshold(rule(season=season)))
    assert result.windows.minimum == Flow(10)
    assert result.point.finding is CheckFinding.PASS
    assert result.comparisons[0].shortfall == Flow(0)
    assert Flow(6).value - data[0].value.value == 2
    assert result.uncertainty.finding is CheckFinding.UNKNOWN
    assert result.permission.finding is CheckFinding.UNKNOWN


def test_m2_every_eligible_window_not_just_first():
    data = samples(date(2020), (4, 8, 12, 14, 12, 10, 10, 0))
    r = rule(season=ContinuousSeason("named eight days", 1, 1, 1, 9))
    result = assess(data, Interval(date(2020), date(2020, 1, 9)), threshold(r))
    assert tuple(c.window.mean for c in result.comparisons) == (Flow(10), Flow(Fraction(66, 7)))
    assert result.comparisons[1].shortfall == Flow(Fraction(4, 7))
    assert result.point.finding is CheckFinding.FAIL


@pytest.mark.parametrize(
    "values,expected,complete",
    [
        ((10, 10, None, 10, 10, 10, 10), CheckFinding.UNKNOWN, Completeness.INCOMPLETE),
        ((5, 5, 5, 5, 5, 5, 5, None), CheckFinding.FAIL, Completeness.INCOMPLETE),
    ],
)
def test_m3_m4_known_violation_survives_missing_coverage(values, expected, complete):
    r = rule(season=ContinuousSeason("test season", 1, 1, 1, len(values) + 1))
    result = assess(samples(date(2020), values), Interval(date(2020), date(2020, 1, len(values) + 1)), threshold(r))
    assert result.point.finding is expected
    assert result.point.completeness is complete
    assert result.windows.coverage is Coverage.PARTIAL


def test_m5_m7_no_eligible_season_window_and_missing_annual_context_never_pass():
    period = Interval(date(2020), date(2020, 1, 5))
    data = samples(date(2019, 12, 29), (4, 8, 12, 14, 12, 10, 10))
    r = rule(season=ContinuousSeason("January only", 1, 1, 2, 1))
    result = assess(data, period, threshold(r))
    assert result.comparisons == ()
    assert result.point.finding is CheckFinding.UNKNOWN
    annual = assess(samples(date(2020), [10] * 4), period, predecessor_basis=None)
    assert annual.point.finding is CheckFinding.UNKNOWN
    assert all(c.window.mean is None for c in annual.comparisons)


def test_m6_annual_boundary_uses_real_predecessor_and_last_daily_interval_year():
    data = samples(date(2019, 12, 29), (4, 8, 12, 14, 12, 10, 10))
    period = Interval(date(2020, 1, 4), date(2020, 1, 5))
    result = assess(data, period)
    window = result.comparisons[0].window
    assert window.mean == Flow(10)
    assert window.block_year == 2020
    assert window.interval.start == date(2019, 12, 29)
    assert window.contributors == data
    assert assess(data, period, predecessor_basis=None).point.finding is CheckFinding.UNKNOWN


def test_m8_leap_day_once_with_exact_volume():
    data = samples(date(2020, 2, 26), [10] * 7)
    result = assess(data, Interval(date(2020, 3, 3), date(2020, 3, 4)))
    window = result.comparisons[0].window
    assert window.interval.seconds == 604800
    assert window.volume.value == 6048000
    assert window.mean == Flow(10)
    assert sum(s.interval.start.day == 29 for s in window.contributors) == 1


def test_m9_finer_intervals_volume_weighting_not_unweighted_rates():
    start = date(2020)
    data = tuple(
        FlowSample(
            LOCATION,
            Interval(start + timedelta(days=i, hours=a), start + timedelta(days=i, hours=b)),
            Flow(v),
            Presence.PRESENT,
            PROVENANCE,
        )
        for i in range(7)
        for a, b, v in ((0, 6, 4), (6, 24, 12))
    )
    result = assess(data, Interval(date(2020, 1, 7), date(2020, 1, 8)))
    assert result.windows.minimum == Flow(10)
    assert result.comparisons[0].window.volume.value == 6048000
    assert result.windows.minimum != Flow(8)


def test_m10_coarse_unknown_fraction_and_daily_subinterval_constancy_refused():
    monthly = FlowSample(LOCATION, Interval(date(2020), date(2020, 2)), Flow(10), Presence.PRESENT, PROVENANCE)
    result = assess((monthly,), Interval(date(2020, 1, 7), date(2020, 1, 8)))
    assert result.point.finding is CheckFinding.UNKNOWN
    assert "coarse interval" in result.comparisons[0].window.reasons[0]
    # A supplied whole coarse interval can give exactly its own total, never fractions.
    whole = assess((monthly,), Interval(date(2020, 1, 31), date(2020, 2)), threshold(rule(days=31)))
    assert whole.windows.minimum == Flow(10)
    # Variable-length civil days cannot masquerade as the configured fixed UTC calendar.
    local = ZoneInfo("Europe/Zurich")
    with pytest.raises(ValueError, match="fixed-offset midnight"):
        assess((), Interval(datetime(2020, 3, 29, tzinfo=local), datetime(2020, 3, 30, tzinfo=local)))


def test_m11_provisional_final_and_advisory_are_distinct_full_year_calls():
    period = year_period(2020)
    count = int(period.seconds / 86400) + 6
    start = period.start - timedelta(days=6)
    provisional = assess(samples(start, [8] * count), period, stage=AssessmentStage.PROVISIONAL)
    final = assess(samples(start, [10] * count), period)
    advisory = assess(
        samples(start, [8] * count), period, candidate_basis="quality remains advisory; no binding uplift"
    )
    assert provisional.point.finding is CheckFinding.FAIL
    assert all(c.shortfall == Flow(2) for c in provisional.comparisons)
    assert final.point.finding is CheckFinding.PASS
    assert advisory.point.finding is CheckFinding.FAIL
    assert len(final.comparisons) == 366
    assert provisional.windows.minimum == Flow(8)  # final call did not mutate prior result
    # An independent natural-bound failure is not repaired by a passing duration test.
    combined = CheckSummary((Check("natural_bounds", CheckFinding.FAIL), Check("duration", final.point.finding)))
    assert combined.finding is CheckFinding.FAIL


@pytest.mark.parametrize(
    "value,flow_bounds,expected",
    [
        (10, bounds("9.5", "10.5"), CheckFinding.UNKNOWN),
        (11, bounds(11, 12), CheckFinding.PASS),
        (8, bounds(7, 8), CheckFinding.FAIL),
    ],
)
def test_m12_supported_uncertainty(value, flow_bounds, expected):
    data = samples(date(2020), [value] * 7, flow_bounds)
    result = assess(data, Interval(date(2020, 1, 7), date(2020, 1, 8)), threshold(uncertainty=bounds(9, 11)))
    assert result.uncertainty.finding is expected
    assert result.comparisons[0].window.uncertainty.lower == flow_bounds.lower


def test_m13_zero_missing_invalid_duration_return_period_and_physical_flow():
    result = assess(samples(date(2020), [0] * 7), Interval(date(2020, 1, 7), date(2020, 1, 8)), threshold(value=0))
    assert result.point.finding is CheckFinding.PASS
    assert result.uncertainty.finding is CheckFinding.UNKNOWN
    assert assess((), year_period(2020), threshold(value=0)).point.finding is CheckFinding.UNKNOWN
    for value in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            Flow(value)
    for duration in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            rule(days=duration)
    for recurrence in (0, 1, -1):
        with pytest.raises(ValueError):
            LowFlowReturnPeriod(recurrence)


def test_m14_complete_annual_minima_empirical_vs_imported_estimator_identity():
    ref = reference()
    assert ref.values == (Flow(4), Flow(3), Flow(2), Flow(1))
    assert tuple(len(m.windows.windows) for m in ref.minima) == (365, 365, 365, 366)
    native = estimate_duration_threshold(
        ref, LowFlowReturnPeriod(2), estimator=DurationEstimator.EMPIRICAL, profile_version="weibull-v1"
    )
    imported = import_duration_threshold(
        ref,
        LowFlowReturnPeriod(2),
        Flow(2),
        profile_version="inverse-ECDF-v1",
        derivation=replace(DERIVATION, equation="inf{x : F_n(x) >= 1/T}"),
        uncertainty=None,
    )
    assert native.value == Flow("2.5")
    assert imported.value == Flow(2)
    assert native.identity != imported.identity
    assert native.estimator is DurationEstimator.EMPIRICAL
    assert imported.estimator is DurationEstimator.IMPORTED
    assert [n.probability.value for n in native.neighbours] == [Fraction(2, 5), Fraction(3, 5)]
    assert native.product(UsePurpose.SIZING).low_flow_return_period == LowFlowReturnPeriod(2)
    extreme = estimate_duration_threshold(
        ref, LowFlowReturnPeriod(100), estimator=DurationEstimator.EMPIRICAL, profile_version="weibull-v1"
    )
    assert extreme.value is None
    assert "outside Weibull support" in extreme.reasons[0]


def test_m15_multiple_tests_and_classes_are_separate_without_averaging():
    period = year_period(2020)
    data = samples(date(2019, 12, 26), [10] * 372)
    passed = assess(data, period)
    failed = assess(data, period, threshold(value=11))
    unknown = assess(data[6:], period, threshold(rule(days=30)))
    checks = CheckSummary(
        (
            Check("class25_d7", passed.point.finding),
            Check("class95_d7", failed.point.finding),
            Check("class95_d30", unknown.point.finding),
        )
    )
    assert checks.finding is CheckFinding.FAIL
    assert checks.completeness is Completeness.INCOMPLETE
    assert passed.point.finding is CheckFinding.PASS
    assert failed.point.finding is CheckFinding.FAIL
    assert unknown.point.finding is CheckFinding.UNKNOWN


def test_reference_gap_excludes_whole_block_even_when_known_small_window_exists():
    data = samples(date(2000, 12, 26), [2] * 371)
    missing = data[:200] + data[201:]
    ref = construct_duration_reference(
        missing,
        year_period(2001),
        rule(),
        location=LOCATION,
        provenance=PROVENANCE,
        predecessor_basis="supplied context",
        climate_basis="synthetic",
        trend=TrendTreatment.COMMON_CLIMATE,
        climate_evidence="synthetic",
        dependence="dependent",
    )
    assert ref.values == ()
    assert ref.minima[0].windows is not None
    assert ref.minima[0].windows.minimum == Flow(2)  # diagnostic only
    assert ref.minima[0].value is None
    assert ref.minima[0].reasons
    unavailable = estimate_duration_threshold(
        ref, LowFlowReturnPeriod(2), estimator=DurationEstimator.EMPIRICAL, profile_version="1"
    )
    assert unavailable.value is None
    with pytest.raises(ValueError, match="every eligible complete"):
        replace(ref.minima[0], value=Flow(2))
    # Supported imported reconstruction remains explicitly distinct from observed minimum.
    restored = replace(ref, minima=(DurationMinimum(year_period(2001), Flow(2), None, DERIVATION, ()),))
    assert restored.values == (Flow(2),)
    assert restored.minima[0].derivation is DERIVATION


def test_reference_partial_period_and_missing_predecessor_exclusions():
    data = samples(date(2001), [2] * 365)

    def construct(period):
        return construct_duration_reference(
            data,
            period,
            rule(),
            location=LOCATION,
            provenance=PROVENANCE,
            predecessor_basis=None,
            climate_basis="synthetic",
            trend=TrendTreatment.COMMON_CLIMATE,
            climate_evidence="synthetic",
            dependence="dependent",
        )

    ref = construct(year_period(2001))
    assert ref.values == ()
    assert ref.minima[0].windows is not None
    assert ref.minima[0].windows.coverage is Coverage.PARTIAL
    partial = construct(Interval(date(2001), date(2001, 12, 31)))
    assert partial.values == ()
    assert "partial" in partial.minima[0].reasons[0]


def test_season_crosses_year_and_fixed_offset_accounting_boundary():
    r = rule(season=ContinuousSeason("winter", 11, 1, 3, 1), offset=300)
    tz = timezone(timedelta(hours=5))
    start = datetime(2019, 11, 1, tzinfo=tz)
    end = datetime(2020, 3, 1, tzinfo=tz)
    period = Interval(start, end)
    result = duration_windows(
        samples(start, [10] * 121), period, r, location=LOCATION, provenance=PROVENANCE, predecessor_basis=None
    )
    assert len(result.windows) == 115
    assert {w.block_year for w in result.windows} == {2020}
    assert result.coverage is Coverage.COMPLETE
    assert result.windows[-1].interval.end == end
    annual = rule(month=10, offset=300)
    block = annual.block(datetime(2019, 10, 1, tzinfo=tz))
    assert annual.label(block) == 2020
    assert block.start == datetime(2019, 10, 1, tzinfo=tz)


def test_zero_ties_fitted_candidate_and_u9_reference_thresholds():
    for levels, expected in [((0, 0, 0, 0), Flow(0)), ((2, 2, 2, 2), Flow(2))]:
        ref = replace(
            reference(),
            minima=tuple(
                DurationMinimum(m.block, Flow(v), None, DERIVATION, ())
                for m, v in zip(reference().minima, levels, strict=True)
            ),
        )
        empirical = estimate_duration_threshold(
            ref, LowFlowReturnPeriod(2), estimator=DurationEstimator.EMPIRICAL, profile_version="1"
        )
        fitted = estimate_duration_threshold(
            ref, LowFlowReturnPeriod(2), estimator=DurationEstimator.ZERO_MIXTURE, profile_version="1"
        )
        assert empirical.value == expected
        assert fitted.value is None
    for factor, expected in [(1, 4.976270579072646), (1.5, 7.464405868608971)]:
        wet, dry = factor * 10 * exp(0.3), factor * 10 * exp(-0.3)
        data = samples(date(2000, 12, 26), [wet] * 371 + [dry] * 365)
        ref = construct_duration_reference(
            data,
            Interval(date(2001), date(2003)),
            rule(),
            location=LOCATION,
            provenance=PROVENANCE,
            predecessor_basis="six supplied wet-year context days",
            climate_basis="stipulated synthetic common climate",
            trend=TrendTreatment.COMMON_CLIMATE,
            climate_evidence="synthetic",
            dependence="stipulated shared errors",
        )
        fitted = estimate_duration_threshold(
            ref, LowFlowReturnPeriod(100), estimator=DurationEstimator.ZERO_MIXTURE, profile_version="synthetic-chain"
        )
        assert fitted.value is not None
        assert float(fitted.value.value) == pytest.approx(expected, abs=2e-13)
        assert tuple(float(v.value) for v in ref.values) == pytest.approx((wet, dry), abs=2e-13)


def test_exact_scientific_subject_required_for_permission_and_no_pattern_cure():
    t = threshold(uncertainty=bounds(10))
    record, evidence = supplied(t.product(UsePurpose.SIZING))
    scientific = assess_scientific_use(record, evidence)
    period = year_period(2020)
    data = samples(date(2019, 12, 26), [10] * 372, bounds(10))
    result = assess(data, period, t, scientific_assessment=scientific)
    assert result.point.finding is CheckFinding.PASS
    assert result.uncertainty.finding is CheckFinding.PASS
    assert result.permission.finding is CheckFinding.PASS
    assert result.checks.finding is CheckFinding.PASS
    changed = threshold(value=9, uncertainty=bounds(9))
    assert assess(data, period, changed, scientific_assessment=scientific).permission.finding is CheckFinding.UNKNOWN
    assert (
        CheckSummary((Check("duration", result.checks.finding), Check("daily_pattern", CheckFinding.FAIL))).finding
        is CheckFinding.FAIL
    )


def test_uncertainty_requires_explicit_joint_support_and_missing_threshold_bounds_unknown():
    data = samples(date(2020), [10] * 7, bounds(10))
    period = Interval(date(2020, 1, 7), date(2020, 1, 8))
    assert (
        assess(data, period, threshold(uncertainty=bounds(10)), uncertainty_support=None).uncertainty.finding
        is CheckFinding.UNKNOWN
    )
    assert assess(data, period, threshold()).uncertainty.finding is CheckFinding.UNKNOWN
    with pytest.raises(ValueError, match="ordered"):
        bounds(11, 9)


def test_duplicate_overlapping_misaligned_location_member_and_unit_refused():
    data = samples(date(2020), [10] * 7)
    period = Interval(date(2020, 1, 7), date(2020, 1, 8))
    with pytest.raises(ValueError, match="duplicate or overlapping"):
        assess(data + (data[0],), period)
    with pytest.raises(ValueError, match="location"):
        assess((replace(data[0], location=replace(LOCATION, mapping_version="2")),) + data[1:], period)
    with pytest.raises(ValueError, match="reference identity"):
        assess((replace(data[0], provenance=replace(PROVENANCE, reference_member="other")),) + data[1:], period)
    with pytest.raises(ValueError, match="unit"):
        Flow(1, "m3/day")
    with pytest.raises(ValueError, match="fixed-offset midnight"):
        assess(data, Interval(date(2020) + timedelta(hours=1), date(2020, 1, 8)))


def test_realised_and_selected_family_links_preserve_reference_member_evidence():
    p = replace(PROVENANCE, scenario="realised-scenario", reference_member="selected-family")
    data = samples(date(2020), [10] * 7, provenance=p)
    period = Interval(date(2020, 1, 7), date(2020, 1, 8))
    t = threshold()
    with pytest.raises(ValueError, match="explicit reference relation"):
        assess(data, period, t, provenance=p)
    relation = CandidateReferenceRelation(
        p, t.reference.identity, "selected family checked against retained member-a evidence"
    )
    result = assess(data, period, t, provenance=p, reference_relation=relation, stage=AssessmentStage.REALISED)
    assert result.point.finding is CheckFinding.PASS
    assert result.reference_relation == relation
    assert result.stage is AssessmentStage.REALISED
    assert result.threshold.reference.provenance == PROVENANCE
    with pytest.raises(ValueError, match="exact inputs"):
        assess(data, period, t, provenance=p, reference_relation=replace(relation, reference_identity="wrong"))


def test_native_untreated_climate_cannot_get_stationary_sizing_permission():
    ref = replace(reference(), trend=TrendTreatment.UNTREATED)
    t = estimate_duration_threshold(
        ref, LowFlowReturnPeriod(2), estimator=DurationEstimator.EMPIRICAL, profile_version="1"
    )
    result = assess(samples(date(2020), [10] * 7), Interval(date(2020, 1, 7), date(2020, 1, 8)), t)
    assert result.point.finding is CheckFinding.PASS
    assert result.permission.finding is CheckFinding.FAIL
    assert "common-climate" in result.permission.reasons[-1]


def test_reference_minimum_cannot_hide_required_windows():
    ref = reference()
    first = ref.minima[0]
    assert first.windows is not None
    hidden = replace(first.windows, windows=first.windows.windows[:-1])
    with pytest.raises(ValueError, match="actual interval evidence"):
        replace(first, windows=hidden)


def test_public_complete_calendar_example(capsys):
    from examples.duration_safeguard import main

    result = main()
    assert len(result.comparisons) == 366
    assert result.point.finding is CheckFinding.PASS
    assert result.uncertainty.finding is CheckFinding.PASS
    assert result.permission.finding is CheckFinding.UNKNOWN
    assert "no regime is issued" in capsys.readouterr().out


def test_nested_known_failure_keeps_incomplete_aggregate_coverage():
    t = threshold(uncertainty=bounds(10))
    record, evidence = supplied(t.product(UsePurpose.SIZING))
    scientific = assess_scientific_use(record, evidence)
    data = samples(date(2019, 12, 26), [5] * 372, bounds(5))
    data = data[:100] + data[101:]
    result = assess(data, year_period(2020), t, scientific_assessment=scientific)
    assert result.point.finding is CheckFinding.FAIL
    assert result.uncertainty.finding is CheckFinding.FAIL
    assert result.point.completeness is Completeness.INCOMPLETE
    assert result.uncertainty.completeness is Completeness.INCOMPLETE
    assert result.permission.finding is CheckFinding.PASS
    assert result.checks.finding is CheckFinding.FAIL
    assert result.checks.completeness is Completeness.INCOMPLETE


def test_changed_reference_meaning_requires_explicit_supported_relation():
    t = threshold(uncertainty=bounds(10))
    record, evidence = supplied(t.product(UsePurpose.SIZING))
    scientific = assess_scientific_use(record, evidence)
    future = replace(PROVENANCE, reference_kind=ReferenceKind.FUTURE_CLIMATE_STRESS)
    data = samples(date(2019, 12, 26), [10] * 372, bounds(10), provenance=future)
    with pytest.raises(ValueError, match="explicit reference relation"):
        assess(data, year_period(2020), t, provenance=future, scientific_assessment=scientific)
    relation = CandidateReferenceRelation(
        future,
        t.reference.identity,
        "explicit hypothetical future-stress test against unchanged present-climate threshold",
    )
    result = assess(
        data, year_period(2020), t, provenance=future, scientific_assessment=scientific, reference_relation=relation
    )
    assert result.checks.finding is CheckFinding.PASS
    assert result.reference_relation == relation
    assert result.windows.provenance.reference_kind is ReferenceKind.FUTURE_CLIMATE_STRESS
    assert result.threshold.reference.provenance.reference_kind is ReferenceKind.PRESENT_CLIMATE_NATURAL
