"""ReviewEvidence × CalculationDate → RevisionAssessment; OperationalFlows → AdjustmentAssessment.

Pure Order 179 temporal, study-review and supplied actual-year adjustment assessments.
No function chooses an operational regime or rewrites an issued design allocation.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    Provenance,
    aggregate_checks,
    permitted_use,
    warmup_restrictions,
)
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, interval_use
from fishy.quantities import Volume, interval_volume


def _date(value: date) -> None:
    if type(value) is not date:
        raise TypeError("a calendar date is required")


class Applicability(StrEnum):
    IN_FORCE = "in_force"
    NOT_YET_IN_FORCE = "not_yet_in_force"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FirstPublication:
    published_on: date
    evidence: Provenance

    def __post_init__(self) -> None:
        _date(self.published_on)
        if not isinstance(self.evidence, Provenance):
            raise TypeError("first official publication requires provenance")


@dataclass(frozen=True)
class TemporalApplicability:
    calculated_on: date
    paragraph: int
    source: Provenance
    publication: FirstPublication | None
    effective_on: date | None
    status: Applicability
    reason: str


def order179_applicability(
    calculated_on: date,
    paragraph: int,
    source: Provenance,
    publication: FirstPublication | None = None,
) -> TemporalApplicability:
    """Enactment clause 4: after first publication; paragraph 11 from 2027-01-01.

    Publication evidence is supplied, not inferred from registration or PDF upload.
    This comparison neither authenticates the evidence nor establishes source currency.
    """
    _date(calculated_on)
    if type(paragraph) is not int or not 1 <= paragraph <= 32:
        raise ValueError("methodology paragraph must be an integer from 1 to 32")
    if not isinstance(source, Provenance):
        raise TypeError("source requires Provenance")
    if publication is not None and not isinstance(publication, FirstPublication):
        raise TypeError("publication requires FirstPublication")
    effective = (
        date(2027, 1, 1)
        if paragraph == 11
        else (publication.published_on + timedelta(days=1) if publication is not None else None)
    )
    status = (
        Applicability.UNKNOWN
        if effective is None
        else Applicability.IN_FORCE
        if calculated_on >= effective
        else Applicability.NOT_YET_IN_FORCE
    )
    return TemporalApplicability(
        calculated_on,
        paragraph,
        source,
        publication,
        effective,
        status,
        "paragraph 11 deferred to 2027-01-01"
        if paragraph == 11
        else "first official publication not supplied"
        if publication is None
        else "commencement on the day after supplied first official publication",
    )


class ChangeState(StrEnum):
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BasinChange:
    state: ChangeState
    evidence: Provenance | None

    def __post_init__(self) -> None:
        if not isinstance(self.state, ChangeState):
            raise TypeError("change state requires ChangeState")
        if self.evidence is not None and not isinstance(self.evidence, Provenance):
            raise TypeError("change evidence requires Provenance")
        if self.state is not ChangeState.UNKNOWN and self.evidence is None:
            raise ValueError("known change or no-change finding requires evidence")


@dataclass(frozen=True)
class StudyReview:
    reviewed_on: date
    evidence: Provenance

    def __post_init__(self) -> None:
        _date(self.reviewed_on)
        if not isinstance(self.evidence, Provenance):
            raise TypeError("study-based review requires provenance")


class RevisionState(StrEnum):
    REQUIRED = "required"
    NOT_DUE = "not_due"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RevisionAssessment:
    applicability: TemporalApplicability
    last_study: StudyReview | None
    basin_conditions: BasinChange
    new_evidence: BasinChange
    review_due: date | None
    state: RevisionState
    checks: CheckSummary


def assess_review(
    applicability: TemporalApplicability,
    last_study: StudyReview | None,
    basin_conditions: BasinChange,
    new_evidence: BasinChange,
) -> RevisionAssessment:
    """Paragraph 23 trigger inventory, separately retaining legal applicability.

    Five calendar years, with February 29 anniversaries due on February 28.
    FAIL means a revision trigger exists, not ecological failure. Missing inventories
    cannot erase a known trigger. A future review cannot reset the clock.
    """
    if applicability.paragraph != 23:
        raise ValueError("review assessment requires paragraph 23 applicability")
    if last_study is not None and not isinstance(last_study, StudyReview):
        raise TypeError("last_study requires StudyReview")
    if not isinstance(basin_conditions, BasinChange) or not isinstance(new_evidence, BasinChange):
        raise TypeError("change inventories require BasinChange")
    due = None
    if last_study is not None:
        previous = last_study.reviewed_on
        if previous > applicability.calculated_on:
            raise ValueError("study review is after calculation date")
        # Explicit conservative calendar convention for the leap-day anniversary.
        due = date(
            previous.year + 5, previous.month, 28 if previous.month == 2 and previous.day == 29 else previous.day
        )
    checks = [
        Check(
            "five_year_study_review",
            CheckFinding.UNKNOWN
            if due is None
            else CheckFinding.FAIL
            if applicability.calculated_on >= due
            else CheckFinding.PASS,
            ("study review evidence missing" if due is None else "five-calendar-year study review deadline",),
        )
    ]
    for name, change in (("basin_conditions", basin_conditions), ("new_evidence", new_evidence)):
        checks.append(
            Check(
                name,
                {
                    ChangeState.UNKNOWN: CheckFinding.UNKNOWN,
                    ChangeState.CHANGED: CheckFinding.FAIL,
                    ChangeState.UNCHANGED: CheckFinding.PASS,
                }[change.state],
                (change.state.value,),
            )
        )
    summary = aggregate_checks(("five_year_study_review", "basin_conditions", "new_evidence"), tuple(checks))
    state = {
        CheckFinding.FAIL: RevisionState.REQUIRED,
        CheckFinding.PASS: RevisionState.NOT_DUE,
        CheckFinding.UNKNOWN: RevisionState.UNKNOWN,
    }[summary.finding]
    return RevisionAssessment(applicability, last_study, basin_conditions, new_evidence, due, state, summary)


@dataclass(frozen=True)
class ActualYearEvidence:
    """Separate issue-versioned current conditions and forecast findings for one use."""

    issued_on: date
    forecast: EvidenceFindings | None
    current_conditions: EvidenceFindings | None
    decision: Provenance

    def __post_init__(self) -> None:
        _date(self.issued_on)
        if not isinstance(self.decision, Provenance):
            raise TypeError("operational decision requires Provenance")
        for finding in (self.forecast, self.current_conditions):
            if finding is not None and not isinstance(finding, EvidenceFindings):
                raise TypeError("operational evidence requires EvidenceFindings")


@dataclass(frozen=True)
class AdjustmentAssessment:
    applicability: TemporalApplicability
    baseline: FlowSample
    adjusted: FlowSample
    scope: EvidenceScope
    evidence: ActualYearEvidence | None
    checks: CheckSummary
    baseline_volume: Volume | None
    adjusted_volume: Volume | None
    volume_change_m3: Fraction | None


def _supported_volume(sample: FlowSample) -> Volume | None:
    if (
        sample.presence is not Presence.PRESENT
        or sample.coverage is not Coverage.COMPLETE
        or interval_use(sample) is not IntervalUse.ELIGIBLE
        or sample.value is None
    ):
        return None
    return interval_volume(sample.value, sample.interval)


def assess_actual_year_adjustment(
    applicability: TemporalApplicability,
    baseline: FlowSample,
    adjusted: FlowSample,
    scope: EvidenceScope,
    evidence: ActualYearEvidence | None,
) -> AdjustmentAssessment:
    """Assess a supplied paragraph 9 decision; do not invent its adjustment relation.

    Compute supported interval volumes independently of scientific/official acceptance.
    A positive assessment means evidence supports this supplied candidate, not that
    every ecological constraint passed or an official duty has been issued.
    """
    if applicability.paragraph != 9:
        raise ValueError("actual-year adjustment requires paragraph 9 applicability")
    if any(
        getattr(baseline.provenance, field) != getattr(adjusted.provenance, field)
        for field in ("scenario", "reference_member", "reference_kind")
    ):
        raise ValueError("operational change must preserve scenario and reference identity")
    if baseline.location != adjusted.location or baseline.interval != adjusted.interval:
        raise ValueError("operational candidate must match baseline location and interval")
    if (
        scope.reach != adjusted.location.reach.identifier
        or scope.period != adjusted.interval
        or scope.member != adjusted.provenance.reference_member
    ):
        raise ValueError("requested scope must match operational flow identity")
    if evidence is not None:
        if evidence.issued_on > applicability.calculated_on:
            raise ValueError("operational evidence was issued after calculation date")
        if evidence.decision != adjusted.provenance:
            raise ValueError("adjusted flow must retain operational decision provenance")
    checks = []
    for name in ("forecast", "current_conditions"):
        finding = getattr(evidence, name) if evidence is not None else None
        if finding is None:
            checks.append(Check(name, CheckFinding.UNKNOWN, ("required operational evidence missing",)))
        elif finding.provenance.scenario != adjusted.provenance.scenario:
            checks.append(Check(name, CheckFinding.UNKNOWN, ("operational evidence scenario mismatch",)))
        elif finding.provenance.reference_member != scope.member:
            checks.append(Check(name, CheckFinding.UNKNOWN, ("operational evidence reference member mismatch",)))
        elif reasons := warmup_restrictions(finding.provenance, scope.period):
            checks.append(Check(name, CheckFinding.UNKNOWN, reasons))
        else:
            check = permitted_use(finding, scope)
            checks.append(Check(name, check.finding, check.reasons))
    before, after = _supported_volume(baseline), _supported_volume(adjusted)
    checks.append(
        Check(
            "flow_support",
            CheckFinding.PASS if before is not None and after is not None else CheckFinding.UNKNOWN,
            ("interval flow support; no subinterval inference",),
        )
    )
    summary = aggregate_checks(("forecast", "current_conditions", "flow_support"), tuple(checks))
    return AdjustmentAssessment(
        applicability,
        baseline,
        adjusted,
        scope,
        evidence,
        summary,
        before,
        after,
        after.value - before.value if before is not None and after is not None else None,
    )
