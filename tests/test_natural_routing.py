"""Appendix A ordered route choices retain independent evidence and failures."""

from dataclasses import replace

import pytest
from test_graduated_entry import statistic
from test_spatial import classification
from test_study_requirements import EVIDENCE, LOCATION, NEED, relation, selection

from fishy.evidence import Check, CheckFinding, Completeness
from fishy.natural_routing import (
    Availability,
    DomesticEntryContracts,
    EntryVariant,
    NaturalRoute,
    RouteFailure,
    ScientificRequirement,
    ScopedRequirement,
    TierEvidence,
    select_entry_variant,
    select_natural_route,
)
from fishy.scientific_acceptance import assess_scientific_use
from fishy.spatial import DesignationState, Eligibility, Origin, UseCategory
from fishy.study_requirements import HighFlowTrigger, NaturalStudyComponent


def finding(name="supplied", state=CheckFinding.PASS):
    return Check(name, state, ("explicit hypothetical evidence",))


def tier(route=NaturalRoute.BASELINE, *, indicative=False):

    from examples.natural_baseline import accepted_family
    from fishy.evidence import (
        Computability,
        Disclosure,
        EvidenceFindings,
        EvidenceScope,
        NumericalValidity,
        OfficialAdmissibility,
        ScientificAdequacy,
    )

    patterns, record = accepted_family()
    first = patterns[0]
    # An independently accepted entry statistic at the same physical location.
    s = statistic(indicative=indicative)
    subject = replace(
        s.product, location=first.location, scope=replace(s.product.scope, reach=first.location.reach.identifier)
    )
    from test_scientific_acceptance import supplied

    rec, evidence = supplied(subject)
    assessment = assess_scientific_use(rec, evidence)
    requirements = (ScientificRequirement("low_flow", subject, assessment),)
    scope = EvidenceScope(
        "reconstruction-disclosure",
        first.location.reach.identifier,
        record.reference.provenance.reference_member,
        record.reference.reference_period,
        "reconstruction contract",
    )
    disclosure = EvidenceFindings(
        scope,
        record.reference.provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("synthetic six-condition disclosure; not scientific accuracy",),
    )
    if indicative:
        converted = []
        for pattern in patterns:
            mag = pattern.magnitude_assessment
            shape = pattern.shape_assessment
            mr = replace(mag.record, indicative_basis="supported short-record sizing")
            sr = replace(shape.record, indicative_basis="supported short-record sizing")
            ma = assess_scientific_use(mr, replace(mag.evidence, frozen_record=mr))
            sa = assess_scientific_use(sr, replace(shape.evidence, frozen_record=sr))
            converted.append(
                replace(
                    pattern,
                    magnitude_assessment=ma,
                    magnitude_evidence=ma.findings,
                    shape_assessment=sa,
                    shape_evidence=sa.findings,
                )
            )
        patterns = tuple(converted)
    return TierEvidence(
        route,
        first.location,
        "requirements-v1",
        Availability.AVAILABLE,
        Availability.AVAILABLE,
        finding("priority"),
        ("low_flow", "reconstruction_disclosure"),
        requirements,
        (ScopedRequirement("reconstruction_disclosure", scope, disclosure),),
        (),
        "explicit study requirement inventory",
        patterns,
        record,
    )


def natural():
    return classification(Origin.NATURAL, UseCategory.AGRICULTURE_IRRIGATION)


def top():
    return TierEvidence(
        NaturalRoute.TOP,
        LOCATION,
        "top-v1",
        Availability.AVAILABLE,
        Availability.AVAILABLE,
        finding("priority"),
        ("reference_contract",),
        (),
        (ScopedRequirement("reference_contract", EVIDENCE.scope, EVIDENCE),),
        (NaturalStudyComponent("habitat", selection(), (relation(),), "seasonal"),),
        "supplied habitat study",
        required_study_components=("habitat",),
        study_need=NEED,
    )


def test_indicative_does_not_force_descent_and_resources_are_not_data_failure():
    baseline = tier(indicative=True)
    entry = replace(baseline, route=NaturalRoute.ENTRY)
    result = select_natural_route(natural(), (baseline, entry))
    assert result.selected is NaturalRoute.BASELINE
    result = select_natural_route(natural(), (replace(baseline, resourced=Availability.UNAVAILABLE), entry))
    assert result.selected is NaturalRoute.ENTRY
    assert result.highest_data_supported is NaturalRoute.BASELINE
    assert any("resources unavailable" in r for r in result.reasons)


def test_top_priority_distinct_from_adequate_study_and_missing_study_descends():
    t = top()
    assert select_natural_route(natural(), (t,)).selected is NaturalRoute.TOP
    result = select_natural_route(natural(), (replace(t, priority=finding("priority", CheckFinding.FAIL)),))
    assert result.selected is NaturalRoute.PENDING and result.highest_data_supported is NaturalRoute.TOP
    assert all(c.check_id != "study:eligibility" for c in result.tiers[0].data.checks)
    assert result.tiers[0].eligibility.finding is CheckFinding.FAIL
    missing = select_natural_route(natural(), (replace(t, studies=()),))
    assert missing.highest_data_supported is None
    assert missing.tiers[0].data.completeness is Completeness.INCOMPLETE


