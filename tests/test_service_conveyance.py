"""Synthetic Appendix A step 7 / U8 interval service-balance witnesses."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from fishy.evidence import (
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ScientificAdequacy,
)
from fishy.quantities import Flow, Volume
from fishy.service_conveyance import (
    Authentication,
    ConvergenceRule,
    ConveyanceLoss,
    ConveyanceRamp,
    ConveyanceRelation,
    ConveyanceState,
    ConveyanceStatus,
    DutySource,
    ServiceConveyanceRequest,
    ServiceDuty,
    ServiceInflow,
    solve_service_conveyance,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

START = datetime(2025, 1, 1, tzinfo=UTC)
PERIOD = Interval(START, START + timedelta(seconds=10))
TRANSITION = Interval(START - timedelta(seconds=10), START)
BODY = WaterBody("canal", "v1")
REACH = Reach("reach", "v1", BODY)
CONTROL = Location(REACH, CalculationSection("control", "v1"), "v1")
OFFTAKE = replace(CONTROL, section=CalculationSection("offtake", "v1"))
AQUIFER = replace(CONTROL, section=CalculationSection("aquifer", "v1"))


def evidence(product, location=CONTROL, period=PERIOD):
    return EvidenceFindings(
        EvidenceScope(product, location.reach.identifier, "member", period, "service_conveyance"),
        Provenance(
            "synthetic study",
            "scenario",
            "member",
            "v1",
            "v1",
            "v1",
            ProductionMethod.ILLUSTRATIVE,
            CorrectionState.ORIGINAL,
        ),
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("synthetic engineering test, not policy",),
    )


def request():
    duty = ServiceDuty(
        "rule",
        OFFTAKE,
        PERIOD,
        Volume(80),
        DutySource.OPERATING_RULE,
        Authentication.AUTHENTICATED,
        evidence("rule", OFFTAKE),
        Flow(20),
    )
    relation = ConveyanceRelation(
        "relation",
        CONTROL,
        PERIOD,
        Volume(100),
        CONTROL,
        (
            ConveyanceState(Flow(0), Volume(100), (ConveyanceLoss("seepage", AQUIFER, Volume(0)),)),
            ConveyanceState(Flow(20), Volume(120), (ConveyanceLoss("seepage", AQUIFER, Volume(20)),)),
        ),
        "survey-v1",
        "steady boundary; full interval delivery",
        "synthetic exact coefficients",
        evidence("relation"),
    )
    return ServiceConveyanceRequest(
        CONTROL,
        PERIOD,
        (duty,),
        relation,
        (),
        Flow(8),
        ConvergenceRule(
            Volume("0.000001"),
            30,
            "fixed-point contraction 0.2; 30 steps bound initial 20 m3 residual below 1e-6 m3; arithmetic tolerance only",
        ),
        Flow(20),
        ConveyanceRamp(Flow(8), TRANSITION, Flow(5), Flow(5), evidence("conveyance_ramp", period=TRANSITION)),
    )


def test_iterative_flow_storage_seepage_full_trace():
    result = solve_service_conveyance(request())
    assert result.status is ConveyanceStatus.SUPPORTED
    assert result.flow is not None
    assert float(result.flow.value) == pytest.approx(10, abs=1e-7)
    assert len(result.trace) > 2
    assert result.trace[0].residual_m3 == -16
    assert result.trace[1].flow == Flow("9.6")
    assert result.trace[-1].state.losses[0].destination == AQUIFER
    for trial in result.trace:
        assert trial.residual_m3 == 10 * trial.flow.value - trial.required_volume_m3
        assert trial.required_volume_m3 == 80 + 2 * trial.flow.value
    assert abs(result.trace[-1].residual_m3) <= Fraction(1, 1000000)
    assert result.request.relation == request().relation


def test_operating_rule_precedes_permit_and_observations():
    req = request()
    duty = req.duties[0]
    permit = replace(
        duty, identifier="permit", source=DutySource.PERMIT, volume=Volume(10), evidence=evidence("permit", OFFTAKE)
    )
    observed = replace(duty, identifier="observed", source=DutySource.OBSERVED, volume=Volume(1))
    result = solve_service_conveyance(replace(req, duties=(permit, observed, duty)))
    assert result.selected_duties == (duty,)
    result = solve_service_conveyance(replace(req, duties=(permit, observed)))
    assert result.selected_duties == (permit,)
    assert solve_service_conveyance(replace(req, duties=(observed,))).status is ConveyanceStatus.MISSING


@pytest.mark.parametrize("kind", ["capacity", "ramp", "offtake"])
def test_infeasible_never_accepts_last_iterate(kind):
    req = request()
    if kind == "capacity":
        req = replace(req, capacity=Flow(9))
    elif kind == "ramp":
        req = replace(req, ramp=replace(req.ramp, rise=Flow(1)))
    else:
        req = replace(req, duties=(replace(req.duties[0], capacity=Flow(7)),))
    result = solve_service_conveyance(req)
    assert result.status is ConveyanceStatus.INFEASIBLE
    assert result.flow is None


def test_nonconvergence_full_trace_without_accepted_last_iterate():
    req = request()
    result = solve_service_conveyance(
        replace(req, stopping=ConvergenceRule(Volume(0), 2, "explicit two-step diagnostic budget"))
    )
    assert result.status is ConveyanceStatus.NONCONVERGENT
    assert result.flow is None
    assert len(result.trace) == 2
    assert result.trace[-1].flow == Flow("9.6")


@pytest.mark.parametrize("field", ["relation", "capacity", "ramp"])
def test_missing_input_is_not_zero(field):
    result = solve_service_conveyance(replace(request(), **{field: None}))
    assert result.status is ConveyanceStatus.MISSING
    assert result.flow is None


def test_unsupported_reversal_and_inflow_counted_once():
    req = request()
    inflow = ServiceInflow("tributary", AQUIFER, PERIOD, Volume(200), evidence("tributary", AQUIFER))
    result = solve_service_conveyance(replace(req, other_inflows=(inflow,)))
    assert result.status is ConveyanceStatus.UNSUPPORTED
    assert result.trace[0].required_volume_m3 == -104
    assert result.flow is None
    inflow = replace(inflow, volume=Volume(40))
    result = solve_service_conveyance(replace(req, other_inflows=(inflow,)))
    assert result.flow is not None
    assert float(result.flow.value) == pytest.approx(5, abs=1e-7)
    with pytest.raises(ValueError, match="duplicate"):
        replace(req, other_inflows=(inflow, inflow))


def test_unsupported_relation_and_domain():
    req = request()
    relation = req.relation
    unsupported = replace(
        relation, evidence=replace(relation.evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
    )
    assert solve_service_conveyance(replace(req, relation=unsupported)).status is ConveyanceStatus.UNSUPPORTED
    result = solve_service_conveyance(replace(req, initial_flow=Flow(21)))
    assert result.flow is None
    assert "domain" in result.reasons[0]


def test_mismatched_interval_scenario_and_conflicting_duty_rejected():
    req = request()
    duty = req.duties[0]
    with pytest.raises(ValueError, match="interval"):
        replace(req, duties=(replace(duty, interval=TRANSITION),))
    with pytest.raises(ValueError, match="scenario"):
        replace(
            req,
            duties=(
                replace(
                    duty,
                    evidence=replace(duty.evidence, provenance=replace(duty.evidence.provenance, scenario="other")),
                ),
            ),
        )
    with pytest.raises(ValueError, match="contradictory"):
        solve_service_conveyance(replace(req, duties=(duty, replace(duty, identifier="other"))))


def test_zero_not_approved_by_arithmetic():
    req = request()
    req = replace(
        req,
        duties=(replace(req.duties[0], volume=Volume(0)),),
        initial_flow=Flow(0),
        ramp=replace(req.ramp, previous_flow=Flow(0)),
    )
    assert solve_service_conveyance(req).status is ConveyanceStatus.UNSUPPORTED


def test_oscillating_accepted_relation_does_not_converge():
    req = request()
    relation = replace(
        req.relation,
        initial_storage=Volume(160),
        states=(
            ConveyanceState(Flow(0), Volume(200), ()),
            ConveyanceState(Flow(20), Volume(0), ()),
        ),
    )
    result = solve_service_conveyance(replace(req, relation=relation))
    assert result.status is ConveyanceStatus.NONCONVERGENT
    assert result.flow is None
    assert len(result.trace) == 30
    assert [trial.flow for trial in result.trace[:4]] == [Flow(8), Flow(4), Flow(8), Flow(4)]
    assert [trial.residual_m3 for trial in result.trace[:4]] == [40, -40, 40, -40]


def test_named_downstream_duty_and_explicit_zero_losses():
    req = request()
    downstream = replace(CONTROL, section=CalculationSection("downstream", "v1"))
    duty = replace(
        req.duties[0],
        identifier="downstream",
        location=downstream,
        volume=Volume(20),
        evidence=evidence("downstream", downstream),
    )
    relation = replace(
        req.relation, states=(ConveyanceState(Flow(0), Volume(100), ()), ConveyanceState(Flow(20), Volume(100), ()))
    )
    result = solve_service_conveyance(replace(req, duties=(*req.duties, duty), relation=relation))
    assert result.flow == Flow(10)
    assert result.trace[-1].residual_m3 == 0
    assert result.selected_duties == (*req.duties, duty)


def test_required_evidence_scope_not_silently_relabelled():
    req = request()
    relation = replace(
        req.relation,
        evidence=replace(req.relation.evidence, scope=replace(req.relation.evidence.scope, intended_use="exploration")),
    )
    assert solve_service_conveyance(replace(req, relation=relation)).status is ConveyanceStatus.UNSUPPORTED
    with pytest.raises(TypeError, match="domain types"):
        replace(req, initial_flow=8)


def test_excluded_warmup_invalidates_relation_support():
    req = request()
    relation = replace(
        req.relation,
        evidence=replace(
            req.relation.evidence, provenance=replace(req.relation.evidence.provenance, excluded_warmup=(PERIOD,))
        ),
    )
    result = solve_service_conveyance(replace(req, relation=relation))
    assert result.status is ConveyanceStatus.UNSUPPORTED
    assert result.flow is None
    assert any("warm-up" in reason for reason in result.reasons)
