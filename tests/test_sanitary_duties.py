from dataclasses import replace
from datetime import timedelta

import pytest

from examples.sanitary_assessment import main, synthetic_inputs
from fishy.duties import Deliverability, Delivery, DutyApplicability, Requirement, assess_feasibility
from fishy.evidence import Check, CheckFinding, CheckSummary, Completeness
from fishy.flows import Presence
from fishy.quantities import Flow, Volume
from fishy.sanitary_duties import (
    Authenticity,
    CombinedAssessment,
    Currency,
    EcologicalRequirementAssessment,
    RequirementConflict,
    SanitaryDuty,
    assess_sanitary_duty,
)
from fishy.sanitary_hydraulics import TemporalSupport
from fishy.time import Interval


def assess(supplied, deliveries=(), findings=()):
    return assess_sanitary_duty(
        supplied, deliveries, candidate="candidate-1", scenario="scenario-1", hydraulic_findings=findings
    )


def passing_delivery(supplied):
    return tuple(Delivery(item.sample, "delivery-1") for item in supplied.duty.schedule)


def test_executable_sanitary_only_and_combined_example(capsys):
    main()
    assert "43200" in capsys.readouterr().out


def test_s1_shortfall_exact_and_s4_complete_import_success_failure_and_unknown():
    supplied, delivered, findings = synthetic_inputs()
    failed = assess(supplied, delivered)
    assert tuple(row.shortfall for row in failed.flow_and_components.intervals) == (Flow(".5"), Flow(0))
    assert failed.flow_and_components.known_shortfall_volume == Volume(43200)
    assert failed.summary.finding is CheckFinding.FAIL
    assert failed.summary.completeness is Completeness.INCOMPLETE
    unresolved = assess(supplied, passing_delivery(supplied))
    assert unresolved.summary.finding is CheckFinding.UNKNOWN
    success = assess(supplied, passing_delivery(supplied), findings)
    assert success.summary.finding is CheckFinding.PASS
    assert success.summary.completeness is Completeness.COMPLETE
    hydraulic_failure = assess(supplied, passing_delivery(supplied), (replace(findings[0], finding=CheckFinding.FAIL),))
    assert hydraulic_failure.summary.finding is CheckFinding.FAIL
    assert hydraulic_failure.summary.completeness is Completeness.INCOMPLETE
    assert success.hydraulic_findings == findings
    assert success.supplied.instrument.currency is Currency.UNRESOLVED


def test_missing_schedule_preserves_supported_hydraulic_failure_nonflow_can_pass():
    supplied, _, findings = synthetic_inputs()
    absent = replace(supplied, duty=replace(supplied.duty, schedule=()))
    failure = assess(absent, findings=(replace(findings[0], finding=CheckFinding.FAIL),))
    assert failure.summary.finding is CheckFinding.FAIL
    assert failure.summary.completeness is Completeness.INCOMPLETE
    assert failure.summary.checks[0].check_id == "discharge"
    assert failure.summary.checks[0].finding is CheckFinding.UNKNOWN
    nonflow = replace(
        absent, duty=replace(absent.duty, required_components=tuple(s.component for s in absent.hydraulic_components))
    )
    assert assess(nonflow, findings=findings).summary.finding is CheckFinding.PASS


@pytest.mark.parametrize("outcome", tuple(DutyApplicability))
def test_inventory_outcomes_authenticity_currency_and_applicability_are_distinct(outcome):
    supplied, _, findings = synthetic_inputs()
    duty = replace(supplied.duty, applicability=outcome, reasons=("dated search and named follow-up",))
    instrument = supplied.instrument
    if outcome is DutyApplicability.APPLICABLE:
        instrument = replace(instrument, authenticity=Authenticity.AUTHENTICATED, currency=Currency.IN_FORCE)
    record = replace(supplied, duty=duty, instrument=instrument)
    result = assess(record, passing_delivery(record), findings)
    assert result.supplied.duty.applicability is outcome
    if outcome in (DutyApplicability.APPLICABLE, DutyApplicability.HYPOTHETICAL):
        assert result.summary.finding is CheckFinding.PASS
    else:
        assert result.summary.finding is CheckFinding.UNKNOWN
    if outcome is DutyApplicability.UNRESOLVED:
        assert len(result.flow_and_components.intervals) == 2
        assert any(
            check.check_id == "stage_change" and check.finding is CheckFinding.PASS for check in result.summary.checks
        )
    assert result.hydraulic_findings == findings


