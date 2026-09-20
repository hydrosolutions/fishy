"""Order 179 temporal, five-year review and operational evidence discriminators."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime
from fractions import Fraction

import pytest

from fishy.evidence import (
    CheckFinding,
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
from fishy.kazakh_review import (
    ActualYearEvidence,
    Applicability,
    BasinChange,
    ChangeState,
    FirstPublication,
    RevisionState,
    StudyReview,
    assess_actual_year_adjustment,
    assess_review,
    order179_applicability,
)
from fishy.quantities import Flow, Volume
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

P = Provenance(
    "Order 179",
    "synthetic",
    "reference",
    "test",
    "held-2025",
    "v1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
)
PUBLICATION = FirstPublication(date(2025, 7, 30), P)  # hypothetical, not a claimed publication date
LOCATION = Location(Reach("reach", "v1", WaterBody("river", "v1")), CalculationSection("section", "v1"), "v1")
PERIOD = Interval(datetime(2028, 2, 1, tzinfo=UTC), datetime(2028, 3, 1, tzinfo=UTC))
SCOPE = EvidenceScope("actual-year adjustment", "reach", "reference", PERIOD, "operational scenario")
UNCHANGED = BasinChange(ChangeState.UNCHANGED, P)
UNKNOWN = BasinChange(ChangeState.UNKNOWN, None)


def finding(**changes):
    base = EvidenceFindings(
        SCOPE,
        P,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        (),
    )
    return replace(base, **changes)


def operational():
    before = FlowSample(LOCATION, PERIOD, Flow(10), Presence.PRESENT, P)
    decision = replace(
        P, source="forecast-based decision", data_version="forecast-issue-2", configuration_version="op-v2"
    )
    after = replace(before, value=Flow(8), provenance=decision)
    evidence = ActualYearEvidence(date(2028, 1, 20), finding(), finding(), decision)
    applicability = order179_applicability(date(2028, 1, 21), 9, P, PUBLICATION)
    return applicability, before, after, evidence


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 12, 31), Applicability.NOT_YET_IN_FORCE),
        (date(2027, 1, 1), Applicability.IN_FORCE),
    ],
)
def test_deferred_paragraph_11_without_publication(day, expected):
    result = order179_applicability(day, 11, P)
    assert result.status is expected
    assert result.effective_on == date(2027, 1, 1)
    assert result.source == P


@pytest.mark.parametrize("paragraph", [4, 9, 10, 12, 23, 32])
def test_other_provisions_require_publication_and_start_after_its_day(paragraph):
    assert order179_applicability(date(2030, 1, 1), paragraph, P).status is Applicability.UNKNOWN
    assert (
        order179_applicability(PUBLICATION.published_on, paragraph, P, PUBLICATION).status
        is Applicability.NOT_YET_IN_FORCE
    )
    assert order179_applicability(date(2025, 7, 31), paragraph, P, PUBLICATION).status is Applicability.IN_FORCE


@pytest.mark.parametrize("paragraph", [0, 33, True, 11.0])
def test_invalid_paragraph(paragraph):
    with pytest.raises(ValueError):
        order179_applicability(date(2028, 1, 1), paragraph, P)


@pytest.mark.parametrize(
    ("day", "state"),
    [
        (date(2030, 7, 30), RevisionState.NOT_DUE),
        (date(2030, 7, 31), RevisionState.REQUIRED),
    ],
)
def test_five_calendar_year_deadline_inclusive(day, state):
    result = assess_review(
        order179_applicability(day, 23, P, PUBLICATION), StudyReview(date(2025, 7, 31), P), UNCHANGED, UNCHANGED
    )
    assert result.review_due == date(2030, 7, 31)
    assert result.state is state
    assert result.checks.completeness is Completeness.COMPLETE


def test_known_basin_trigger_survives_missing_study_and_new_evidence_inventory():
    result = assess_review(
        order179_applicability(date(2028, 1, 1), 23, P), None, BasinChange(ChangeState.CHANGED, P), UNKNOWN
    )
    assert result.state is RevisionState.REQUIRED
    assert result.checks.completeness is Completeness.INCOMPLETE
    assert result.applicability.status is Applicability.UNKNOWN
    assert result.review_due is None


def test_new_evidence_triggers_even_when_recent_study():
    result = assess_review(
        order179_applicability(date(2028, 1, 1), 23, P),
        StudyReview(date(2027, 12, 1), P),
        UNCHANGED,
        BasinChange(ChangeState.CHANGED, P),
    )
    assert result.state is RevisionState.REQUIRED


def test_missing_review_cannot_pass_and_leap_anniversary_is_explicit():
    applicability = order179_applicability(date(2033, 2, 28), 23, P)
    assert assess_review(applicability, None, UNCHANGED, UNCHANGED).state is RevisionState.UNKNOWN
    result = assess_review(applicability, StudyReview(date(2028, 2, 29), P), UNCHANGED, UNCHANGED)
    assert result.review_due == date(2033, 2, 28)
    assert result.state is RevisionState.REQUIRED
    with pytest.raises(ValueError, match="after calculation"):
        assess_review(applicability, StudyReview(date(2034, 1, 1), P), UNCHANGED, UNCHANGED)


def test_successful_supplied_actual_year_decision_exact_leap_month_volumes():
    applicability, before, after, evidence = operational()
    result = assess_actual_year_adjustment(applicability, before, after, SCOPE, evidence)
    assert result.checks.finding is CheckFinding.PASS
    assert result.baseline_volume == Volume(25056000)
    assert result.adjusted_volume == Volume(20044800)
    assert result.volume_change_m3 == Fraction(-5011200)
    assert result.evidence is not None
    assert result.evidence.forecast is not None
    assert result.evidence.forecast.official_admissibility is OfficialAdmissibility.PENDING
    assert before.value == Flow(10)
    assert result.adjusted.provenance.data_version == "forecast-issue-2"
    with pytest.raises(FrozenInstanceError):
        result.baseline = after  # ty: ignore[invalid-assignment]
    later = replace(evidence, decision=replace(after.provenance, data_version="forecast-issue-3"))
    new_result = assess_actual_year_adjustment(
        applicability, before, replace(after, value=Flow(9), provenance=later.decision), SCOPE, later
    )
    assert new_result.adjusted_volume == Volume(22550400)
    assert result.adjusted_volume == Volume(20044800)


def test_missing_operational_evidence_keeps_arithmetic_but_not_pass():
    applicability, before, after, _ = operational()
    result = assess_actual_year_adjustment(applicability, before, after, SCOPE, None)
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.checks.completeness is Completeness.INCOMPLETE
    assert result.adjusted_volume == Volume(20044800)


def test_known_evidence_restriction_survives_missing_forecast():
    applicability, before, after, evidence = operational()
    restricted = finding(restrictions=(UseRestriction("rating invalid", (SCOPE.intended_use,)),))
    result = assess_actual_year_adjustment(
        applicability, before, after, SCOPE, replace(evidence, forecast=None, current_conditions=restricted)
    )
    assert result.checks.finding is CheckFinding.FAIL
    assert result.checks.completeness is Completeness.INCOMPLETE


@pytest.mark.parametrize(
    "change",
    [
        {"scope": replace(SCOPE, product="another product")},
        {"provenance": replace(P, scenario="other")},
        {"scientific_adequacy": ScientificAdequacy.UNKNOWN},
    ],
)
def test_unmatched_or_unaccepted_evidence_cannot_pass(change):
    applicability, before, after, evidence = operational()
    result = assess_actual_year_adjustment(
        applicability, before, after, SCOPE, replace(evidence, forecast=finding(**change))
    )
    assert result.checks.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize("presence", [Presence.MISSING, Presence.OUTSIDE_HORIZON, Presence.UNSUPPORTED])
def test_absence_is_not_zero(presence):
    applicability, before, after, evidence = operational()
    after = replace(after, value=None, presence=presence, reasons=("not supplied",))
    result = assess_actual_year_adjustment(applicability, before, after, SCOPE, evidence)
    assert result.adjusted.presence is presence
    assert result.adjusted_volume is None
    assert result.baseline_volume == Volume(25056000)
    assert result.volume_change_m3 is None
    assert result.checks.finding is CheckFinding.UNKNOWN


def test_present_zero_partial_and_warmup_support():
    applicability, before, after, evidence = operational()
    zero = assess_actual_year_adjustment(applicability, before, replace(after, value=Flow(0)), SCOPE, evidence)
    assert zero.adjusted_volume == Volume(0)
    assert zero.checks.finding is CheckFinding.PASS
    partial = assess_actual_year_adjustment(
        applicability, before, replace(after, coverage=Coverage.PARTIAL, reasons=("gap",)), SCOPE, evidence
    )
    assert partial.adjusted_volume is None
    warm = replace(before, provenance=replace(P, excluded_warmup=(PERIOD,)))
    assert assess_actual_year_adjustment(applicability, warm, after, SCOPE, evidence).baseline_volume is None


def test_wrong_identity_future_issue_or_unversioned_decision_rejected():
    applicability, before, after, evidence = operational()
    with pytest.raises(ValueError, match="location"):
        assess_actual_year_adjustment(
            applicability, before, replace(after, location=replace(LOCATION, mapping_version="v2")), SCOPE, evidence
        )
    with pytest.raises(ValueError, match="scope"):
        assess_actual_year_adjustment(applicability, before, after, replace(SCOPE, reach="elsewhere"), evidence)
    with pytest.raises(ValueError, match="issued after"):
        assess_actual_year_adjustment(
            applicability, before, after, SCOPE, replace(evidence, issued_on=date(2029, 1, 1))
        )
    with pytest.raises(ValueError, match="provenance"):
        assess_actual_year_adjustment(applicability, before, after, SCOPE, replace(evidence, decision=P))


def test_operational_change_cannot_mix_reference_or_scenario():
    applicability, before, after, evidence = operational()
    for field in ("reference_member", "scenario", "reference_kind"):
        value = "different" if field != "reference_kind" else ReferenceKind.FUTURE_CLIMATE_STRESS
        with pytest.raises(ValueError, match="reference identity"):
            assess_actual_year_adjustment(
                applicability, replace(before, provenance=replace(P, **{field: value})), after, SCOPE, evidence
            )


@pytest.mark.parametrize(
    "provenance",
    [
        replace(P, excluded_warmup=(PERIOD,)),
        replace(P, reference_member="different-reference"),
    ],
)
def test_operational_evidence_provenance_cannot_override_scope_support(provenance):
    applicability, before, after, evidence = operational()
    result = assess_actual_year_adjustment(
        applicability,
        before,
        after,
        SCOPE,
        replace(evidence, forecast=finding(provenance=provenance)),
    )
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.checks.completeness is Completeness.INCOMPLETE
    assert result.adjusted_volume == Volume(20044800)


def test_excluded_forecast_does_not_erase_known_current_conditions_failure():
    applicability, before, after, evidence = operational()
    restricted = finding(restrictions=(UseRestriction("not accepted for sizing", (SCOPE.intended_use,)),))
    result = assess_actual_year_adjustment(
        applicability,
        before,
        after,
        SCOPE,
        replace(
            evidence, forecast=finding(provenance=replace(P, excluded_warmup=(PERIOD,))), current_conditions=restricted
        ),
    )
    assert result.checks.finding is CheckFinding.FAIL
    assert result.checks.completeness is Completeness.INCOMPLETE
