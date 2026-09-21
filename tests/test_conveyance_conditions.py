"""conveyance_witnesses : ServiceConveyanceRequest × FlowSample → CheckSummary.

Synthetic service5 plus quality10 exercises original-domain final rechecks.
"""

from dataclasses import replace
from datetime import timedelta
from fractions import Fraction

import pytest

from examples.requirement_chain import TARGET, accepted_evidence, samples
from fishy.conveyance_conditions import assess_conveyance_conditions
from fishy.evidence import CheckFinding, Completeness, EvidenceScope, ReferenceKind, ScientificAdequacy
from fishy.flows import Coverage
from fishy.quantities import Flow, Volume
from fishy.receptor_delivery import (
    ControlMapping,
    DeliveryContext,
    WaterRelationship,
    control_equivalent,
    delivery_scope,
)
from fishy.requirement_checks import sample_subject
from fishy.service_conveyance import (
    Authentication,
    ConvergenceRule,
    ConveyanceRamp,
    ConveyanceRelation,
    ConveyanceState,
    ConveyanceStatus,
    DutySource,
    ServiceConveyanceRequest,
    ServiceDuty,
    solve_service_conveyance,
)
from fishy.time import Interval


def service_request(base=None, *, upper=8, capacity=20, rise=20, fall=20):
    """Explicit complete daily service request, unchanged by later quality water."""
    if base is None:
        original = samples(TARGET, 5, "service", "R")[0]
        base = replace(original, provenance=replace(original.provenance, reference_kind=ReferenceKind.MANAGED))
    p = base.provenance

    def support(name, period):
        return accepted_evidence(
            EvidenceScope(name, base.location.reach.identifier, p.reference_member, period, "service_conveyance"), p
        )

    duty = ServiceDuty(
        "service",
        base.location,
        base.interval,
        Volume(5 * base.interval.seconds),
        DutySource.OPERATING_RULE,
        Authentication.AUTHENTICATED,
        support("service", base.interval),
        Flow(20),
    )
    relation = ConveyanceRelation(
        "relation",
        base.location,
        base.interval,
        Volume(0),
        base.location,
        (ConveyanceState(Flow(0), Volume(0), ()), ConveyanceState(Flow(upper), Volume(0), ())),
        "original-geometry-v1",
        "constant daily service; zero storage and losses",
        "explicit exact synthetic support",
        support("relation", base.interval),
    )
    transition = Interval(base.interval.start - timedelta(days=1), base.interval.start)
    ramp = ConveyanceRamp(Flow(5), transition, Flow(rise), Flow(fall), support("conveyance_ramp", transition))
    request = ServiceConveyanceRequest(
        base.location,
        base.interval,
        (duty,),
        relation,
        (),
        Flow(5),
        ConvergenceRule(Volume(0), 3, "exact fixed service balance"),
        Flow(capacity),
        ramp,
    )
    return base, request


def test_final_quality_flow_outside_original_domain_is_unsupported_not_issued_service():
    base, request = service_request()
    assert solve_service_conveyance(request).flow == Flow(5)
    final = replace(base, value=Flow(10))
    result = assess_conveyance_conditions(request, final)
    assert result.source.status is ConveyanceStatus.SUPPORTED
    assert result.source.flow == Flow(5)
    assert result.local_flow == Flow(10) and result.state is None
    assert result.checks.finding is CheckFinding.UNKNOWN
    checks = {c.check_id: c.finding for c in result.checks.checks}
    assert checks["final_capacity"] is checks["final_ramp"] is CheckFinding.PASS
    assert checks["final_relation_domain"] is CheckFinding.UNKNOWN
    assert request.initial_flow == Flow(5)