def test_study_recomputed_and_preserves_supported_pulse_above_baseline_cap():
    t = top()
    bad = replace(t.studies[0], study=selection(10))
    result = select_natural_route(natural(), (replace(t, studies=(bad,)),))
    assert result.selected is NaturalRoute.PENDING
    pulse = NaturalStudyComponent(
        "pulse", selection(8, required=("sediment", "hydraulic", "flood_safety", "ramping")), (relation(),), "pulse"
    )
    full = replace(
        t, studies=(pulse,), required_study_components=("pulse",), study_trigger=HighFlowTrigger.SEDIMENT_TRAPPING
    )
    assert select_natural_route(natural(), (full,)).selected is NaturalRoute.TOP
    missing = replace(full, studies=(replace(pulse, study=selection(8)),))
    assert select_natural_route(natural(), (missing,)).selected is NaturalRoute.PENDING


def test_failed_route_not_reselected_and_failure_is_preserved():
    baseline = tier()
    entry = replace(baseline, route=NaturalRoute.ENTRY)
    failures = (RouteFailure(NaturalRoute.BASELINE, CheckFinding.FAIL, ("strict natural bound crossing",)),)
    result = select_natural_route(natural(), (baseline, entry), failures)
    assert result.selected is NaturalRoute.ENTRY and result.failures == failures
    failures += (RouteFailure(NaturalRoute.ENTRY, CheckFinding.UNKNOWN, ("large-river screen missing",)),)
    assert select_natural_route(natural(), (baseline, entry), failures).selected is NaturalRoute.PENDING
    with pytest.raises(TypeError, match="not a pass label"):
        select_natural_route(natural(), (), transfer=finding())


def test_absent_required_statistic_and_changed_product_never_pass():
    b = tier()
    assert select_natural_route(natural(), (replace(b, statistics=()),)).selected is NaturalRoute.PENDING
    changed = replace(b.statistics[0], product=replace(b.statistics[0].product, reference_identity="other"))
    assert select_natural_route(natural(), (replace(b, statistics=(changed,)),)).selected is NaturalRoute.PENDING
    with pytest.raises(ValueError, match="nonempty"):
        replace(b, required_ids=())


def test_potential_and_undetermined_bypass_natural_ladder_and_unknown_category_does_not():
    b = tier()
    for c in (
        replace(natural(), origin=Origin.ARTIFICIAL),
        replace(natural(), designation=DesignationState.DESIGNATED, designation_eligibility=Eligibility.ACCEPTED),
    ):
        assert select_natural_route(c, (b,)).selected is NaturalRoute.POTENTIAL
    assert select_natural_route(replace(natural(), origin=Origin.UNKNOWN), (b,)).selected is NaturalRoute.PENDING
    assert (
        select_natural_route(replace(natural(), category=UseCategory.UNDETERMINED), (b,)).selected
        is NaturalRoute.BASELINE
    )


def contracts():
    return DomesticEntryContracts(
        *(finding(n) for n in ("estimator", "windows", "adequacy", "failure", "selection", "interpretation"))
    )


def test_current_domestic_unavailable_and_ordered_branches_never_shop_on_adequacy_failure():
    decision = select_entry_variant(None, finding(), finding())
    assert decision.variant is EntryVariant.GRADUATED
    assert "unavailable" in decision.checks[0].reasons[0]
    unavailable = replace(contracts(), estimator=finding("estimator", CheckFinding.UNKNOWN))
    assert select_entry_variant(unavailable, finding(), finding()).variant is EntryVariant.GRADUATED
    assert (
        select_entry_variant(contracts(), finding(state=CheckFinding.FAIL), finding()).variant is EntryVariant.GRADUATED
    )
    assert (
        select_entry_variant(contracts(), finding(), finding(state=CheckFinding.FAIL)).variant is EntryVariant.FALLBACK
    )
    assert select_entry_variant(contracts(), finding(), finding()).variant is EntryVariant.DOMESTIC


@pytest.mark.parametrize("missing", [0, 1, 2, 3, 4])
def test_each_missing_natural_pattern_prevents_baseline_selection(missing):
    b = tier()
    incomplete = replace(b, natural_patterns=b.natural_patterns[:missing] + b.natural_patterns[missing + 1 :])
    assert select_natural_route(natural(), (incomplete,)).selected is NaturalRoute.PENDING


def test_recorded_minimum_and_reconstruction_disclosure_are_not_optional():
    b = tier()
    assert select_natural_route(natural(), (replace(b, recorded_minimum=None),)).selected is NaturalRoute.PENDING
    assert select_natural_route(natural(), (replace(b, prerequisites=()),)).selected is NaturalRoute.PENDING
    low_flow_only = replace(b, natural_patterns=(), recorded_minimum=None, required_ids=("low_flow",), prerequisites=())
    assert select_natural_route(natural(), (low_flow_only,)).highest_data_supported is None