def test_unauthenticated_or_outdated_instrument_cannot_become_binding():
    supplied, _, _ = synthetic_inputs()
    with pytest.raises(ValueError, match="binding applicability"):
        replace(supplied, duty=replace(supplied.duty, applicability=DutyApplicability.APPLICABLE))
    authenticated = replace(supplied.instrument, authenticity=Authenticity.AUTHENTICATED)
    with pytest.raises(ValueError, match="binding applicability"):
        replace(
            supplied, instrument=authenticated, duty=replace(supplied.duty, applicability=DutyApplicability.APPLICABLE)
        )


def test_scope_mismatch_and_daily_only_cannot_certify_within_day():
    supplied, _, findings = synthetic_inputs()
    daily = replace(findings[3], scope=replace(findings[3].scope, temporal_support=TemporalSupport.DAILY_MEANS))
    result = assess(supplied, passing_delivery(supplied), (*findings[:3], daily, findings[4]))
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.summary.checks[-2].finding is CheckFinding.UNKNOWN
    with pytest.raises(ValueError, match="candidate/scenario"):
        assess_sanitary_duty(supplied, (), candidate="another", scenario="scenario-1")
    with pytest.raises(ValueError, match="delivery scenario"):
        assess(
            supplied,
            (
                replace(
                    passing_delivery(supplied)[0],
                    sample=replace(
                        supplied.duty.schedule[0].sample,
                        provenance=replace(supplied.duty.schedule[0].sample.provenance, scenario="other"),
                    ),
                ),
            ),
        )
    with pytest.raises(TypeError, match="attributable"):
        assess(supplied, findings=(Check("stage_change", CheckFinding.PASS),))
    with pytest.raises(ValueError, match="duplicate"):
        assess(supplied, findings=(findings[0], findings[0]))


def test_s5_independent_versions_locations_conflicts_no_sum_or_maximum_and_shortage_no_rewrite():
    supplied, delivered, findings = synthetic_inputs()
    first = assess(supplied, delivered, findings)
    next_duty = replace(
        supplied.duty,
        version="issued-2",
        schedule=tuple(replace(item, version="issued-2") for item in supplied.duty.schedule),
    )
    second = assess(replace(supplied, duty=next_duty), delivered, findings)
    ecological_sample = replace(
        delivered[0].sample,
        location=replace(delivered[0].sample.location, mapping_version="other-control-point"),
        value=Flow(8),
    )
    ecological = EcologicalRequirementAssessment(
        "ecological",
        "independent method",
        "candidate-1",
        "scenario-1",
        (Requirement(ecological_sample, "eco-v1"),),
        CheckSummary((Check("habitat", CheckFinding.FAIL),)),
    )
    conflict = RequirementConflict(
        "sanitary-instrument@issued-1", "ecological", "joint study-1", "incompatible supplied conditions"
    )
    combined = CombinedAssessment((first, second), (ecological,), (conflict,))
    assert combined.sanitary == (first, second)
    assert combined.ecological[0].requirements[0].sample.value == Flow(8)
    assert combined.conflicts == (conflict,)
    assert first.supplied.duty.schedule[0].sample.value == Flow(2)
    shortage = assess_feasibility(
        supplied.duty, tuple(Deliverability(item.sample, "availability-v1") for item in delivered)
    )
    assert shortage.duty == supplied.duty
    assert shortage.intervals[0].shortfall == Flow(".5")
    with pytest.raises(ValueError, match="same candidate"):
        CombinedAssessment((first,), (replace(ecological, candidate="other"),))
    with pytest.raises(ValueError, match="duplicate"):
        CombinedAssessment((first, first))


