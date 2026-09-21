"""Public potential-route witnesses; synthetic settings never adopt a national rule."""

from dataclasses import replace

import pytest
from test_service_conveyance import request
from test_study_requirements import (
    DEPTH,
    EVIDENCE,
    NATURAL,
    NEED,
    POTENTIAL,
    SCOPE,
    VELOCITY,
    condition,
    criterion,
    relation,
    selection,
)

from fishy.duties import DutyApplicability, SuppliedDuty
from fishy.evidence import CheckFinding, OfficialAdmissibility, ScientificAdequacy
from fishy.potential_requirements import (
    Applicability,
    AuthorityBasis,
    IssuedRequirementVersion,
    PotentialRoute,
    PotentialStudy,
    ReplacementDecision,
    ServiceZeroDetermination,
    ZeroInterpretation,
    retain_requirement_history,
    size_potential_floor,
)
from fishy.quantities import Flow
from fishy.spatial import DesignationState, Eligibility, Track, assessment_track
from fishy.study_requirements import StudyNeed, StudyScope

MISSING = PotentialStudy(Applicability.UNRESOLVED, "survey and objective pending", None, ())
HABITAT = PotentialStudy(Applicability.APPLICABLE, "accepted potential objective", selection(), (relation(),))
HYDRAULICS = PotentialStudy(
    Applicability.APPLICABLE,
    "accepted joint targets",
    selection(criteria=(criterion(DEPTH, 1, 2), criterion(VELOCITY, 0, 1))),
    (relation(DEPTH, (0, 1, 2)), relation(VELOCITY, (0, 1, 2))),
)


def run(habitat=MISSING, hydraulics=MISSING, **kwargs):
    return size_potential_floor(SCOPE, POTENTIAL, habitat, hydraulics, None, NEED, **kwargs)


def zero(interpretation=ZeroInterpretation.SERVICE_DETERMINATION):
    return ServiceZeroDetermination(
        SCOPE,
        interpretation,
        AuthorityBasis.HYPOTHETICAL,
        EVIDENCE,
        "audited no required service during this interval",
        "explicit assumed Committee signoff",
        "independent audit right",
        "reviewable dispute route",
        "supplied no-adverse-service criterion",
        NEED,
        "explicit assumed drying adoption" if interpretation is ZeroInterpretation.DESIGNED_DRY else None,
    )


def test_habitat_first_route_returns_floor_only_not_natural_minimum():
    result = run(HABITAT, HYDRAULICS)
    assert result.floor == Flow(5)
    assert result.selected_route is PotentialRoute.HABITAT
    assert len(result.routes) == 1
    assert result.output_kind == "seasonal_floor_only"
    assert result.requirement_state == "pending_full_requirement"
    assert result.obligation_state == "pending_new_delivery_obligation"


def test_joint_hydraulics_success_keeps_earlier_missing_ecology():
    result = run(hydraulics=HYDRAULICS)
    assert result.floor == Flow(5)
    assert result.selected_route is PotentialRoute.HYDRAULIC
    assert result.routes[0].checks.finding is CheckFinding.UNKNOWN
    assert result.routes[0].next_route is PotentialRoute.HYDRAULIC
    assert tuple(r.value for r in result.routes[1].study.responses) == (
        criterion(DEPTH, 1, 1).acceptable,
        criterion(VELOCITY, 1, 1).acceptable,
    )


def test_conveyance_third_route_success_retains_full_trial_trace():
    req = request()
    scope = StudyScope("candidate", req.location, req.interval, "scenario", "member", "sizing", "summer")
    result = size_potential_floor(scope, POTENTIAL, MISSING, MISSING, req, NEED)
    assert result.selected_route is PotentialRoute.CONVEYANCE
    assert result.floor is not None
    assert float(result.floor.value) == pytest.approx(10, abs=1e-7)
    assert len(result.routes) == 3
    assert result.routes[-1].conveyance is not None
    assert len(result.routes[-1].conveyance.trace) > 2
    assert result.routes[0].checks.finding is CheckFinding.UNKNOWN
    assert "ecological" in result.routes[-1].conveyance.limitations[0]


def test_conveyance_infeasible_is_not_pending_pass_and_wrong_scenario_rejected():
    req = request()
    scope = StudyScope("candidate", req.location, req.interval, "scenario", "member", "sizing", "summer")
    result = size_potential_floor(scope, POTENTIAL, MISSING, MISSING, replace(req, capacity=Flow(1)), NEED)
    assert result.floor is None
    assert result.routes[2].checks.finding is CheckFinding.FAIL
    with pytest.raises(ValueError, match="scenario"):
        size_potential_floor(replace(scope, scenario="other"), POTENTIAL, MISSING, MISSING, req, NEED)


def test_missing_all_routes_winter_suspended_and_no_zero_default():
    result = run()
    assert result.floor is None
    assert result.selected_route is None
    assert result.routes[-1].route is PotentialRoute.WINTER
    assert result.routes[-1].checks.checks[0].reasons == ("suspended; cannot size or rescue a route",)
    assert result.review == NEED
    assert result.uncertainty == "high"
    with pytest.raises(ValueError, match="responsibility"):
        size_potential_floor(SCOPE, POTENTIAL, MISSING, MISSING, None, StudyNeed("review missing", None, None))