def test_supported_excess_is_not_resized_back_to_original_fixedpoint(monkeypatch):
    import fishy.conveyance_conditions as module

    base, request = service_request(upper=12)
    calls = []
    native = module.solve_service_conveyance

    def original_only(actual):
        calls.append(actual)
        return native(actual)

    monkeypatch.setattr(module, "solve_service_conveyance", original_only)
    result = assess_conveyance_conditions(request, replace(base, value=Flow(10)))
    assert calls == [request]
    assert result.source.flow == Flow(5)
    assert result.state is not None and result.state.flow == Flow(10)
    assert result.balance_margin_m3 == 5 * 86400
    assert result.unassigned_excess == Volume(5 * 86400)
    assert result.raw_shortfall == Volume(0)
    assert result.ramp_increment_m3_s == 5
    assert result.ramp_rate_m3_s2 == Fraction(5, 86400)
    assert result.checks.finding is CheckFinding.PASS


@pytest.mark.parametrize("kind", ("capacity", "rise", "fall"))
def test_known_original_capacity_and_directional_ramp_limits_apply_to_final_flow(kind):
    base, request = service_request(
        upper=12,
        capacity=8 if kind == "capacity" else 20,
        rise=1 if kind == "rise" else 20,
        fall=1 if kind == "fall" else 20,
    )
    final = replace(base, value=Flow(3 if kind == "fall" else 10))
    result = assess_conveyance_conditions(request, final)
    assert result.source.status is ConveyanceStatus.SUPPORTED
    assert result.checks.finding is CheckFinding.FAIL
    assert (
        next(
            c for c in result.checks.checks if c.check_id == ("final_capacity" if kind == "capacity" else "final_ramp")
        ).finding
        is CheckFinding.FAIL
    )


def test_supported_final_service_deficit_is_not_hidden_by_domain_capacity_pass():
    base, request = service_request(upper=12)
    result = assess_conveyance_conditions(request, replace(base, value=Flow(4)))
    assert result.raw_shortfall == Volume(86400)
    assert result.unassigned_excess == Volume(0)
    assert result.balance_margin_m3 == -86400
    assert result.checks.finding is CheckFinding.FAIL


@pytest.mark.parametrize("missing", ("relation", "ramp"))
def test_known_capacity_failure_survives_missing_domain_or_predecessor(missing):
    base, request = service_request(capacity=8)
    request = replace(request, **{missing: None})
    result = assess_conveyance_conditions(request, replace(base, value=Flow(10)))
    assert result.checks.finding is CheckFinding.FAIL
    assert result.checks.completeness is Completeness.INCOMPLETE
    assert next(c for c in result.checks.checks if c.check_id == "final_capacity").finding is CheckFinding.FAIL