@pytest.mark.parametrize("presence", (Presence.MISSING, Presence.OUTSIDE_HORIZON, Presence.UNSUPPORTED))
def test_s1_presence_is_preserved_and_does_not_cancel_known_failure(presence):
    supplied, deliveries, _ = synthetic_inputs()
    unknown = replace(
        deliveries[1], sample=replace(deliveries[1].sample, value=None, presence=presence, reasons=("unavailable",))
    )
    result = assess(supplied, (deliveries[0], unknown))
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert result.flow_and_components.intervals[1].shortfall is None


def test_s1_zero_and_mismatched_interval_or_location():
    supplied, deliveries, _ = synthetic_inputs()
    zero = replace(deliveries[0], sample=replace(deliveries[0].sample, value=Flow(0)))
    assert assess(supplied, (zero,)).flow_and_components.intervals[0].shortfall == Flow(2)
    sample = deliveries[0].sample
    for wrong in (
        replace(sample, location=replace(sample.location, mapping_version="wrong")),
        replace(sample, interval=Interval(sample.interval.start, sample.interval.end + timedelta(hours=1))),
    ):
        with pytest.raises(ValueError):
            assess(supplied, (replace(deliveries[0], sample=wrong),))


def test_empty_components_cannot_manufacture_satisfaction():
    supplied, _, _ = synthetic_inputs()
    empty = SanitaryDuty(replace(supplied.duty, schedule=(), required_components=()), supplied.instrument, ())
    assert assess(empty).summary.finding is CheckFinding.UNKNOWN


def test_hypothetical_profile_changes_do_not_rewrite_other_methods_or_prior_duties():
    from datetime import UTC, datetime

    from fishy.evidence import EvidenceScope
    from fishy.residual_flow import statutory_minimum
    from fishy.sanitary_profile import (
        ProfileAttribution,
        SeasonalMinimum,
        SeasonalWindows,
        SeasonWindow,
        imported_sanitary_profile,
        nominated_sanitary_profile,
    )

    supplied, delivered, findings = synthetic_inputs()
    issued_result = assess(supplied, delivered, findings)
    foreign = statutory_minimum(Flow(160, "l/s"))
    period = Interval(datetime(2020, 1, 1, tzinfo=UTC), datetime(2021, 1, 1, tzinfo=UTC))
    provenance = findings[0].evidence.provenance
    evidence = replace(findings[0].evidence, scope=EvidenceScope("imported-profile", "reach", None, period, "scenario"))
    attribution = ProfileAttribution("imported-profile", findings[0].scope.location, period, provenance, evidence, UTC)
    windows = SeasonalWindows(SeasonWindow((7, 1), (7, 3)), SeasonWindow((1, 1), (1, 3)))
    original = imported_sanitary_profile(
        attribution,
        "external method-v1",
        windows,
        SeasonalMinimum(windows.summer, Flow(2), ()),
        SeasonalMinimum(windows.winter, Flow(3), ()),
    )
    alternative = imported_sanitary_profile(
        replace(
            attribution,
            provenance=replace(provenance, configuration_version="v2"),
            evidence=replace(evidence, provenance=replace(provenance, configuration_version="v2")),
        ),
        "external method-v2",
        windows,
        SeasonalMinimum(windows.summer, Flow(0), ()),
        SeasonalMinimum(windows.winter, Flow(1), ()),
    )
    pending = nominated_sanitary_profile((), attribution, 2020, None, None)
    assert pending.presence is Presence.MISSING
    assert original.summer is not None and original.summer.value == Flow(2)
    assert alternative.summer is not None and alternative.summer.value == Flow(0)
    assert original.interpretation == "external method-v1"
    assert statutory_minimum(Flow(160, "l/s")) == foreign == Flow(130, "l/s")
    assert assess(supplied, delivered, findings) == issued_result
    assert issued_result.flow_and_components.known_shortfall_volume == Volume(43200)