@pytest.mark.parametrize("interpretation", list(ZeroInterpretation))
def test_supported_zero_and_designed_dry_are_explicit_hypothetical_determinations(interpretation):
    result = run(zero=zero(interpretation))
    assert result.floor == Flow(0)
    assert result.selected_route is PotentialRoute.ZERO
    assert result.zero_determination.basis is AuthorityBasis.HYPOTHETICAL


@pytest.mark.parametrize(
    "field",
    [
        "determination",
        "committee_signoff",
        "audit_right",
        "dispute_route",
        "service_impact_criterion",
        "drying_adoption",
    ],
)
def test_missing_designed_dry_condition_never_authorizes_zero(field):
    result = run(zero=replace(zero(ZeroInterpretation.DESIGNED_DRY), **{field: None}))
    assert result.floor is None


def test_hydraulic_zero_still_needs_service_determination():
    study = replace(HABITAT, selection=selection(0, criteria=(criterion(low=0),)))
    assert run(habitat=study).floor is None
    assert run(habitat=study, zero=zero()).floor == Flow(0)


def test_pending_thermal_groundwater_and_active_quality_survive_success():
    thermal = condition("unsized reservoir thermal-state selective-withdrawal required", CheckFinding.UNKNOWN)
    groundwater = condition(
        "groundwater coupled-model milestone; no natural conservative interim", CheckFinding.UNKNOWN
    )
    quality = condition("supported active same-section quality contribution")
    result = run(HABITAT, additional_conditions=(thermal, groundwater), active_quality=(quality,))
    assert result.floor == Flow(5)
    assert result.additional_conditions == (thermal, groundwater)
    assert result.active_quality == (quality,)


def test_designation_preserves_issued_natural_version_until_supported_revision():
    duty = SuppliedDuty("existing", "v1", "existing permit", DutyApplicability.APPLICABLE, (), "held existing act")
    designated = replace(NATURAL, designation=DesignationState.DESIGNATED, designation_eligibility=Eligibility.ACCEPTED)
    proposal = size_potential_floor(SCOPE, designated, HABITAT, MISSING, None, NEED, existing_duties=(duty,))
    old = IssuedRequirementVersion("natural-v1", Track.NATURAL, (duty,), "prior authority")
    assert retain_requirement_history(proposal, (old,)).in_force == old
    assert retain_requirement_history(proposal, ()).in_force is None
    assert proposal.existing_duties == (duty,)
    new = IssuedRequirementVersion("potential-v2", Track.POTENTIAL, (duty,), "competent replacement act")
    decision = ReplacementDecision(
        "natural-v1",
        new,
        "supported revision procedure completed",
        replace(EVIDENCE, official_admissibility=OfficialAdmissibility.ADMISSIBLE),
    )
    history = retain_requirement_history(proposal, (old,), decision)
    assert history.in_force == new
    assert history.issued == (old, new)
    unsupported = replace(decision, evidence=replace(EVIDENCE, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED))
    assert retain_requirement_history(proposal, (old,), unsupported).in_force == old
    pending = replace(proposal, floor=None)
    assert retain_requirement_history(pending, (old,), decision).in_force == old


@pytest.mark.parametrize(
    "state, expected",
    [
        (DesignationState.PENDING, Track.UNDETERMINED),
        (DesignationState.EXPIRED, Track.NATURAL),
        (DesignationState.REJECTED, Track.NATURAL),
    ],
)
def test_distinct_designation_states_and_irrigation_origin_preserved(state, expected):
    classification = replace(NATURAL, designation=state)
    assert assessment_track(classification).track is expected
    assert assessment_track(classification).classification.designation is state


def test_pending_official_replacement_cannot_displace_issued_requirement():
    proposal = run(HABITAT)
    old = IssuedRequirementVersion("natural-v1", Track.NATURAL, (), "existing act")
    new = IssuedRequirementVersion("potential-v2", Track.POTENTIAL, (), "proposed act")
    decision = ReplacementDecision("natural-v1", new, "revision file", EVIDENCE)
    assert retain_requirement_history(proposal, (old,), decision).in_force == old


def test_zero_cannot_replace_infeasible_positive_service_duties():
    req = request()
    scope = StudyScope("candidate", req.location, req.interval, "scenario", "member", "sizing", "summer")
    evidence = replace(
        EVIDENCE,
        scope=replace(EVIDENCE.scope, product=scope.candidate, period=scope.period, member="member"),
        provenance=replace(
            EVIDENCE.provenance, scenario="scenario", reference_member="member", configuration_version="v1"
        ),
    )
    determination = replace(zero(), scope=scope, evidence=evidence)
    result = size_potential_floor(
        scope, POTENTIAL, MISSING, MISSING, replace(req, capacity=Flow(1)), NEED, zero=determination
    )
    assert result.floor is None
    assert result.routes[2].checks.finding is CheckFinding.FAIL
    assert result.routes[-1].checks.finding is not CheckFinding.PASS