def test_unsupported_ramp_evidence_never_becomes_supported_failure():
    base, request = service_request(upper=12, rise=1)
    assert request.ramp is not None
    request = replace(
        request,
        ramp=replace(
            request.ramp, evidence=replace(request.ramp.evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
        ),
    )
    result = assess_conveyance_conditions(request, replace(base, value=Flow(10)))
    assert result.ramp_increment_m3_s == 5
    assert result.checks.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize("wrong", ("period", "scenario", "configuration", "partial"))
def test_original_carrier_domain_and_evidence_cannot_be_relabelled(wrong):
    base, request = service_request(upper=12)
    final = replace(base, value=Flow(10))
    if wrong == "period":
        final = replace(final, interval=Interval(final.interval.start, final.interval.start + timedelta(hours=12)))
    elif wrong == "partial":
        final = replace(final, coverage=Coverage.PARTIAL, reasons=("partial unsupported interval",))
    else:
        field = "configuration_version" if wrong == "configuration" else "scenario"
        final = replace(final, provenance=replace(final.provenance, **{field: "other"}))
    result = assess_conveyance_conditions(request, final)
    assert result.local_flow is None
    assert result.checks.finding is (
        CheckFinding.FAIL if wrong in ("scenario", "configuration") else CheckFinding.UNKNOWN
    )


@pytest.mark.parametrize(
    "relationship,final_value,expected_local,expected",
    (
        (WaterRelationship.SAME_WATER, 10, 10, CheckFinding.UNKNOWN),
        (WaterRelationship.LATERAL, 8, 5, CheckFinding.PASS),
    ),
)
def test_mapped_source_section_uses_actual_shared_or_continuing_water(
    relationship, final_value, expected_local, expected
):
    base, request = service_request()
    upstream = replace(base.location, section=replace(base.location.section, identifier="U"))
    final = replace(base, location=upstream, value=Flow(final_value))
    ctx = DeliveryContext(
        base.location, base.interval, sample_subject(final), "explicit carrier mapping", base.provenance
    )
    mapping = ControlMapping(
        ctx,
        upstream,
        base.location,
        Flow(5),
        Flow(10 if relationship is WaterRelationship.SAME_WATER else 3),
        relationship,
        "supported zero-loss no-delay mapping",
    )
    equivalence = control_equivalent(mapping, accepted_evidence(delivery_scope(ctx, mapping), base.provenance))
    result = assess_conveyance_conditions(request, final, mapping=equivalence)
    assert result.local_flow == Flow(expected_local)
    assert result.checks.finding is expected
    assert assess_conveyance_conditions(request, final).checks.finding is CheckFinding.UNKNOWN
    changed = replace(final, value=Flow(final_value + 1))
    assert assess_conveyance_conditions(request, changed, mapping=equivalence).checks.finding is CheckFinding.FAIL


def test_known_service_volume_deficit_survives_missing_ramp_context():
    base, request = service_request(upper=12)
    result = assess_conveyance_conditions(replace(request, ramp=None), replace(base, value=Flow(4)))
    assert result.checks.finding is CheckFinding.FAIL
    assert result.checks.completeness is Completeness.INCOMPLETE
    assert result.raw_shortfall == Volume(86400)


def test_actual_storage_and_named_losses_are_recomputed_at_final_flow():
    from fishy.service_conveyance import ConveyanceLoss

    base, request = service_request(upper=12)
    assert request.relation is not None
    destination = replace(base.location, section=replace(base.location.section, identifier="aquifer"))
    relation = replace(
        request.relation,
        states=(
            ConveyanceState(Flow(0), Volume(0), (ConveyanceLoss("seepage", destination, Volume(0)),)),
            ConveyanceState(Flow(12), Volume(2 * 86400), (ConveyanceLoss("seepage", destination, Volume(86400)),)),
        ),
    )
    request = replace(
        request,
        relation=relation,
        stopping=ConvergenceRule(Volume("0.000001"), 30, "declared numerical convergence bound"),
    )
    result = assess_conveyance_conditions(request, replace(base, value=Flow(10)))
    assert result.source.status is ConveyanceStatus.SUPPORTED
    assert result.source.flow is not None and result.source.flow.value < 10
    assert result.state is not None
    assert result.state.final_storage == Volume(144000)
    assert result.state.losses[0].volume == Volume(72000)
    assert result.state.losses[0].destination == destination
    assert result.balance_margin_m3 == 216000
    assert result.checks.finding is CheckFinding.PASS


def test_only_original_numeric_balance_tolerance_preserves_native_accepted_approximation():
    base, request = service_request(upper=12)
    assert request.relation is not None
    request = replace(
        request,
        relation=replace(
            request.relation,
            states=(ConveyanceState(Flow(0), Volume(0), ()), ConveyanceState(Flow(12), Volume(3 * 86400), ())),
        ),
        stopping=ConvergenceRule(Volume("0.000001"), 30, "original fixed-point numerical precision"),
    )
    native = solve_service_conveyance(request)
    assert native.status is ConveyanceStatus.SUPPORTED and native.flow is not None
    final = replace(base, value=native.flow)
    result = assess_conveyance_conditions(request, final)
    assert result.raw_shortfall is not None
    assert 0 < result.raw_shortfall.value <= request.stopping.residual_tolerance.value
    assert result.checks.finding is CheckFinding.PASS
    assert result.request.stopping is request.stopping
    # The numerical volume tolerance does not soften the independent strict capacity.
    tighter = replace(request, capacity=Flow(native.flow.value - Fraction(1, 10**12)))
    refused = assess_conveyance_conditions(tighter, final)
    assert next(c for c in refused.checks.checks if c.check_id == "final_capacity").finding is CheckFinding.FAIL
    assert refused.checks.finding is CheckFinding.FAIL
