"""Appendix A ordered route choices retain independent evidence and failures."""

from dataclasses import replace

import pytest
from test_graduated_entry import statistic
from test_spatial import classification
from test_study_requirements import NEED, relation, selection

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
    reconstruction_disclosure_scope,
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
    scope = reconstruction_disclosure_scope(first.magnitude.reference)
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


def study_component(b, *, flow=5, required=("ramping",), name="habitat", kind="seasonal"):
    """Explicit supported synthetic study on this complete natural reference family."""
    original = selection(flow, required=required)
    scope = replace(
        original.scope,
        location=b.location,
        period=b.natural_patterns[0].samples[0].interval,
        scenario=b.natural_patterns[0].magnitude.provenance.scenario,
        reference_member=b.natural_patterns[0].magnitude.provenance.reference_member,
    )
    evidence = replace(
        original.evidence,
        scope=replace(
            original.evidence.scope,
            reach=b.location.reach.identifier,
            member=scope.reference_member,
            period=scope.period,
        ),
        provenance=b.natural_patterns[0].magnitude.provenance,
    )
    chosen = replace(
        original,
        scope=scope,
        evidence=evidence,
        conditions=tuple(replace(c, scope=scope, evidence=evidence) for c in original.conditions),
    )
    supported_relation = replace(relation(), scope=scope, evidence=evidence)
    return NaturalStudyComponent(name, chosen, (supported_relation,), kind)


