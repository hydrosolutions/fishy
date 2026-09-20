"""Synthetic witnesses for GSchG Art.31(2), no site calibration or legal approval."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from fishy.evidence import (
    CheckFinding,
    Completeness,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ScientificAdequacy,
)
from fishy.flows import FlowSample, Presence
from fishy.quantities import Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.swiss_safeguards import (
    Elevation,
    FishFunction,
    FlowNeed,
    HabitatReplacement,
    Safeguard,
    SafeguardSite,
    SafeguardStudy,
    SafeguardTreatment,
    assess_safeguards,
    safeguard_study_scope,
)
from fishy.time import Interval


def site(q=160, elevation=700, fish=FishFunction.SPAWNING_OR_REARING, identifier="downstream"):
    period = Interval(datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 2, 1, tzinfo=UTC))
    location = Location(Reach("reach", "v1", WaterBody("river", "v1")), CalculationSection(identifier, "v1"), "v1")
    provenance = Provenance(
        "synthetic starting minimum",
        "scenario-a",
        "member-a",
        "v1",
        "v1",
        "v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )
    sample = FlowSample(location, period, Flow(130, "l/s"), Presence.PRESENT, provenance)
    return SafeguardSite(
        identifier, sample, Flow(q, "l/s"), Elevation(elevation), fish, "synthetic affected-reach inventory"
    )


def study(s, safeguard, total=130, treatment=SafeguardTreatment.FLOW_REQUIREMENT, **kwargs):
    need = (
        FlowNeed(Flow(total, "l/s"), Flow(0), Flow(1), "supplied site inversion", "specialist-selected criterion")
        if treatment is SafeguardTreatment.FLOW_REQUIREMENT
        else None
    )
    findings = EvidenceFindings(
        safeguard_study_scope(s, safeguard, treatment, need, kwargs.get("measure"), kwargs.get("replacement")),
        s.starting_minimum.provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("synthetic accepted scenario relationship",),
    )
    return SafeguardStudy(
        s.identifier,
        safeguard,
        s.starting_minimum.location,
        findings,
        treatment,
        "synthetic site requirement",
        flow_need=need,
        **kwargs,
    )


def reviewed(s, item):
    return replace(
        item,
        findings=replace(
            item.findings,
            scope=safeguard_study_scope(
                s, item.safeguard, item.treatment, item.flow_need, item.measure, item.replacement
            ),
        ),
    )


def complete(s):
    return tuple(study(s, safeguard, 180 if safeguard is Safeguard.FISH_PASSAGE else 130) for safeguard in Safeguard)


def test_all_safeguards_supported_totals_are_not_added():
    s = site(q=40)
    result = assess_safeguards((s,), complete(s))
    assert result.sites[0].minimum.value == Flow(180, "l/s")
    assert result.sites[0].initial_conditions.finding is CheckFinding.FAIL
    assert result.summary.finding is CheckFinding.PASS
    assert result.summary.completeness is Completeness.COMPLETE
    assert s.starting_minimum.value == Flow(130, "l/s")
    assert all(
        item.findings.official_admissibility is OfficialAdmissibility.PENDING for item in result.sites[0].studies
    )


@pytest.mark.parametrize(
    "q,elevation,fish,expected",
    [
        (40, 799, FishFunction.SPAWNING_OR_REARING, CheckFinding.UNKNOWN),
        ("40.001", 799, FishFunction.SPAWNING_OR_REARING, CheckFinding.PASS),
        (40, 800, FishFunction.SPAWNING_OR_REARING, CheckFinding.PASS),
        (40, 799, FishFunction.NEITHER, CheckFinding.PASS),
        (40, 799, FishFunction.UNKNOWN, CheckFinding.UNKNOWN),
    ],
)
def test_spawning_boundaries_at_affected_point(q, elevation, fish, expected):
    s = site(q, elevation, fish)
    studies = tuple(item for item in complete(s) if item.safeguard is not Safeguard.SPAWNING_REARING)
    result = assess_safeguards((s,), studies)
    assert result.summary.finding is expected


def test_high_intake_does_not_exclude_low_downstream_spawning():
    high = site(40, 900, identifier="intake")
    low = site(40, 700, identifier="downstream")
    result = assess_safeguards(
        (high, low),
        complete(high) + tuple(item for item in complete(low) if item.safeguard is not Safeguard.SPAWNING_REARING),
    )
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.sites[0].summary.finding is CheckFinding.PASS
    assert result.sites[1].summary.finding is CheckFinding.UNKNOWN


def test_known_failure_survives_missing_safeguards_and_no_universal_depth():
    s = site()
    failure = study(s, Safeguard.FISH_PASSAGE, treatment=SafeguardTreatment.IMPOSSIBLE)
    result = assess_safeguards((s,), (failure,))
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert result.sites[0].minimum.value == Flow(130, "l/s")


def test_alternative_measure_avoids_uplift_and_qualified_habitat_replacement():
    s = site(40)
    studies = list(complete(s))
    studies[4] = study(
        s,
        Safeguard.FISH_PASSAGE,
        treatment=SafeguardTreatment.ALTERNATIVE,
        measure="constructed passage channel with accepted site depth criterion",
    )
    studies[3] = study(
        s,
        Safeguard.RARE_HABITATS,
        treatment=SafeguardTreatment.REPLACEMENT,
        measure="equivalent rare habitat replacement",
        replacement=HabitatReplacement(
            CheckFinding.PASS, CheckFinding.PASS, CheckFinding.PASS, "specialist qualifications"
        ),
    )
    result = assess_safeguards((s,), tuple(studies))
    assert result.summary.finding is CheckFinding.PASS
    assert result.sites[0].minimum.value == Flow(130, "l/s")
    assert len(result.sites[0].measures) == 2
    bad = replace(studies[3], replacement=replace(studies[3].replacement, overriding_reasons_absent=CheckFinding.FAIL))
    assert assess_safeguards((s,), (reviewed(s, bad),)).summary.finding is CheckFinding.FAIL


def test_unqualified_rare_habitat_alternative_refused():
    s = site()
    with pytest.raises(ValueError, match="qualified"):
        study(s, Safeguard.RARE_HABITATS, treatment=SafeguardTreatment.ALTERNATIVE, measure="replacement")


def test_combined_lower_bound_rechecked_against_all_relationship_domains():
    s = site()
    inputs = list(complete(s))
    inputs[0] = replace(inputs[0], flow_need=replace(inputs[0].flow_need, domain_upper=Flow(150, "l/s")))
    result = assess_safeguards((s,), tuple(reviewed(s, item) for item in inputs))
    assert result.sites[0].minimum.value == Flow(180, "l/s")
    assert result.summary.finding is CheckFinding.FAIL


def test_unaccepted_relation_does_not_invent_uplift_and_fail_survives():
    s = site()
    item = study(s, Safeguard.FISH_PASSAGE, 999)
    item = replace(item, findings=replace(item.findings, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED))
    result = assess_safeguards((s,), (item,))
    assert result.sites[0].minimum.value == Flow(130, "l/s")
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE


def test_wrong_scope_unknown_wrong_scenario_refused():
    s = site()
    item = study(s, Safeguard.FISH_PASSAGE, 180)
    wrong = replace(
        item, findings=replace(item.findings, scope=replace(item.findings.scope, intended_use="another use"))
    )
    assert assess_safeguards((s,), (wrong,)).sites[0].minimum.value == Flow(130, "l/s")
    wrong = replace(
        item, findings=replace(item.findings, provenance=replace(item.findings.provenance, scenario="other"))
    )
    with pytest.raises(ValueError, match="scenario"):
        assess_safeguards((s,), (wrong,))


def test_seasonal_and_event_needs_stay_at_each_interval_and_point():
    winter = site(identifier="winter")
    event = site(identifier="event")
    event = replace(
        event,
        starting_minimum=replace(
            event.starting_minimum,
            interval=Interval(datetime(2025, 7, 1, tzinfo=UTC), datetime(2025, 7, 1, 1, tzinfo=UTC)),
        ),
    )
    event_studies = tuple(study(event, safeguard, 500) for safeguard in Safeguard)
    result = assess_safeguards((winter, event), complete(winter) + event_studies)
    assert [row.minimum.value for row in result.sites] == [Flow(180, "l/s"), Flow(500, "l/s")]
    assert result.sites[1].minimum.interval.seconds == 3600
    assert winter.starting_minimum.value == Flow(130, "l/s")


def test_absent_and_empty_inventory_cannot_pass():
    assert assess_safeguards((), ()).summary.finding is CheckFinding.UNKNOWN
    s = site()
    missing = replace(
        s,
        starting_minimum=replace(
            s.starting_minimum, value=None, presence=Presence.MISSING, reasons=("missing starting minimum",)
        ),
    )
    result = assess_safeguards((missing,), complete(missing))
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.sites[0].minimum.presence is Presence.UNSUPPORTED


def test_duplicate_and_undeclared_studies_refused():
    s = site()
    item = study(s, Safeguard.FISH_PASSAGE)
    with pytest.raises(ValueError, match="duplicate"):
        assess_safeguards((s,), (item, item))
    with pytest.raises(ValueError, match="undeclared"):
        assess_safeguards((s,), (replace(item, site_identifier="elsewhere"),))


def test_habitat_preservation_measure_is_not_an_unqualified_replacement():
    s = site()
    item = study(
        s,
        Safeguard.RARE_HABITATS,
        treatment=SafeguardTreatment.PRESERVATION,
        measure="supported habitat-preserving channel work",
    )
    result = assess_safeguards((s,), (item,))
    assert result.sites[0].measures == ("supported habitat-preserving channel work",)
    assert not any(check.finding is CheckFinding.FAIL for check in result.summary.checks)


def test_study_cannot_transfer_to_new_data_or_configuration_version():
    s = site()
    item = study(s, Safeguard.FISH_PASSAGE, 180)
    for field in ("data_version", "configuration_version"):
        altered = replace(
            s,
            starting_minimum=replace(
                s.starting_minimum, provenance=replace(s.starting_minimum.provenance, **{field: "changed"})
            ),
        )
        with pytest.raises(ValueError, match="identity"):
            assess_safeguards((altered,), (item,))


def test_findings_cannot_be_rebound_to_another_section_or_reach_revision():
    s = site()
    item = study(s, Safeguard.FISH_PASSAGE, 180)
    original = s.starting_minimum.location
    for location in (
        replace(original, section=CalculationSection("other", "v1")),
        replace(original, reach=replace(original.reach, version="v2")),
    ):
        altered = replace(s, starting_minimum=replace(s.starting_minimum, location=location))
        rebound = replace(item, location=location)
        result = assess_safeguards((altered,), (rebound,))
        assert result.sites[0].minimum.value == Flow(130, "l/s")
        assert result.summary.finding is CheckFinding.UNKNOWN


def test_calculated_minimum_is_not_labelled_an_observation():
    s = site()
    s = replace(
        s,
        starting_minimum=replace(
            s.starting_minimum,
            provenance=replace(s.starting_minimum.provenance, production_method=ProductionMethod.OBSERVED),
        ),
    )
    result = assess_safeguards((s,), complete(s))
    assert result.sites[0].minimum.provenance.production_method is not ProductionMethod.OBSERVED


def test_excluded_study_period_cannot_support_an_increase():
    s = site()
    item = study(s, Safeguard.FISH_PASSAGE, 180)
    item = replace(
        item,
        findings=replace(
            item.findings, provenance=replace(item.findings.provenance, excluded_warmup=(s.starting_minimum.interval,))
        ),
    )
    assert assess_safeguards((s,), (item,)).sites[0].minimum.value == Flow(130, "l/s")


def test_unknown_spawning_function_cannot_invent_a_known_failure():
    s = site(40, 700, FishFunction.UNKNOWN)
    item = study(s, Safeguard.SPAWNING_REARING, treatment=SafeguardTreatment.NOT_APPLICABLE)
    assert assess_safeguards((s,), (item,)).summary.finding is CheckFinding.UNKNOWN


def test_final_candidate_rechecks_actual_safeguard_domains():
    from fishy.swiss_safeguards import assess_safeguard_candidate

    s = site()
    studies = tuple(
        replace(item, flow_need=replace(item.flow_need, domain_upper=Flow(200, "l/s"))) for item in complete(s)
    )
    supported = assess_safeguards((s,), tuple(reviewed(s, item) for item in studies))
    assert supported.summary.finding is CheckFinding.PASS
    candidate = replace(supported.sites[0].minimum, value=Flow(220, "l/s"))
    assert assess_safeguard_candidate(supported, (candidate,)).finding is CheckFinding.FAIL


def test_indicative_studies_are_labelled_scenarios_not_final_sizing():
    from fishy.swiss_safeguards import SafeguardUse

    s = site()
    inputs = tuple(
        replace(item, findings=replace(item.findings, scientific_adequacy=ScientificAdequacy.ACCEPTED_AS_INDICATIVE))
        for item in complete(s)
    )
    scenario = assess_safeguards((s,), inputs, use=SafeguardUse.SCENARIO)
    assert scenario.summary.finding is CheckFinding.PASS
    assert scenario.use is SafeguardUse.SCENARIO
    final = assess_safeguards((s,), inputs, use=SafeguardUse.FINAL_SIZING)
    assert final.summary.finding is CheckFinding.UNKNOWN
    assert final.sites[0].minimum.value == Flow(130, "l/s")


def test_final_candidate_missing_or_lower_is_not_a_pass():
    from fishy.swiss_safeguards import assess_safeguard_candidate

    s = site()
    supported = assess_safeguards((s,), complete(s))
    assert assess_safeguard_candidate(supported, ()).finding is CheckFinding.UNKNOWN
    assert (
        assess_safeguard_candidate(supported, (replace(supported.sites[0].minimum, value=Flow(150, "l/s")),)).finding
        is CheckFinding.FAIL
    )


def test_accepted_study_cannot_be_rebound_to_an_unreviewed_flow_requirement():
    s = site()
    item = study(s, Safeguard.FISH_PASSAGE, 180)
    altered = replace(item, flow_need=replace(item.flow_need, total=Flow(999, "l/s")))
    result = assess_safeguards((s,), (altered,))
    assert result.sites[0].minimum.value == Flow(130, "l/s")
    assert result.summary.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize("safeguard", tuple(Safeguard))
def test_each_required_safeguard_missing_is_unresolved(safeguard):
    s = site(40)
    inputs = tuple(item for item in complete(s) if item.safeguard is not safeguard)
    assert assess_safeguards((s,), inputs).summary.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize("safeguard", tuple(Safeguard))
def test_each_supported_safeguard_failure_survives_other_missing(safeguard):
    s = site(40)
    impossible = study(s, safeguard, treatment=SafeguardTreatment.IMPOSSIBLE)
    result = assess_safeguards((s,), (impossible,))
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE


def test_final_candidate_recomputes_studies_instead_of_trusting_cached_summary():
    from fishy.swiss_safeguards import assess_safeguard_candidate

    s = site()
    inputs = tuple(
        reviewed(s, replace(item, flow_need=replace(item.flow_need, domain_upper=Flow(200, "l/s"))))
        for item in complete(s)
    )
    assessment = assess_safeguards((s,), inputs)
    forged = replace(assessment, sites=tuple(replace(row, studies=()) for row in assessment.sites))
    assert forged.summary.finding is CheckFinding.PASS
    candidate = replace(assessment.sites[0].minimum, value=Flow(220, "l/s"))
    assert assess_safeguard_candidate(forged, (candidate,)).finding is CheckFinding.UNKNOWN


def test_forged_derived_minimum_is_ignored_in_candidate_recheck():
    from fishy.swiss_safeguards import assess_safeguard_candidate

    s = site()
    assessment = assess_safeguards((s,), complete(s))
    forged = replace(
        assessment,
        sites=tuple(replace(row, minimum=replace(row.minimum, value=Flow(1, "l/s"))) for row in assessment.sites),
    )
    low = replace(assessment.sites[0].minimum, value=Flow(50, "l/s"))
    assert assess_safeguard_candidate(forged, (low,)).finding is CheckFinding.FAIL
