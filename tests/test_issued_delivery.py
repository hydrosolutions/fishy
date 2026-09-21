"""Proposed Uzbek issuance and supported delivery tests, separate from independent duties."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from examples.issued_duty import scenario, scenario_evidence
from fishy.comparison_evidence import MarginBounds, NumericalFinding
from fishy.delivery_assessment import assess_issued_delivery
from fishy.duties import (
    Availability,
    Deliverability,
    DutyApplicability,
    Requirement,
    SuppliedDuty,
    assess_duty,
)
from fishy.evidence import Check, CheckFinding, CheckSummary, Completeness
from fishy.flows import Coverage, Presence
from fishy.quantities import Flow, FlowBounds, Volume
from fishy.uzbek_issuance import issue_obligation


def test_c4_immutable_issued_values_and_independent_sanitary_foreign_duties():
    issue, result, prohibition = scenario(datetime(2020, 2, 29, tzinfo=UTC))
    assert issue.requirement.sample.value == Flow(10)
    assert issue.deliverability.sample.value == Flow(6)
    assert issue.obligation.sample.value == Flow(6)
    assert issue.ecological_deficit == Flow(4)
    assert result.raw_shortfall == Flow(1)
    assert result.raw_shortfall_volume == Volume(86400)
    assert result.margin == MarginBounds(-1, -1)
    assert result.numerical is NumericalFinding.BELOW
    assert result.official.finding is CheckFinding.UNKNOWN
    later = replace(result.actual, sample=replace(result.actual.sample, value=Flow(2), uncertainty=None), version="v2")
    comparison = assess_issued_delivery(issue.obligation, later, evidence=scenario_evidence(issue.obligation, later))
    assert comparison.raw_shortfall == Flow(4)
    assert comparison.numerical is NumericalFinding.UNAVAILABLE
    assert issue.obligation.sample.value == Flow(6)
    assert prohibition.floor.sample.value == Flow(8)
    with pytest.raises(FrozenInstanceError):
        issue.obligation.version = "revised"
    # Neither existing independent duty is recapped by this profile.
    for instrument in ("sanitary", "foreign"):
        independent = SuppliedDuty(
            instrument,
            "issued-v1",
            "supplied instrument",
            DutyApplicability.HYPOTHETICAL,
            (replace(issue.obligation, sample=issue.requirement.sample),),
            "located schedule",
        )
        nominal = assess_duty(independent, (result.actual,))
        assert nominal.intervals[0].shortfall == Flow(5)
        assert nominal.duty.schedule[0].sample.value == Flow(10)


@pytest.mark.parametrize(
    "lower,upper,expected",
    [
        ("4", "5.9", NumericalFinding.BELOW),
        ("5", "6", NumericalFinding.INDETERMINATE),
        ("5", "7", NumericalFinding.INDETERMINATE),
        ("6", "6", NumericalFinding.NOT_BELOW),
        ("6", "9", NumericalFinding.NOT_BELOW),
        ("0", "0", NumericalFinding.BELOW),
    ],
)
def test_supported_delivery_bounds_and_equality(lower, upper, expected):
    issue, result, _ = scenario(datetime(2020, 2, 29, tzinfo=UTC))
    lo, hi = Flow(lower), Flow(upper)
    actual = replace(
        result.actual,
        sample=replace(
            result.actual.sample,
            value=Flow((lo.value + hi.value) / 2),
            uncertainty=FlowBounds(lo, hi, "enclosing support", "scenario-v1", "no joint confidence claim"),
        ),
    )
    compared = assess_issued_delivery(issue.obligation, actual, evidence=scenario_evidence(issue.obligation, actual))
    assert compared.numerical is expected


def test_complete_leap_year_has_no_surplus_offset_and_known_failure_survives_missing_day():
    start = datetime(2020, 1, 1, tzinfo=UTC)
    end = datetime(2021, 1, 1, tzinfo=UTC)
    days = tuple(start + timedelta(days=i) for i in range((end - start).days))
    results = tuple(scenario(day)[1] for day in days)
    assert len(results) == 366
    assert results[59].obligation.sample.interval.start == datetime(2020, 2, 29, tzinfo=UTC)
    assert results[-1].obligation.sample.interval.end == end
    assert sum(row.raw_shortfall_volume.value for row in results) == Volume(366 * 86400).value
    gap = results[100]
    missing = assess_issued_delivery(gap.obligation, None, evidence=scenario_evidence(gap.obligation, None))
    assert missing.numerical is NumericalFinding.UNAVAILABLE
    # No annual resampling/renormalisation: one check per required real day.
    rows = (*results[:100], missing, *results[101:])
    checks = tuple(
        Check(str(i), CheckFinding.FAIL if row.numerical is NumericalFinding.BELOW else CheckFinding.UNKNOWN)
        for i, row in enumerate(rows)
    )
    summary = CheckSummary(checks)
    assert summary.finding is CheckFinding.FAIL
    assert summary.completeness is Completeness.INCOMPLETE
    high = replace(results[1].actual, sample=replace(results[1].actual.sample, value=Flow(100), uncertainty=None))
    surplus = assess_issued_delivery(
        results[1].obligation, high, evidence=scenario_evidence(results[1].obligation, high)
    )
    assert surplus.raw_shortfall == Flow(0)
    assert results[0].raw_shortfall == Flow(1)


@pytest.mark.parametrize("check_id", ["coverage", "infill", "authentication", "reconciliation", "uncertainty"])
def test_rejected_admission_is_unavailable_even_with_supported_numeric_shortfall(check_id):
    issue, result, _ = scenario(datetime(2020, 2, 29, tzinfo=UTC))
    evidence = scenario_evidence(issue.obligation, result.actual)
    checks = tuple(
        replace(c, finding=CheckFinding.FAIL, reasons=("evidence rejected",)) if c.check_id == check_id else c
        for c in evidence.checks
    )
    result = assess_issued_delivery(issue.obligation, result.actual, evidence=replace(evidence, checks=checks))
    assert result.numerical is NumericalFinding.UNAVAILABLE
    assert result.raw_shortfall == Flow(1)


def test_floor_only_or_actual_or_availability_cannot_be_issuance_operand():
    issue, delivery, floor = scenario(datetime(2020, 2, 29, tzinfo=UTC))
    for role in (floor.floor, delivery.actual, Availability(issue.requirement.sample, "available-v1")):
        with pytest.raises(TypeError, match="Requirement and Deliverability"):
            issue_obligation(role, issue.deliverability, version="bad", provenance=issue.obligation.sample.provenance)  # ty: ignore[invalid-argument-type] -- intentional boundary rejection
    with pytest.raises(TypeError, match="Requirement and Deliverability"):
        issue_obligation(
            issue.requirement, delivery.actual, version="bad", provenance=issue.obligation.sample.provenance
        )
    with pytest.raises(TypeError, match="Obligation"):
        assess_issued_delivery(floor.floor, delivery.actual, evidence=floor.evidence)


@pytest.mark.parametrize("role", ["requirement", "deliverability"])
@pytest.mark.parametrize("missing", ["value", "coverage", "warmup"])
def test_incomplete_issuance_operands_refused(role, missing):
    issue, _, _ = scenario(datetime(2020, 2, 29, tzinfo=UTC))
    original = getattr(issue, role)
    sample = original.sample
    if missing == "value":
        sample = replace(sample, value=None, uncertainty=None, presence=Presence.MISSING, reasons=("absent input",))
    elif missing == "coverage":
        sample = replace(sample, coverage=Coverage.PARTIAL, reasons=("half-day only",))
    else:
        sample = replace(sample, provenance=replace(sample.provenance, excluded_warmup=(sample.interval,)))
    changed = replace(original, sample=sample)
    with pytest.raises(ValueError, match="complete supported"):
        issue_obligation(
            changed if role == "requirement" else issue.requirement,
            changed if role == "deliverability" else issue.deliverability,
            version="v2",
            provenance=issue.obligation.sample.provenance,
        )


def test_new_issuance_retains_old_and_rejects_scenario_interval_version_evidence_reuse():
    old, actual, floor = scenario(datetime(2020, 2, 29, tzinfo=UTC))
    new_requirement = Requirement(replace(old.requirement.sample, value=Flow(12), uncertainty=None), "requirement-v2")
    new = issue_obligation(
        new_requirement,
        old.deliverability,
        version="issued-v2",
        provenance=replace(old.obligation.sample.provenance, configuration_version="profile-v2"),
    )
    assert new.ecological_deficit == Flow(6)
    assert old.ecological_deficit == Flow(4)
    assert old.obligation.sample.provenance.configuration_version == "assumptions-v1"
    assert floor.floor.sample.value == Flow(8)
    with pytest.raises(ValueError, match="exact delivery operands"):
        assess_issued_delivery(new.obligation, actual.actual, evidence=actual.evidence)
    bad_capacity = Deliverability(
        replace(
            old.deliverability.sample,
            provenance=replace(old.deliverability.sample.provenance, scenario="foreign-profile"),
        ),
        "v2",
    )
    with pytest.raises(ValueError, match="mix scenarios"):
        issue_obligation(old.requirement, bad_capacity, version="v2", provenance=old.obligation.sample.provenance)
    next_day = scenario(datetime(2020, 3, 1, tzinfo=UTC))[0]
    with pytest.raises(ValueError, match="exact location and interval"):
        issue_obligation(
            old.requirement, next_day.deliverability, version="v2", provenance=old.obligation.sample.provenance
        )


def test_delivered_obligation_does_not_license_below_floor_abstraction():
    from fishy.floor_assessment import assess_floor

    issue, delivery, floor = scenario(datetime(2020, 2, 29, tzinfo=UTC))
    actual = replace(
        delivery.actual,
        sample=replace(
            delivery.actual.sample,
            value=Flow(6),
            uncertainty=FlowBounds(Flow(6), Flow(6), "fixed fictional actual", "scenario-v1", "fixed support"),
        ),
    )
    delivered = assess_issued_delivery(issue.obligation, actual, evidence=scenario_evidence(issue.obligation, actual))
    compared = assess_floor(
        floor.floor, actual, floor.but_for, evidence=scenario_evidence(floor.floor, actual, floor.but_for)
    )
    assert delivered.numerical is NumericalFinding.NOT_BELOW
    assert compared.numerical is NumericalFinding.BELOW
    assert compared.margin == MarginBounds(-2, -2)
    assert compared.floor.sample.value == Flow(8)
