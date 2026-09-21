"""Exact synthetic sanitary D.1 witnesses, not scientific or legal certification."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from fractions import Fraction
from zoneinfo import ZoneInfo

import pytest

from fishy.evidence import (
    Completeness,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    ScientificAdequacy,
    UseRestriction,
)
from fishy.flows import Coverage, FlowSample, Presence
from fishy.quantities import Flow
from fishy.sanitary_profile import (
    ProfileAttribution,
    ProfileMethod,
    SeasonalMinimum,
    SeasonalWindows,
    SeasonWindow,
    annual_sanitary_profile,
    imported_sanitary_profile,
    nominated_sanitary_profile,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

LOCATION = Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "1")
PROVENANCE = Provenance(
    "synthetic reconstruction",
    "scenario",
    "member",
    "test",
    "1",
    "1",
    ProductionMethod.RECONSTRUCTED,
    CorrectionState.ORIGINAL,
    ReferenceKind.NATURALISED_HISTORICAL,
    limitations=("rating range unresolved", "dependence and climate relevance retained"),
)
WINDOWS = SeasonalWindows(SeasonWindow((7, 1), (8, 31)), SeasonWindow((1, 1), (2, 28)))


def attribution(start=2001, end=2020, offset=UTC, provenance=PROVENANCE):
    period = Interval(datetime(start, 1, 1, tzinfo=offset), datetime(end, 1, 1, tzinfo=offset))
    evidence = EvidenceFindings(
        EvidenceScope("profile-v1", "reach", provenance.reference_member, period, "indicative sanitary scenario"),
        provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("synthetic evidence only",),
        (UseRestriction("rating range", ("official sizing",)),),
    )
    return ProfileAttribution("profile-v1", LOCATION, period, provenance, evidence, offset)


def series(attr, value):
    day = attr.reference_period.start.astimezone(attr.fixed_offset)
    end = attr.reference_period.end.astimezone(attr.fixed_offset)
    result = []
    while day < end:
        result.append(
            FlowSample(
                attr.location,
                Interval(day, day + timedelta(days=1)),
                Flow(value(day)),
                Presence.PRESENT,
                attr.provenance,
            )
        )
        day += timedelta(days=1)
    return tuple(result)


def witness(day):
    if day.year != 2019:
        return 2021 - day.year
    return {(1, 1): Fraction(3, 5), (7, 1): Fraction(9, 10)}.get((day.month, day.day), Fraction(1457, 726))


@pytest.mark.parametrize("offset", [UTC, timezone(timedelta(hours=5))])
def test_complete_annual_selection_exact_witness_and_fixed_offset(offset):
    attr = attribution(offset=offset)
    samples = series(attr, witness)
    result = annual_sanitary_profile(samples, attr, WINDOWS)
    assert result.selected_year == 2019
    assert result.selected_rank is not None
    assert result.winter is not None and result.summer is not None
    assert result.selected_rank.mean == Flow(2)
    assert result.selected_rank.probability == Fraction(19, 20)
    assert result.winter.value == Flow("0.6")
    assert result.summer.value == Flow("0.9")
    assert result.winter.dates == (date(2019, 1, 1),)
    assert result.summer.dates == (date(2019, 7, 1),)
    assert result.value_on(date(2024, 8, 31)) == Flow("0.9")
    assert result.value_on(date(2024, 9, 1)) is None
    assert result.value_on(date(2024, 6, 30)) is None
    assert result.attribution.evidence == attr.evidence
    assert result.attribution.provenance.limitations == PROVENANCE.limitations
    assert (
        sum(
            s.interval.start.astimezone(offset).day == 29 and s.interval.start.astimezone(offset).month == 2
            for s in result.samples
        )
        == 4
    )


def test_support_before_rounding_and_ties_reduce_support():
    attr = attribution(end=2019)
    result = annual_sanitary_profile(series(attr, witness), attr, WINDOWS)
    assert max(r.probability for r in result.annual_ranks) == Fraction(18, 19)
    assert round(float(Fraction(18, 19)), 2) == 0.95
    assert result.presence is Presence.UNSUPPORTED
    assert result.completeness is Completeness.INCOMPLETE
    assert result.summer is None and result.selected_year is None
    attr = attribution()
    result = annual_sanitary_profile(series(attr, lambda d: max(2, 2020 - d.year)), attr, WINDOWS)
    assert max(r.probability for r in result.annual_ranks) == Fraction(37, 40)
    assert result.presence is Presence.UNSUPPORTED


def test_equal_distance_prefers_larger_probability_and_tied_years_earliest():
    attr = attribution(end=2030)
    result = annual_sanitary_profile(series(attr, lambda d: 2031 - d.year), attr, WINDOWS)
    assert result.selected_year == 2029
    assert result.selected_rank is not None
    assert result.selected_rank.probability == Fraction(29, 30)
    assert tuple(r.year for r in result.tied_candidates) == (2028, 2029)
    attr = attribution(end=2031)
    result = annual_sanitary_profile(series(attr, lambda d: max(2, 2031 - d.year)), attr, WINDOWS)
    assert result.selected_year == 2029
    assert result.selected_rank is not None
    assert tuple(r.year for r in result.tied_candidates) == (2029, 2030)
    assert result.selected_rank.rank == Fraction(59, 2)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "partial", "unsupported", "identity", "location", "hour"])
def test_invalid_daily_evidence_stops_calculation(mutation):
    attr = attribution()
    samples = series(attr, witness)
    first = samples[0]
    if mutation == "missing":
        samples = samples[:59] + samples[60:]
    elif mutation == "duplicate":
        samples += samples[:1]
    else:
        changes = {
            "partial": {"coverage": Coverage.PARTIAL, "reasons": ("partial",)},
            "unsupported": {"presence": Presence.UNSUPPORTED, "reasons": ("unsupported",)},
            "identity": {"provenance": replace(PROVENANCE, reference_member="other")},
            "location": {"location": replace(LOCATION, section=CalculationSection("elsewhere", "1"))},
            "hour": {"interval": Interval(first.interval.start, first.interval.start + timedelta(hours=1))},
        }
        samples = (replace(first, **changes[mutation]),) + samples[1:]
    with pytest.raises(ValueError):
        annual_sanitary_profile(samples, attr, WINDOWS)


def test_leap_day_completeness_window_validity_and_dst_rejection():
    attr = attribution(2000, 2001)
    samples = series(attr, lambda _: 1)
    assert len(samples) == 366
    with pytest.raises(ValueError, match="missing day"):
        annual_sanitary_profile(
            tuple(s for s in samples if s.interval.start.date() != date(2000, 2, 29)), attr, WINDOWS
        )
    leap_windows = SeasonalWindows(WINDOWS.summer, SeasonWindow((2, 29), (2, 29)))
    assert annual_sanitary_profile(samples, attr, leap_windows).presence is Presence.UNSUPPORTED
    attr = attribution(2001, 2002)
    with pytest.raises(ValueError):
        annual_sanitary_profile(series(attr, lambda _: 1), attr, leap_windows)
    with pytest.raises(TypeError, match="DST"):
        replace(attr, fixed_offset=ZoneInfo("Europe/Zurich"))
    with pytest.raises(ValueError, match="overlap"):
        SeasonalWindows(WINDOWS.summer, SeasonWindow((8, 31), (9, 1)))
    for endpoints in [((12, 1), (2, 1)), ((2, 30), (3, 1))]:
        with pytest.raises(ValueError):
            SeasonWindow(*endpoints)


def test_nomination_import_zero_and_pending_do_not_claim_annual_selection():
    attr = attribution(2020, 2021)
    windows = SeasonalWindows(SeasonWindow((7, 1), (7, 3)), SeasonWindow((1, 1), (1, 3)))
    values = {(7, 1): 4, (7, 2): 2, (7, 3): 5, (1, 1): 6, (1, 2): 3, (1, 3): 7}
    samples = tuple(
        s
        for s in series(attr, lambda d: values.get((d.month, d.day), 100))
        if (s.interval.start.month, s.interval.start.day) in values
    )
    result = nominated_sanitary_profile(samples, attr, 2020, windows, "nomination study v1")
    assert result.summer is not None and result.winter is not None
    assert (result.summer.value, result.winter.value) == (Flow(2), Flow(3))
    assert result.selected_year == 2020 and not result.annual_ranks
    assert result.interpretation == "nomination study v1"
    assert result.method is ProfileMethod.NOMINATED_YEAR
    imported = imported_sanitary_profile(
        attr,
        "external fitted method v3",
        windows,
        SeasonalMinimum(windows.summer, Flow(0), ()),
        SeasonalMinimum(windows.winter, Flow(3), ()),
    )
    assert imported.method is ProfileMethod.IMPORTED
    assert imported.interpretation == "external fitted method v3"
    assert imported.value_on(date(2020, 7, 1)) == Flow(0)
    assert not imported.annual_ranks and imported.selected_year is None
    pending = nominated_sanitary_profile((), attr, 2020, None, None)
    assert pending.presence is Presence.MISSING and pending.completeness is Completeness.INCOMPLETE
    assert imported_sanitary_profile(attr, None, None, None, None).presence is Presence.MISSING
    with pytest.raises(ValueError, match="missing day"):
        nominated_sanitary_profile(samples[1:], attr, 2020, windows, "study")


def test_evidence_identity_and_invalid_quantities_are_rejected():
    attr = attribution()
    for changes in (
        {"identifier": "another"},
        {"provenance": replace(PROVENANCE, scenario="other")},
        {"location": replace(LOCATION, reach=Reach("other", "1", LOCATION.reach.water_body))},
    ):
        with pytest.raises(ValueError, match="evidence"):
            replace(attr, **changes)
    for value in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            Flow(value)


def test_independent_failed_member_remains_visible_without_comparison():
    good = attribution()
    bad = attribution(end=2019, provenance=replace(PROVENANCE, reference_member="failed-member"))
    results = (
        annual_sanitary_profile(series(good, witness), good, WINDOWS),
        annual_sanitary_profile(series(bad, witness), bad, WINDOWS),
    )
    assert tuple(r.presence for r in results) == (Presence.PRESENT, Presence.UNSUPPORTED)
    assert tuple(r.attribution.provenance.reference_member for r in results) == ("member", "failed-member")
    assert any(r.completeness is Completeness.INCOMPLETE for r in results)


def test_import_minimum_dates_cannot_escape_reference_period():
    attr = attribution(2020, 2021)
    with pytest.raises(ValueError, match="reference period"):
        imported_sanitary_profile(
            attr,
            "study",
            WINDOWS,
            SeasonalMinimum(WINDOWS.summer, Flow(2), (date(2019, 7, 1),)),
            SeasonalMinimum(WINDOWS.winter, Flow(3), ()),
        )


@pytest.mark.parametrize("status", ["invalid", "not_computable"])
def test_invalid_numerical_evidence_cannot_support_import_or_calculation(status):
    attr = attribution(2020, 2021)
    evidence = replace(
        attr.evidence,
        **(
            {"numerical_validity": NumericalValidity.INVALID}
            if status == "invalid"
            else {"computability": Computability.NOT_COMPUTABLE}
        ),
    )
    attr = replace(attr, evidence=evidence)
    result = imported_sanitary_profile(
        attr,
        "study",
        WINDOWS,
        SeasonalMinimum(WINDOWS.summer, Flow(2), ()),
        SeasonalMinimum(WINDOWS.winter, Flow(3), ()),
    )
    assert result.presence is Presence.UNSUPPORTED
    assert result.completeness is Completeness.INCOMPLETE
    with pytest.raises(ValueError, match="numerical evidence"):
        annual_sanitary_profile(series(attr, lambda _: 1), attr, WINDOWS)
