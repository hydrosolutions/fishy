"""Complete-year public-boundary witnesses (exact Fraction equality, tolerance zero).

D1: full-reference .97/.99 membership; D2: .99 outside [.95,.97];
D3: five donor years/two clusters fails three; D4/D5: equal-year shares
3/8,3/8,1/4,0 and one receiving Flow(8) scaling; D6/D7/D9 arithmetic
operators also have dedicated test_pattern_calendar witnesses; D8: simultaneous
edge/shift exclusions and recomputation; D10: source zero is not missing;
D11: strict unmodified crossings; D12: 252288000/252979200 m3;
D13: explicit missing/invalid/identity failures; D14: crossing-season fallback.
Synthetic settings below are test inputs, not scientific acceptance criteria.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest
from fishy.scientific_acceptance import (
    AcceptanceRecord,
    Aggregation,
    ClimateTreatment,
    Comparison,
    CriterionRole,
    DailyDerivation,
    DiagnosticObservation,
    ErrorMeasure,
    EvidenceItem,
    EvidenceRequirement,
    HydrologicalProductKind,
    RatingSupport,
    ScientificCriterion,
    ScientificEvidence,
    UsePurpose,
    ValidationEvidence,
    ValidationMethod,
    assess_scientific_use,
    minimum_evidence,
)

from fishy.annual_statistics import (
    AnnualEstimator,
    AnnualReference,
    ExceedanceProbability,
    ImportedDerivation,
    TrendTreatment,
    YearProbability,
    import_annual_estimate,
)
from fishy.daily_patterns import (
    AlignmentChoice,
    AlignmentSettings,
    AnalogueReference,
    DailyReferenceYear,
    DonorEligibility,
    Extrapolation,
    ImportedMembership,
    MembershipEstimator,
    PatternMethod,
    PatternProfile,
    annual_magnitude_product,
    construct_pattern,
    crossed_bounds,
    import_pattern,
    pattern_product,
)
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    Computability,
    CorrectionState,
    Disclosure,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    ScientificAdequacy,
)
from fishy.flows import Coverage, FlowSample, Presence
from fishy.pattern_calendar import AccountingYear
from fishy.quantities import Flow, Volume
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

PASS = CheckSummary((Check("synthetic-quality", CheckFinding.PASS),))
PROVENANCE = Provenance(
    "synthetic-record",
    "present",
    "natural-v1",
    "test-v1",
    "test-v1",
    "test-v1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
    ReferenceKind.PRESENT_CLIMATE_NATURAL,
)
TARGET = AccountingYear(2023, 1, 0)


def location(name="receiver"):
    return Location(Reach(name, "v1", WaterBody("water", "v1")), CalculationSection(name, "v1"), "v1")


def year(number=2019, values=None, *, donor="a", cluster=None, provenance=PROVENANCE, calendar=None):
    calendar = AccountingYear(number, 1, 0) if calendar is None else calendar
    if values is None:
        values = (Fraction(1),) * calendar.days
    samples = tuple(
        FlowSample(
            location(donor),
            Interval(calendar.interval.start + timedelta(days=i), calendar.interval.start + timedelta(days=i + 1)),
            Flow(value),
            Presence.PRESENT,
            provenance,
        )
        for i, value in enumerate(values)
    )
    return DailyReferenceYear(calendar, samples, cluster or str(number), PASS)


def pool(years, probabilities=None, *, daily_years=None):
    observations = tuple(
        FlowSample(y.location, y.calendar.interval, y.annual_mean, Presence.PRESENT, y.provenance) for y in years
    )
    periods = [y.calendar.interval for y in years]
    reference = AnnualReference(
        observations,
        Interval(min(p.start for p in periods), max(p.end for p in periods)),
        "synthetic-common-climate",
        years[0].calendar.start_month,
        years[0].calendar.utc_offset_minutes,
        (),
        TrendTreatment.COMMON_CLIMATE,
        "synthetic supported basis",
    )
    membership = (
        None
        if probabilities is None
        else ImportedMembership(
            tuple(
                YearProbability(y.calendar.interval, ExceedanceProbability(p))
                for y, p in zip(years, probabilities, strict=True)
            ),
            "tabulated full-reference synthetic probabilities",
            "fixed fixture",
            "fixture identities checked",
            "not scientific evidence",
            years[0].provenance,
        )
    )
    return AnalogueReference(reference, tuple(years if daily_years is None else daily_years), membership)


def magnitude(target=Fraction(99, 100), value=8, *, reference_calendar=None):
    reference = pool((year(donor="receiver", calendar=reference_calendar),)).reference
    return import_annual_estimate(
        reference,
        ExceedanceProbability(target),
        Flow(value),
        estimator=AnnualEstimator.IMPORTED_STATIONARY,
        profile_version="annual-test-v1",
        provenance=PROVENANCE,
        derivation=ImportedDerivation(
            "Q(P)=fixture",
            "fixed synthetic input",
            "synthetic reference",
            ("not fitted",),
            "not scientifically validated",
            "not assessed",
            "tests/test_daily_patterns.py",
        ),
    )


def profile(
    pools,
    *,
    target=Fraction(99, 100),
    band=Fraction(1),
    estimator=MembershipEstimator.IMPORTED,
    clusters=1,
    sources=1,
    alignment=None,
):
    donors = {y.location: y.provenance for p in pools for y in p.years}
    return PatternProfile(
        "pattern-test-v1",
        ExceedanceProbability(target),
        band,
        "natural-v1",
        "present",
        "synthetic-common-climate",
        estimator,
        tuple(
            DonorEligibility(loc, ("synthetic hydrological similarity",), PASS, provenance)
            for loc, provenance in donors.items()
        ),
        sources,
        clusters,
        alignment or AlignmentSettings(AlignmentChoice.CALENDAR, 0, 365, Fraction(0)),
        "synthetic-tests-not-acceptance",
        Interval(datetime(2010, 1, 1, tzinfo=UTC), datetime(2030, 1, 1, tzinfo=UTC)),
    )


def construct(pools, settings=None, *, target=Fraction(99, 100), value=8, calendar=TARGET):
    return construct_pattern(
        magnitude(target, value),
        calendar,
        tuple(pools),
        settings or profile(pools, target=target),
        intended_use="exploratory",
        purpose=UsePurpose.SCREENING,
    )


def test_d1_closed_imported_band_uses_full_reference():
    years = tuple(year(n) for n in range(2017, 2021))
    reference = pool(years, (Fraction(92, 100), Fraction(95, 100), Fraction(97, 100), Fraction(99, 100)))
    result = construct((reference,), profile((reference,), band=Fraction(2, 100)))
    assert tuple(c.probability.value for c in result.selected) == (Fraction(97, 100), Fraction(99, 100))
    assert result.membership.probability_centre == Fraction(98, 100)
    assert result.membership.nearest_distance == 0
    assert len(result.exclusions) == 2


def test_d1_empirical_membership_precedes_daily_subset_and_retains_ties():
    years = tuple(
        year(n, (Fraction(v),) * AccountingYear(n, 1, 0).days)
        for n, v in zip(range(2017, 2021), (40, 20, 20, 10), strict=True)
    )
    reference = pool(years, daily_years=years[1:3])
    result = construct(
        (reference,),
        profile((reference,), target=Fraction(1, 2), band=Fraction(0), estimator=MembershipEstimator.EMPIRICAL),
        target=Fraction(1, 2),
    )
    assert tuple(c.probability.value for c in result.selected) == (Fraction(1, 2), Fraction(1, 2))
    assert result.membership.source_count == 2


def test_d2_shape_extrapolation_is_independent_of_numeric_construction():
    reference = pool((year(2018), year(2019)), (Fraction(95, 100), Fraction(97, 100)))
    result = construct((reference,), profile((reference,), band=Fraction(4, 100)))
    assert result.membership.shape_extrapolation is Extrapolation.OUTSIDE_SUPPORT
    assert result.membership.probability_range == (Fraction(95, 100), Fraction(97, 100))
    assert result.membership.nearest_distance == Fraction(2, 100)
    assert len(result.samples) == 365
    assert result.use_checks.finding is not CheckFinding.PASS


def test_d3_five_donors_do_not_manufacture_three_climate_clusters():
    pools = tuple(pool((year(donor=str(i), cluster=str(i % 2)),), (Fraction(97, 100),)) for i in range(5))
    result = construct(pools, profile(pools, clusters=3, band=Fraction(2, 100)))
    assert result.membership.source_count == 5
    assert result.membership.climate_cluster_count == 2
    assert sorted(count for _, count in result.membership.donor_counts) == [1] * 5
    assert result.support.finding is CheckFinding.FAIL
    assert result.volume == Volume(252288000)
    assert result.profile.band == Fraction(2, 100)


def test_d4_d5_equal_year_shares_and_scale_once_on_complete_year():
    a = year(values=(Fraction(1), Fraction(1), Fraction(2), Fraction(0)) + (Fraction(0),) * 361)
    b = year(values=(Fraction(20), Fraction(20), Fraction(0), Fraction(0)) + (Fraction(0),) * 361, donor="b")
    pools = (pool((a,), (Fraction(99, 100),)), pool((b,), (Fraction(99, 100),)))
    result = construct(pools)
    assert (
        result.shape
        == tuple(Fraction(365) * x for x in (Fraction(3, 8), Fraction(3, 8), Fraction(1, 4), Fraction(0)))
        + (Fraction(0),) * 361
    )
    assert tuple(s.value.value for s in result.samples) == tuple(8 * x for x in result.shape)
    assert sum(result.shape) == 365
    assert result.volume == Volume(252288000)
    assert result.selected[0].mapped_shares[:4] == (Fraction(1, 4), Fraction(1, 4), Fraction(1, 2), Fraction(0))
    assert result.selected[1].mapped_shares[:4] == (Fraction(1, 2), Fraction(1, 2), Fraction(0), Fraction(0))


@pytest.mark.parametrize(("number", "expected"), [(2023, 252288000), (2024, 252979200)])
def test_d12_real_calendar_volume(number, expected):
    source = year(number)
    reference = pool((source,), (Fraction(99, 100),))
    result = construct((reference,), calendar=source.calendar)
    assert result.shape == (Fraction(1),) * source.calendar.days
    assert tuple(s.value for s in result.samples) == (Flow(8),) * source.calendar.days
    assert result.volume == Volume(expected)


def test_d1_annual_mean_not_volume_controls_membership_across_leap_years():
    years = (year(2019, (Fraction(1001, 1000),) * 365), year(2020))
    assert sum(years[0].volumes) < sum(years[1].volumes)
    reference = pool(years)
    result = construct(
        (reference,),
        profile((reference,), target=Fraction(1, 3), band=Fraction(0), estimator=MembershipEstimator.EMPIRICAL),
        target=Fraction(1, 3),
    )
    assert tuple(c.source.calendar.year for c in result.selected) == (2019,)


def test_d10_zero_source_stays_in_frequency_but_not_positive_shape():
    years = (year(2018), year(2019, (Fraction(0),) * 365))
    reference = pool(years)
    result = construct(
        (reference,),
        profile((reference,), target=Fraction(1, 2), estimator=MembershipEstimator.EMPIRICAL),
        target=Fraction(1, 2),
    )
    assert result.selected[0].probability.value == Fraction(1, 3)
    assert len(reference.reference.observations) == 2
    assert any("zero source" in reason for e in result.exclusions for reason in e.reasons)
    empty = pool((years[1],), (Fraction(99, 100),))
    unavailable = construct((empty,))
    assert unavailable.method is PatternMethod.UNAVAILABLE
    assert unavailable.samples == ()
    assert unavailable.support.finding is CheckFinding.FAIL


def test_d10_unsupported_zero_target_cannot_claim_zero_exception():
    result = construct_pattern(
        magnitude(value=0), TARGET, (), None, intended_use="exploratory", purpose=UsePurpose.SCREENING
    )
    assert result.method is PatternMethod.UNAVAILABLE
    assert result.shape is None
    assert result.samples == ()
    assert any("zero" in reason for reason in result.reasons)


def test_d13_missing_profile_and_missing_donor_support_remain_attributable():
    reference = pool((year(),), (Fraction(99, 100),))
    result = construct_pattern(
        magnitude(), TARGET, (reference,), None, intended_use="exploratory", purpose=UsePurpose.SCREENING
    )
    assert result.samples == ()
    assert "profile" in result.reasons[0]
    result = construct((reference,), replace(profile((reference,)), donors=()))
    assert result.method is PatternMethod.UNAVAILABLE
    assert any("donor eligibility missing" in e.reasons for e in result.exclusions)


@pytest.mark.parametrize("band", [Fraction(-1, 100), Fraction(101, 100), float("inf"), float("nan")])
def test_d13_invalid_band_refused(band):
    with pytest.raises(ValueError):
        profile((), band=band)


def test_d13_duplicate_and_incompatible_members_refused():
    source = year()
    reference = pool((source,), (Fraction(99, 100),))
    with pytest.raises(ValueError, match="at most once"):
        replace(reference, years=(source, source))
    with pytest.raises(ValueError, match="duplicate donor-year"):
        construct((reference, reference))
    other = pool((year(provenance=replace(PROVENANCE, reference_member="other")),), (Fraction(99, 100),))
    with pytest.raises(ValueError, match="incompatible"):
        construct((other,))
    with pytest.raises(ValueError, match="receiving target/scenario/member"):
        construct((reference,), replace(profile((reference,)), target=ExceedanceProbability(Fraction(1, 2))))


def test_d13_missing_import_or_partial_full_reference_is_not_guessed():
    years = (year(2018), year(2019))
    reference = pool(years, (Fraction(97, 100), Fraction(99, 100)))
    with pytest.raises(ValueError, match="FULL"):
        replace(
            reference,
            imported_membership=replace(
                reference.imported_membership, probabilities=reference.imported_membership.probabilities[:1]
            ),
        )
    with pytest.raises(ValueError, match="missing"):
        construct((replace(reference, imported_membership=None),))


def test_d13_missing_daily_values_are_not_zero():
    source = year()
    missing = replace(source.samples[0], value=None, presence=Presence.MISSING, reasons=("synthetic missing day",))
    with pytest.raises(ValueError, match="missing daily coverage"):
        replace(source, samples=(missing, *source.samples[1:]))
    with pytest.raises(ValueError, match="complete accounting year"):
        replace(source, samples=source.samples[:-1])


def test_d14_crossing_melt_season_uses_original_calendar_set():
    reference = pool((year(),), (Fraction(99, 100),))
    settings = profile((reference,), alignment=AlignmentSettings(AlignmentChoice.MELT, 330, 30, Fraction(20 * 86400)))
    result = construct((reference,), settings)
    baseline = construct((reference,))
    assert result.method is PatternMethod.FALLBACK
    assert result.shape == baseline.shape
    assert result.retained == result.selected
    assert "crosses design-year boundary" in result.reasons[0]


def pulse_year(number, marker, donor):
    values = [Fraction(0)] * AccountingYear(number, 1, 0).days
    values[marker - 1] = values[marker] = Fraction(1)
    return year(number, tuple(values), donor=donor)


def test_d8_simultaneous_exclusion_recompute_and_order_invariance():
    pools = tuple(
        pool(
            tuple(pulse_year(n, marker, str(marker)) for n in (2018, 2019, 2020)),
            (Fraction(1, 10), Fraction(99, 100), Fraction(1, 10)),
        )
        for marker in (60, 80, 100, 104, 110, 140)
    )
    settings = profile(
        pools,
        band=Fraction(0),
        sources=3,
        alignment=AlignmentSettings(AlignmentChoice.MELT, 50, 160, Fraction(20 * 86400)),
    )
    result = construct(pools, settings)
    reversed_pools = tuple(replace(p, years=tuple(reversed(p.years))) for p in reversed(pools))
    reordered = construct(reversed_pools, settings)
    assert result.method is PatternMethod.ALIGNED
    assert result.shape == reordered.shape
    assert result.retained == reordered.retained
    assert {c.source.location.reach.identifier: c.shift_seconds / 86400 for c in result.retained} == {
        "100": Fraction(4),
        "104": Fraction(0),
        "110": Fraction(-6),
    }
    assert tuple(item.median_seconds / 86400 for item in result.alignment_iterations) == (102, 104)
    assert result.alignment_iterations == reordered.alignment_iterations
    aligned_exclusions = {(e.location.reach.identifier, e.iteration) for e in result.exclusions if e.iteration}
    assert aligned_exclusions == {("60", 1), ("80", 1), ("140", 1)}
    assert {
        (e.location.reach.identifier, e.iteration) for e in reordered.exclusions if e.iteration
    } == aligned_exclusions
    assert all(sum(c.retained_shares) == 1 for c in result.retained)
    assert result.volume == Volume(252288000)


def test_d8_missing_shifted_edge_falls_back_without_wrapping():
    pools = tuple(pool((pulse_year(2019, marker, str(marker)),), (Fraction(99, 100),)) for marker in (100, 104))
    settings = profile(
        pools, sources=2, alignment=AlignmentSettings(AlignmentChoice.MELT, 50, 160, Fraction(10 * 86400))
    )
    result = construct(pools, settings)
    assert result.method is PatternMethod.FALLBACK
    assert result.shape == construct(pools).shape
    assert result.retained == result.selected
    assert len([e for e in result.exclusions if e.iteration == 1]) == 2
    assert all(e.reasons for e in result.exclusions)


def test_d11_bounds_cross_without_clipping_or_sorting():
    source = year(values=(Fraction(0), Fraction(2), Fraction(2), Fraction(0)) + (Fraction(0),) * 361)
    low_pool = pool((source,), (Fraction(99, 100),))
    high_pool = pool((year(),), (Fraction(1, 2),))
    low = construct((low_pool,), value=2)
    high = construct((high_pool,), target=Fraction(1, 2), value=3)
    before = tuple(s.value for s in low.samples)
    assert crossed_bounds(low, high) == tuple(s.interval for s in low.samples[1:3])
    assert tuple(s.value for s in low.samples) == before
    assert low.magnitude.value.value < high.magnitude.value.value


def test_d7_d9_real_year_alignment_renormalizes_each_truncated_contribution():
    # Seasonal markers are days 100/104; nonseasonal volume does not move them.
    a_values = [Fraction(0)] * 365
    a_values[99] = a_values[100] = Fraction(1)
    a_values[364] = Fraction(2)
    b_values = [Fraction(0)] * 365
    for day in (103, 104, 200, 201):
        b_values[day] = Fraction(1)
    pools = tuple(
        pool(
            (
                year(2018, (Fraction(0),) * 365, donor=name),
                year(2019, tuple(values), donor=name),
                year(2020, (Fraction(0),) * 366, donor=name),
            ),
            (Fraction(1, 10), Fraction(99, 100), Fraction(1, 10)),
        )
        for name, values in (("a", a_values), ("b", b_values))
    )
    settings = profile(
        pools,
        band=Fraction(0),
        sources=2,
        alignment=AlignmentSettings(AlignmentChoice.MELT, 50, 160, Fraction(10 * 86400)),
    )
    result = construct(pools, settings)
    assert result.method is PatternMethod.ALIGNED
    assert tuple(c.marker_seconds / 86400 for c in result.retained) == (100, 104)
    assert tuple(c.shift_seconds / 86400 for c in result.retained) == (2, -2)
    assert tuple(c.displaced_share for c in result.retained) == (Fraction(1, 2), Fraction(0))
    assert tuple(c.introduced_share for c in result.retained) == (Fraction(0), Fraction(0))
    expected = [Fraction(0)] * 365
    expected[101] = expected[102] = Fraction(3, 8)
    expected[198] = expected[199] = Fraction(1, 8)
    assert result.shape == tuple(365 * x for x in expected)
    assert all(sum(c.retained_shares) == 1 for c in result.retained)
    assert result.volume == Volume(252288000)


def test_d8_missing_context_recomputed_until_stable_without_reinstatement():
    pools = tuple(pool((pulse_year(2019, marker, str(marker)),), (Fraction(99, 100),)) for marker in (100, 104))
    supported = pool(
        tuple(pulse_year(n, 108, "108") for n in (2018, 2019, 2020)),
        (Fraction(1, 10), Fraction(99, 100), Fraction(1, 10)),
    )
    pools = (*pools, supported)
    settings = profile(
        pools, band=Fraction(0), alignment=AlignmentSettings(AlignmentChoice.MELT, 50, 160, Fraction(20 * 86400))
    )
    result = construct(pools, settings)
    reordered = construct(tuple(reversed(pools)), settings)
    assert result.method is PatternMethod.ALIGNED
    assert tuple(c.source.location.reach.identifier for c in result.retained) == ("108",)
    assert result.retained[0].shift_seconds == 0
    assert tuple(item.median_seconds / 86400 for item in result.alignment_iterations) == (104, 106, 108)
    assert tuple(item.iteration for item in result.alignment_iterations) == (1, 2, 3)
    assert tuple(
        {loc.reach.identifier: shift / 86400 for loc, _, shift in item.shifts} for item in result.alignment_iterations
    ) == ({"100": 4, "104": 0, "108": -4}, {"104": 2, "108": -2}, {"108": 0})
    assert tuple(
        tuple(e.location.reach.identifier for e in item.exclusions) for item in result.alignment_iterations
    ) == (("100",), ("104",), ())
    assert result.alignment_iterations == reordered.alignment_iterations
    assert {(e.location.reach.identifier, e.iteration) for e in result.exclusions if e.iteration} == {
        ("100", 1),
        ("104", 2),
    }
    assert result.retained == reordered.retained
    assert result.shape == reordered.shape


def test_d6_complete_year_february_mapping_preserves_monthly_share():
    values = [Fraction(0)] * 365
    values[31] = Fraction(1)
    reference = pool((year(2019, tuple(values)),), (Fraction(99, 100),))
    result = construct((reference,), calendar=AccountingYear(2024, 1, 0))
    mapped = result.selected[0].mapped_shares
    assert mapped[31:33] == (Fraction(28, 29), Fraction(1, 29))
    assert sum(mapped[31:60]) == sum(mapped) == 1
    assert all(value == 0 for value in (*mapped[:31], *mapped[33:]))
    assert result.volume == Volume(252979200)
    assert any("not newly observed" in reason for reason in result.samples[0].provenance.limitations)


@pytest.mark.parametrize("invalid", [-1, float("inf"), float("nan")])
def test_d13_invalid_daily_flow_refused_at_input_boundary(invalid):
    with pytest.raises(ValueError):
        year(values=(invalid,) + (Fraction(1),) * 364)


def test_supported_import_preserves_complete_schedule_and_never_rescales():
    reference = pool((year(),), (Fraction(99, 100),))
    original = construct((reference,))
    result = import_pattern(
        original.magnitude,
        original.calendar,
        tuple(reversed(original.samples)),
        original.magnitude.derivation,
        intended_use="exploratory",
        purpose=UsePurpose.SCREENING,
    )
    assert result.method is PatternMethod.IMPORTED
    assert result.samples == original.samples
    assert result.shape == original.shape
    assert result.volume == Volume(252288000)
    assert result.selected == result.retained == ()
    assert result.use_checks.finding is not CheckFinding.PASS
    assert any("import equation:" in reason for reason in result.reasons)
    assert any("import uncertainty:" in reason for reason in result.reasons)


@pytest.mark.parametrize("failure", ["mean", "identity", "partial-year", "partial-day", "missing-day"])
def test_import_refuses_wrong_mean_identity_and_coverage(failure):
    reference = pool((year(),), (Fraction(99, 100),))
    original = construct((reference,))
    samples = original.samples
    expected = ""
    if failure == "mean":
        samples = (replace(samples[0], value=Flow(9)), *samples[1:])
        expected = "no silent scaling"
    elif failure == "identity":
        samples = tuple(replace(s, provenance=replace(s.provenance, reference_member="other")) for s in samples)
        expected = "incompatible"
    elif failure == "partial-year":
        samples = samples[:-1]
        expected = "complete daily accounting year"
    elif failure == "partial-day":
        samples = (replace(samples[0], coverage=Coverage.PARTIAL, reasons=("synthetic partial day",)), *samples[1:])
        expected = "unsupported daily coverage"
    elif failure == "missing-day":
        samples = (
            replace(samples[0], value=None, presence=Presence.MISSING, reasons=("synthetic missing day",)),
            *samples[1:],
        )
        expected = "unsupported daily coverage"
    with pytest.raises(ValueError, match=expected):
        import_pattern(
            original.magnitude,
            original.calendar,
            samples,
            original.magnitude.derivation,
            intended_use="exploratory",
            purpose=UsePurpose.SCREENING,
        )


def synthetic_acceptance(subject):
    """Hypothetical external study; declared 1-unit maxima pass at equality.

    The frozen record precedes the supplied withheld diagnostics. This exercises
    permission plumbing, not scientific certification of these synthetic rivers.
    """
    contracts = ((EvidenceRequirement.DISTRIBUTION, "m3/s", "annual-mean-error"),)
    if subject.kind is HydrologicalProductKind.DAILY_PATTERN:
        contracts = (
            (EvidenceRequirement.SEASONAL_SHARES, "percent", "season-volume/annual-volume*100"),
            (EvidenceRequirement.TIMING, "days", "first-half-volume-time-nonwrapping"),
            (EvidenceRequirement.MINIMA, "m3/s", "minimum-complete-seven-day-mean"),
            (EvidenceRequirement.SPELLS, "days", "longest-strict-below-fixed-threshold"),
        )
    cases = ("heldout-climate-2010", "heldout-climate-2011")
    criteria = tuple(
        ScientificCriterion(
            requirement.value,
            CriterionRole.MANDATORY,
            formula,
            "synthetic withheld year",
            units,
            ErrorMeasure.ABSOLUTE,
            Aggregation.EACH_CASE,
            Comparison.AT_MOST,
            1.0,
            cases,
            "hypothetical test distinction of one unit, not a policy threshold",
            requirement,
        )
        for requirement, units, formula in contracts
    )
    record = AcceptanceRecord(
        subject,
        "synthetic-acceptance-v1",
        "preparer",
        "independent-reviewer",
        datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 9, 4, tzinfo=UTC),
        criteria,
        "synthetic sampling and rating uncertainty with declared coverage",
        ("structural alternatives",),
        "synthetic screening only",
        (subject.scope.intended_use,),
        (),
        "new independent evidence required",
    )
    observations = tuple(
        DiagnosticObservation(
            c.criterion_id,
            case,
            1.0,
            0.0,
            c.units,
            c.formula,
            c.domain,
            "hypothetical withheld independent diagnostics",
        )
        for c in record.criteria
        for case in cases
    )
    validation = ValidationEvidence(
        ValidationMethod.WITHHELD,
        ("training-climate-2000",),
        cases,
        (),
        (),
        ("training-case",),
        cases,
        ("training-climate-2000",),
        cases,
        ("heldout-donor",),
        ("shared-rating-error",),
        datetime(2026, 9, 3, tzinfo=UTC),
        "caller-owned whole climate-year holdouts",
    )
    items = tuple(
        EvidenceItem(
            requirement,
            CheckFinding.PASS,
            "synthetic external study",
            "explicit hypothetical supported finding; not empirical site certification",
        )
        for requirement in minimum_evidence(subject, DailyDerivation.NATIVE)
    )
    evidence = ScientificEvidence(
        subject,
        record.profile_version,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        OfficialAdmissibility.PENDING,
        items,
        observations,
        validation,
        RatingSupport.WITHIN_RANGE,
        ClimateTreatment.COMMON_BASIS,
        DailyDerivation.NATIVE,
        frozen_record=record,
    )
    assessment = assess_scientific_use(record, evidence)
    assert assessment.findings.scientific_adequacy is ScientificAdequacy.ACCEPTED
    assert assessment.acceptance_for(subject).finding is CheckFinding.PASS
    assert all(c.actual == c.criterion.limit == 1.0 for c in assessment.comparisons)
    return assessment


@pytest.mark.parametrize("calendar", [AccountingYear(2023, 1, 0), AccountingYear(2024, 1, 0)])
def test_d10_accepted_zero_bypasses_profile_and_positive_source_support(calendar):
    annual = magnitude(value=0)
    subject = annual_magnitude_product(annual, intended_use="screen", purpose=UsePurpose.SCREENING)
    assessment = synthetic_acceptance(subject)
    result = construct_pattern(
        annual, calendar, (), None, intended_use="screen", purpose=UsePurpose.SCREENING, magnitude_assessment=assessment
    )
    assert result.method is PatternMethod.ZERO
    assert result.shape is None
    assert result.selected == result.retained == ()
    assert tuple(s.value for s in result.samples) == (Flow(0),) * calendar.days
    assert result.volume == Volume(0)
    assert result.use_checks.finding is CheckFinding.PASS
    assert result.magnitude_evidence == assessment.findings
    assert result.magnitude_evidence is not None
    assert result.magnitude_evidence.official_admissibility is OfficialAdmissibility.PENDING


@pytest.mark.parametrize("changed", ["target", "member", "profile", "scenario"])
def test_d10_accepted_zero_permission_never_transfers_identity(changed):
    annual = magnitude(value=0)
    subject = annual_magnitude_product(annual, intended_use="screen", purpose=UsePurpose.SCREENING)
    if changed == "target":
        subject = replace(subject, target_probability=0.5)
    elif changed == "member":
        subject = replace(
            subject,
            scope=replace(subject.scope, member="other"),
            provenance=replace(subject.provenance, reference_member="other"),
        )
    elif changed == "profile":
        subject = replace(subject, scope=replace(subject.scope, product=subject.scope.product + ":other-profile"))
    elif changed == "scenario":
        subject = replace(subject, provenance=replace(subject.provenance, scenario="other"))
    assessment = synthetic_acceptance(subject)
    result = construct_pattern(
        annual, TARGET, (), None, intended_use="screen", purpose=UsePurpose.SCREENING, magnitude_assessment=assessment
    )
    assert result.method is PatternMethod.UNAVAILABLE
    assert result.samples == ()
    assert result.shape is None
    assert result.use_checks.finding is not CheckFinding.PASS


def test_supported_positive_pattern_accepts_its_exact_public_product():
    reference = pool((year(),), (Fraction(99, 100),))
    annual = magnitude()
    settings = replace(profile((reference,)), acceptance_profile="synthetic-acceptance-v1")
    annual_assessment = synthetic_acceptance(
        annual_magnitude_product(annual, intended_use="screen", purpose=UsePurpose.SCREENING)
    )
    exploratory = construct_pattern(
        annual,
        TARGET,
        (reference,),
        settings,
        intended_use="screen",
        purpose=UsePurpose.SCREENING,
        magnitude_assessment=annual_assessment,
    )
    assert exploratory.use_checks.finding is not CheckFinding.PASS
    subject = pattern_product(exploratory, intended_use="screen", purpose=UsePurpose.SCREENING)
    daily_assessment = synthetic_acceptance(subject)
    accepted = construct_pattern(
        annual,
        TARGET,
        (reference,),
        settings,
        intended_use="screen",
        purpose=UsePurpose.SCREENING,
        magnitude_assessment=annual_assessment,
        shape_assessment=daily_assessment,
    )
    assert accepted.samples == exploratory.samples
    assert accepted.shape == exploratory.shape
    assert accepted.use_checks.finding is CheckFinding.PASS
    assert accepted.shape_evidence is not None
    assert accepted.shape_evidence.scientific_adequacy is ScientificAdequacy.ACCEPTED
    # Mean/volume closure alone did not grant this separate daily permission.
    assert accepted.volume == exploratory.volume == Volume(252288000)


def test_d1_fitted_membership_uses_full_zero_mixture_reference_before_subset():
    # Symmetric positive logs of [1/2,1,2] give mu=0; with pi0=1/4,
    # the positive median has exceedance (1-pi0)/2 = 3/8 exactly.
    # Fitting only this available daily year would be degenerate, not 3/8.
    years = tuple(
        year(n, (value,) * AccountingYear(n, 1, 0).days)
        for n, value in zip(range(2017, 2021), (Fraction(0), Fraction(1, 2), Fraction(1), Fraction(2)), strict=True)
    )
    reference = pool(years, daily_years=(years[2],))
    settings = profile((reference,), target=Fraction(3, 8), band=Fraction(0), estimator=MembershipEstimator.FITTED)
    result = construct((reference,), settings, target=Fraction(3, 8))
    assert tuple(c.probability.value for c in result.selected) == (Fraction(3, 8),)
    assert result.selected[0].source == years[2]
    assert result.membership.shape_extrapolation is Extrapolation.WITHIN_SUPPORT
    assert result.volume == Volume(252288000)


def test_d13_degenerate_full_reference_cannot_claim_fitted_membership():
    reference = pool((year(2018), year(2019)))
    settings = profile((reference,), estimator=MembershipEstimator.FITTED)
    with pytest.raises(ValueError, match="fitted membership unavailable"):
        construct((reference,), settings)


def test_d13_full_source_reference_must_fit_frozen_profile_period():
    years = (year(2018), year(2019))
    reference = pool(years, (Fraction(97, 100), Fraction(99, 100)), daily_years=(years[1],))
    settings = replace(profile((reference,)), reference_period=years[1].calendar.interval)
    # The available daily year lies inside the profile, but its FULL frequency
    # reference also contains 2018. That omitted year cannot be silently ignored.
    with pytest.raises(ValueError, match="reference period"):
        construct((reference,), settings)


def test_scientific_shape_record_must_match_frozen_acceptance_profile():
    reference = pool((year(),), (Fraction(99, 100),))
    annual = magnitude()
    settings = profile((reference,))
    annual_assessment = synthetic_acceptance(
        annual_magnitude_product(annual, intended_use="screen", purpose=UsePurpose.SCREENING)
    )
    exploratory = construct_pattern(
        annual,
        TARGET,
        (reference,),
        settings,
        intended_use="screen",
        purpose=UsePurpose.SCREENING,
        magnitude_assessment=annual_assessment,
    )
    daily_assessment = synthetic_acceptance(
        pattern_product(exploratory, intended_use="screen", purpose=UsePurpose.SCREENING)
    )
    assert daily_assessment.record.profile_version != settings.acceptance_profile
    result = construct_pattern(
        annual,
        TARGET,
        (reference,),
        settings,
        intended_use="screen",
        purpose=UsePurpose.SCREENING,
        magnitude_assessment=annual_assessment,
        shape_assessment=daily_assessment,
    )
    assert result.samples == exploratory.samples
    assert result.use_checks.finding is CheckFinding.UNKNOWN
    assert next(c for c in result.use_checks.checks if c.check_id == "daily_shape").finding is CheckFinding.UNKNOWN


def test_d8_adjacent_context_uses_original_source_total_through_public_boundary():
    pools = []
    for donor, marker in (("a", 100), ("b", 104)):
        left = [Fraction(0)] * 365
        right = [Fraction(0)] * 366
        if donor == "a":
            left[-1] = Fraction(2)
        else:
            right[0] = Fraction(4)
        pools.append(
            pool(
                (
                    year(2018, tuple(left), donor=donor),
                    pulse_year(2019, marker, donor),
                    year(2020, tuple(right), donor=donor),
                ),
                (Fraction(1, 10), Fraction(99, 100), Fraction(1, 10)),
            )
        )
    settings = profile(
        tuple(pools),
        band=Fraction(0),
        sources=2,
        alignment=AlignmentSettings(AlignmentChoice.MELT, 50, 160, Fraction(10 * 86400)),
    )
    result = construct(tuple(pools), settings)
    assert result.method is PatternMethod.ALIGNED
    assert tuple(c.shift_seconds / 86400 for c in result.retained) == (2, -2)
    # Selected source totals are both2. The actual imported edge volumes2/4
    # therefore contribute shares1/2, not independently normalized padding1/1.
    assert tuple(c.introduced_share for c in result.retained) == (Fraction(1), Fraction(2))
    assert tuple(c.displaced_share for c in result.retained) == (Fraction(0), Fraction(0))
    expected = [Fraction(0)] * 365
    expected[1] = Fraction(1, 4)
    expected[101] = expected[102] = Fraction(5, 24)
    expected[363] = Fraction(1, 3)
    assert result.shape == tuple(365 * x for x in expected)
    assert result.volume == Volume(252288000)


def test_d12_non_january_fixed_offset_complete_pattern():
    calendar = AccountingYear(2023, 10, 330)
    reference = pool((year(calendar=calendar),), (Fraction(99, 100),))
    annual = magnitude(reference_calendar=calendar)
    result = construct_pattern(
        annual, calendar, (reference,), profile((reference,)), intended_use="screen", purpose=UsePurpose.SCREENING
    )
    assert result.calendar == calendar
    assert result.samples[0].interval.start == datetime(2023, 9, 30, 18, 30, tzinfo=UTC)
    assert result.samples[-1].interval.end == datetime(2024, 9, 30, 18, 30, tzinfo=UTC)
    assert result.shape == (Fraction(1),) * 366
    assert tuple(s.value for s in result.samples) == (Flow(8),) * 366
    assert result.volume == Volume(252979200)


def test_import_refuses_observed_daily_values_for_natural_magnitude():
    original = construct((pool((year(),), (Fraction(99, 100),)),))
    observed = tuple(
        replace(s, provenance=replace(s.provenance, reference_kind=ReferenceKind.OBSERVED)) for s in original.samples
    )
    with pytest.raises(ValueError, match="incompatible|natural"):
        import_pattern(
            original.magnitude,
            original.calendar,
            observed,
            original.magnitude.derivation,
            intended_use="screen",
            purpose=UsePurpose.SCREENING,
        )


def test_import_cannot_relabel_consistent_observed_only_reference_as_natural_pattern():
    original = construct((pool((year(),), (Fraction(99, 100),)),))
    observed_provenance = replace(PROVENANCE, reference_kind=ReferenceKind.OBSERVED)
    annual_reference = replace(
        original.magnitude.reference,
        observations=tuple(
            replace(s, provenance=observed_provenance) for s in original.magnitude.reference.observations
        ),
    )
    annual = import_annual_estimate(
        annual_reference,
        original.magnitude.target,
        Flow(8),
        estimator=AnnualEstimator.IMPORTED_STATIONARY,
        profile_version="observed-annual-v1",
        provenance=observed_provenance,
        derivation=original.magnitude.derivation,
    )
    samples = tuple(replace(s, provenance=observed_provenance) for s in original.samples)
    with pytest.raises(ValueError, match="natural"):
        import_pattern(
            annual, original.calendar, samples, annual.derivation, intended_use="screen", purpose=UsePurpose.SCREENING
        )


def test_illustrative_inputs_remain_explicitly_illustrative_after_construction():
    reference = pool((year(),), (Fraction(99, 100),))
    result = construct((reference,))
    assert result.magnitude.provenance.production_method is ProductionMethod.ILLUSTRATIVE
    assert all(c.source.provenance.production_method is ProductionMethod.ILLUSTRATIVE for c in result.retained)
    assert tuple(s.provenance.production_method for s in result.samples) == (ProductionMethod.ILLUSTRATIVE,) * 365