def test_adopted_zero_candidate_retains_separate_official_admissibility():
    result = run(zero=replace(zero(ZeroInterpretation.DESIGNED_DRY), basis=AuthorityBasis.ADOPTED))
    assert result.floor == Flow(0)
    assert result.zero_determination.evidence.official_admissibility is OfficialAdmissibility.PENDING
    assert result.obligation_state == "pending_new_delivery_obligation"
    adopted = replace(
        zero(ZeroInterpretation.DESIGNED_DRY),
        basis=AuthorityBasis.ADOPTED,
        evidence=replace(EVIDENCE, official_admissibility=OfficialAdmissibility.ADMISSIBLE),
    )
    assert run(zero=adopted).floor == Flow(0)


def test_supported_service_zero_balance_requires_and_accepts_determination():
    from fishy.quantities import Volume

    req = request()
    assert req.ramp is not None
    req = replace(
        req,
        duties=(replace(req.duties[0], volume=Volume(0)),),
        initial_flow=Flow(0),
        ramp=replace(req.ramp, previous_flow=Flow(0)),
    )
    scope = StudyScope("candidate", req.location, req.interval, "scenario", "member", "sizing", "summer")
    evidence = replace(
        EVIDENCE,
        scope=replace(EVIDENCE.scope, product=scope.candidate, period=scope.period, member="member"),
        provenance=replace(
            EVIDENCE.provenance, scenario="scenario", reference_member="member", configuration_version="v1"
        ),
    )
    determination = replace(zero(), scope=scope, evidence=evidence)
    result = size_potential_floor(scope, POTENTIAL, MISSING, MISSING, req, NEED, zero=determination)
    assert result.floor == Flow(0)
    assert result.routes[2].conveyance is not None
    assert result.routes[2].conveyance.zero_candidate == Flow(0)
    assert result.routes[2].conveyance.flow is None


@pytest.mark.parametrize("target", ["zero", "additional", "active_quality"])
def test_potential_handoff_rejects_mixed_configuration(target):
    changed = replace(EVIDENCE, provenance=replace(EVIDENCE.provenance, configuration_version="other-policy"))
    kwargs = {}
    if target == "zero":
        kwargs["zero"] = replace(zero(), evidence=changed)
    elif target == "additional":
        kwargs["additional_conditions"] = (replace(condition("thermal"), evidence=changed),)
    else:
        kwargs["active_quality"] = (replace(condition("quality"), evidence=changed),)
    with pytest.raises(ValueError, match="configuration"):
        run(HABITAT, **kwargs)


@pytest.mark.parametrize("route", ["habitat", "hydraulics"])
def test_earlier_supported_zero_reconciles_supplied_service_account(route):
    from fishy.quantities import Volume

    req = request()
    assert req.ramp is not None and req.relation is not None

    def evidence_at(evidence, product, period):
        return replace(
            evidence,
            scope=replace(evidence.scope, product=product, period=period, member=SCOPE.reference_member),
            provenance=replace(
                evidence.provenance,
                scenario=SCOPE.scenario,
                reference_member=SCOPE.reference_member,
                configuration_version=EVIDENCE.provenance.configuration_version,
            ),
        )

    transition = replace(
        req.ramp.transition,
        start=SCOPE.period.start - (req.ramp.transition.end - req.ramp.transition.start),
        end=SCOPE.period.start,
    )
    duty = replace(
        req.duties[0],
        interval=SCOPE.period,
        volume=Volume(0),
        evidence=evidence_at(req.duties[0].evidence, "rule", SCOPE.period),
    )
    relation_input = replace(
        req.relation,
        location=SCOPE.location,
        interval=SCOPE.period,
        evidence=evidence_at(req.relation.evidence, "relation", SCOPE.period),
    )
    ramp = replace(
        req.ramp,
        previous_flow=Flow(0),
        transition=transition,
        evidence=evidence_at(req.ramp.evidence, "conveyance_ramp", transition),
    )
    req = replace(
        req,
        location=SCOPE.location,
        interval=SCOPE.period,
        duties=(duty,),
        relation=relation_input,
        initial_flow=Flow(0),
        ramp=ramp,
    )
    habitat = replace(HABITAT, selection=selection(0, criteria=(criterion(low=0),))) if route == "habitat" else MISSING
    hydraulics = (
        replace(HYDRAULICS, selection=selection(0, criteria=(criterion(DEPTH, 0, 2), criterion(VELOCITY, 0, 1))))
        if route == "hydraulics"
        else MISSING
    )
    result = size_potential_floor(SCOPE, POTENTIAL, habitat, hydraulics, req, NEED, zero=zero())
    assert result.floor == Flow(0)
    assert result.selected_route is PotentialRoute.ZERO
    first_success = next(r for r in result.routes if r.flow is not None)
    assert first_success.route is (PotentialRoute.HABITAT if route == "habitat" else PotentialRoute.HYDRAULIC)
    assert result.routes[-1].conveyance is not None
    assert result.routes[-1].conveyance.zero_candidate == Flow(0)
    assert result.routes[-1].conveyance.trace[0].flow == Flow(0)
    assert result.routes[-1].conveyance.trace[0].residual_m3 == 0