def top():
    b = tier()
    return replace(
        b,
        route=NaturalRoute.TOP,
        studies=(study_component(b),),
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
    bad = study_component(t, flow=10)
    result = select_natural_route(natural(), (replace(t, studies=(bad,)),))
    assert result.selected is NaturalRoute.PENDING
    pulse = study_component(
        t, flow=8, required=("sediment", "hydraulic", "flood_safety", "ramping"), name="pulse", kind="pulse"
    )
    full = replace(
        t, studies=(pulse,), required_study_components=("pulse",), study_trigger=HighFlowTrigger.SEDIMENT_TRAPPING
    )
    assert select_natural_route(natural(), (full,)).selected is NaturalRoute.TOP
    missing = replace(full, studies=(study_component(t, flow=8, name="pulse", kind="pulse"),))
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


def test_screening_only_daily_statistic_cannot_select_entry():
    from test_scientific_acceptance import supplied

    from fishy.scientific_acceptance import UsePurpose

    b = tier()
    s = b.statistics[0]
    subject = replace(
        s.product, purpose=UsePurpose.SCREENING, scope=replace(s.product.scope, intended_use=UsePurpose.SCREENING.value)
    )
    record, evidence = supplied(subject)
    screened = ScientificRequirement("low_flow", subject, assess_scientific_use(record, evidence))
    entry = replace(
        b,
        route=NaturalRoute.ENTRY,
        required_ids=("low_flow",),
        statistics=(screened,),
        prerequisites=(),
        natural_patterns=(),
        recorded_minimum=None,
    )
    result = select_natural_route(natural(), (entry,))
    assert result.selected is NaturalRoute.PENDING
    assert result.highest_data_supported is None


def test_top_cannot_omit_baseline_hydrological_prerequisites():
    t = top()
    t = replace(t, natural_patterns=(), recorded_minimum=None)
    result = select_natural_route(natural(), (t,))
    assert result.selected is NaturalRoute.PENDING
    assert result.highest_data_supported is None


@pytest.mark.parametrize(
    "field,value",
    [("member", "other-member"), ("intended_use", "screen only"), ("product", "unrelated reference contract")],
)
def test_reconstruction_disclosure_cannot_rebind_its_own_scope(field, value):
    b = tier()
    d = b.prerequisites[0]
    changed_scope = replace(d.scope, **{field: value})
    changed = replace(d, scope=changed_scope, findings=replace(d.findings, scope=changed_scope))
    result = select_natural_route(natural(), (replace(b, prerequisites=(changed,)),))
    assert result.selected is NaturalRoute.PENDING
    assert result.highest_data_supported is None


def test_reconstruction_disclosure_other_scenario_is_not_this_reference():
    b = tier()
    d = b.prerequisites[0]
    changed = replace(d, findings=replace(d.findings, provenance=replace(d.findings.provenance, scenario="other")))
    assert select_natural_route(natural(), (replace(b, prerequisites=(changed,)),)).selected is NaturalRoute.PENDING


def test_recorded_minimum_permission_must_match_family_requested_use():
    from examples.natural_baseline import synthetic_acceptance
    from fishy.natural_baseline import recorded_minimum_product
    from fishy.scientific_acceptance import UsePurpose

    b = tier()
    minimum = b.recorded_minimum
    subject = recorded_minimum_product(minimum, intended_use="screening", purpose=UsePurpose.SIZING)
    changed = replace(minimum, assessment=synthetic_acceptance(subject))
    assert select_natural_route(natural(), (replace(b, recorded_minimum=changed),)).selected is NaturalRoute.PENDING


def test_reconstruction_contract_requires_complete_disclosure():
    from fishy.evidence import Disclosure

    b = tier()
    d = b.prerequisites[0]
    incomplete = replace(d, findings=replace(d.findings, disclosure=Disclosure.INCOMPLETE))
    assert select_natural_route(natural(), (replace(b, prerequisites=(incomplete,)),)).selected is NaturalRoute.PENDING


@pytest.mark.parametrize("missing", [0, 1, 2, 3, 4])
def test_top_requires_every_natural_probability_product(missing):
    t = top()
    incomplete = replace(t, natural_patterns=t.natural_patterns[:missing] + t.natural_patterns[missing + 1 :])
    assert select_natural_route(natural(), (incomplete,)).selected is NaturalRoute.PENDING


def test_top_study_screening_permission_is_not_sizing_permission():
    t = top()
    c = t.studies[0]
    scope = replace(c.study.scope, purpose="screening")
    evidence = replace(c.study.evidence, scope=replace(c.study.evidence.scope, intended_use="screening"))
    study = replace(
        c.study,
        scope=scope,
        evidence=evidence,
        conditions=tuple(replace(v, scope=scope, evidence=evidence) for v in c.study.conditions),
    )
    relations = tuple(replace(v, scope=scope, evidence=evidence) for v in c.relations)
    changed = replace(c, study=study, relations=relations)
    assert select_natural_route(natural(), (replace(t, studies=(changed,)),)).selected is NaturalRoute.PENDING


@pytest.mark.parametrize("route", [NaturalRoute.BASELINE, NaturalRoute.TOP])
def test_natural_family_cannot_mix_individually_accepted_intended_uses(route):
    from examples.natural_baseline import synthetic_acceptance
    from fishy.daily_patterns import annual_magnitude_product, pattern_product

    b = tier() if route is NaturalRoute.BASELINE else top()
    pattern = b.natural_patterns[1]
    use = "separate use only"
    magnitude = synthetic_acceptance(
        annual_magnitude_product(pattern.magnitude, intended_use=use, purpose=pattern.purpose)
    )
    changed = replace(
        pattern,
        requested_use=use,
        magnitude_assessment=magnitude,
        magnitude_evidence=magnitude.findings,
        shape_assessment=None,
        shape_evidence=None,
    )
    shape = synthetic_acceptance(pattern_product(changed, intended_use=use, purpose=changed.purpose))
    changed = replace(changed, shape_assessment=shape, shape_evidence=shape.findings)
    assert changed.use_checks.finding is CheckFinding.PASS
    patterns = (b.natural_patterns[0], changed, *b.natural_patterns[2:])
    result = select_natural_route(natural(), (replace(b, natural_patterns=patterns),))
    assert result.selected is NaturalRoute.PENDING
    assert result.highest_data_supported is None
