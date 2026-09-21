"""conveyance_conditions : ServiceConveyanceRequest × FlowSample → ConveyanceConditionAssessment.

The original service requirement remains fixed. Evaluate the actual final flow in
its original supported storage/loss domain, capacity and predecessor transition.
"""

from dataclasses import dataclass, replace
from fractions import Fraction

from fishy.evidence import Check, CheckFinding, CheckSummary
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, interval_use
from fishy.potential_requirements import ServiceZeroDetermination, _zero_checks
from fishy.quantities import Flow, Volume
from fishy.receptor_delivery import ControlEquivalent, WaterRelationship, control_equivalent
from fishy.requirement_checks import sample_subject
from fishy.service_conveyance import (
    ConveyanceState,
    ConveyanceStatus,
    ServiceConveyanceRequest,
    ServiceConveyanceResult,
    _state,
    _support_reasons,
    solve_service_conveyance,
)


@dataclass(frozen=True)
class ConveyanceConditionAssessment:
    request: ServiceConveyanceRequest
    final: FlowSample
    mapping: ControlEquivalent | None
    source: ServiceConveyanceResult
    local_flow: Flow | None
    state: ConveyanceState | None
    balance_margin_m3: Fraction | None
    unassigned_excess: Volume | None
    raw_shortfall: Volume | None
    ramp_increment_m3_s: Fraction | None
    ramp_rate_m3_s2: Fraction | None
    checks: CheckSummary
    zero: ServiceZeroDetermination | None = None
    zero_checks: CheckSummary | None = None
    original_source: ServiceConveyanceResult | None = None


def _local_flow(request: ServiceConveyanceRequest, final: FlowSample, mapping: ControlEquivalent | None):
    if request.interval != final.interval:
        return None, Check(
            "source_interval",
            CheckFinding.UNKNOWN,
            ("original service accounting interval must match exactly; no implicit temporal equivalence",),
        )
    if (
        final.presence is not Presence.PRESENT
        or final.coverage is not Coverage.COMPLETE
        or final.value is None
        or interval_use(final) is not IntervalUse.ELIGIBLE
    ):
        return None, Check("final_flow", CheckFinding.UNKNOWN, ("complete supported final flow required",))
    evidence = tuple(d.evidence for d in request.duties) + tuple(i.evidence for i in request.other_inflows)
    if request.relation is not None:
        evidence += (request.relation.evidence,)
    if request.ramp is not None:
        evidence += (request.ramp.evidence,)
    if any(
        e.provenance.scenario != final.provenance.scenario
        or e.provenance.configuration_version != final.provenance.configuration_version
        for e in evidence
    ):
        return None, Check(
            "source_identity",
            CheckFinding.FAIL,
            ("original service evidence belongs to another final scenario/configuration",),
        )
    if request.location == final.location:
        return final.value, Check("source_section", CheckFinding.PASS)
    if mapping is None:
        return None, Check(
            "source_mapping", CheckFinding.UNKNOWN, ("supported mapping to original service section missing",)
        )
    m = mapping.mapping
    if (m.control, m.continuing_location, m.context.period, m.context.candidate) != (
        final.location,
        request.location,
        final.interval,
        sample_subject(final),
    ):
        return None, Check(
            "source_mapping",
            CheckFinding.FAIL,
            ("mapping does not bind exact final sample and original service section",),
        )
    if any(
        getattr(m.context.provenance, f) != getattr(final.provenance, f)
        for f in ("scenario", "reference_member", "reference_kind", "configuration_version")
    ):
        return None, Check(
            "source_mapping", CheckFinding.FAIL, ("mapping evidence belongs to another final input identity",)
        )
    evaluated = control_equivalent(m, mapping.evidence)
    if evaluated.upstream is None:
        return None, Check("source_mapping", CheckFinding.UNKNOWN, evaluated.reasons)
    if evaluated.upstream != final.value:
        return None, Check(
            "source_mapping", CheckFinding.FAIL, ("supported upstream equivalent differs from actual final flow",)
        )
    local = final.value if m.relationship is WaterRelationship.SAME_WATER else m.continuing
    return local, Check(
        "source_mapping",
        CheckFinding.PASS,
        ("actual local carrier flow, not an arbitrary source requirement lower bound",),
    )


def assess_conveyance_conditions(
    request: ServiceConveyanceRequest,
    final: FlowSample,
    *,
    mapping: ControlEquivalent | None = None,
    zero: ServiceZeroDetermination | None = None,
) -> ConveyanceConditionAssessment:
    """Recheck a final physical candidate without solving a new service requirement.

    Source prerequisites use the original request and, when explicitly supplied,
    its zero reconciliation. Neither solve is seeded with the positive final flow.
    Native relation interpolation evaluates final flow without extrapolation. Excess
    inside the supported domain is retained as unassigned through-flow, not a new
    service duty, operating allocation or failed fixed-point convergence.
    Only the original declared numerical balance tolerance applies; it neither
    relaxes a delivery duty nor caps an issued obligation. Raw deficit is retained.
    """
    if not isinstance(request, ServiceConveyanceRequest) or not isinstance(final, FlowSample):
        raise TypeError("typed original service request and actual final FlowSample required")
    if mapping is not None and not isinstance(mapping, ControlEquivalent):
        raise TypeError("typed supported control mapping required")
    if zero is not None and not isinstance(zero, ServiceZeroDetermination):
        raise TypeError("typed scoped zero determination required")
    original_source = solve_service_conveyance(request)
    source = original_source
    checks = []
    zero_checks = None
    accepted_zero = False
    if zero is not None:
        # This is the same explicit zero reconciliation as potential sizing,
        # never a fixed-point solve seeded with the positive final quality flow.
        source = solve_service_conveyance(replace(request, initial_flow=Flow(0)))
        source_evidence = tuple(d.evidence for d in request.duties) + tuple(i.evidence for i in request.other_inflows)
        if request.relation is not None:
            source_evidence += (request.relation.evidence,)
        if request.ramp is not None:
            source_evidence += (request.ramp.evidence,)
        identity = zero.scope.location == request.location and zero.scope.period == request.interval
        identity = (
            identity
            and bool(source_evidence)
            and all(
                zero.scope.scenario == e.provenance.scenario
                and zero.scope.reference_member == e.provenance.reference_member
                and all(
                    getattr(zero.evidence.provenance, f) == getattr(e.provenance, f)
                    for f in ("scenario", "reference_member", "reference_kind", "configuration_version")
                )
                for e in source_evidence
            )
        )
        native_zero = source.status is ConveyanceStatus.UNSUPPORTED and source.zero_candidate == Flow(0)
        zero_checks = CheckSummary(
            (
                *_zero_checks(zero).checks,
                Check(
                    "request_identity",
                    CheckFinding.PASS if identity else CheckFinding.FAIL,
                    (
                        "zero determination must bind original control, accounting period, scenario, member and configuration",
                    ),
                ),
                Check(
                    "native_zero_candidate",
                    CheckFinding.PASS
                    if native_zero
                    else CheckFinding.FAIL
                    if source.flow is not None and source.flow.value > 0
                    else CheckFinding.UNKNOWN,
                    (
                        "native service reconciliation must supply zero; authority cannot erase positive service needs or missing physics",
                    ),
                ),
            )
        )
        checks.extend(Check("zero:" + c.check_id, c.finding, c.reasons) for c in zero_checks.checks)
        accepted_zero = zero_checks.finding is CheckFinding.PASS
        # The separately evaluated native zero is the actual source candidate.
        # A failed discarded initial fixed point stays visible in original_source;
        # zero reconciliation and actual final constraints, not that old trial, gate.

    prerequisite = (
        CheckFinding.PASS
        if source.status is ConveyanceStatus.SUPPORTED or accepted_zero
        else CheckFinding.FAIL
        if source.status is ConveyanceStatus.INFEASIBLE
        else CheckFinding.UNKNOWN
    )
    checks.append(
        Check(
            "source_service",
            prerequisite,
            ("native zero candidate has separately accepted scoped determination",)
            if accepted_zero
            else source.reasons,
        )
    )
    flow, domain = _local_flow(request, final, mapping)
    checks.append(domain)
    capacity = (
        CheckFinding.UNKNOWN
        if request.capacity is None or flow is None
        else CheckFinding.PASS
        if flow.value <= request.capacity.value
        else CheckFinding.FAIL
    )
    checks.append(Check("final_capacity", capacity, ("original control capacity applies to actual final local flow",)))
    relation = request.relation
    state = None
    relation_supported = False
    if relation is None:
        checks.append(
            Check("relation_support", CheckFinding.UNKNOWN, ("original accepted storage/loss relation missing",))
        )
    else:
        reasons = _support_reasons(relation.evidence, relation.identifier, relation.location, relation.interval)
        relation_supported = not reasons
        checks.append(
            Check("relation_support", CheckFinding.PASS if relation_supported else CheckFinding.UNKNOWN, reasons)
        )
        if flow is not None:
            state = _state(relation, flow)
    checks.append(
        Check(
            "final_relation_domain",
            CheckFinding.PASS if state is not None and relation_supported else CheckFinding.UNKNOWN,
            ("native original relation evaluated at actual final flow; outside-domain extrapolation is unsupported",),
        )
    )
    increment = rate = None
    ramp = request.ramp
    if ramp is None:
        checks.append(
            Check("final_ramp", CheckFinding.UNKNOWN, ("original predecessor and directional limits missing",))
        )
    else:
        reasons = _support_reasons(ramp.evidence, "conveyance_ramp", request.location, ramp.transition)
        finding = CheckFinding.UNKNOWN
        if flow is not None:
            increment = flow.value - ramp.previous_flow.value
            rate = increment / ramp.transition.seconds
            if not reasons:
                finding = CheckFinding.PASS if -ramp.fall.value <= increment <= ramp.rise.value else CheckFinding.FAIL
        checks.append(
            Check(
                "final_ramp",
                finding,
                reasons
                or (
                    "original directional increments assessed at actual elapsed predecessor interval; no instantaneous-rate inference",
                ),
            )
        )
    balance = excess = shortfall = None
    duties_supported = (
        bool(source.selected_duties)
        and {d.location for d in source.selected_duties} == {d.location for d in request.duties}
        and all(not _support_reasons(d.evidence, d.identifier, d.location, d.interval) for d in source.selected_duties)
    )
    inflows_supported = all(
        not _support_reasons(i.evidence, i.identifier, i.location, i.interval) for i in request.other_inflows
    )
    if (
        duties_supported
        and inflows_supported
        and state is not None
        and relation_supported
        and flow is not None
        and relation is not None
    ):
        service = sum((d.volume.value for d in source.selected_duties), Fraction())
        inflows = sum((i.volume.value for i in request.other_inflows), Fraction())
        losses = sum((loss.volume.value for loss in state.losses), Fraction())
        needed = service + state.final_storage.value - relation.initial_storage.value + losses - inflows
        balance = flow.value * request.interval.seconds - needed
        excess = Volume(max(Fraction(), balance))
        shortfall = Volume(max(Fraction(), -balance))
        finding = CheckFinding.PASS if balance >= -request.stopping.residual_tolerance.value else CheckFinding.FAIL
        checks.append(
            Check(
                "final_service_balance",
                finding,
                (
                    "required service/storage/loss volumes retained once; positive remainder is unassigned excess, not a new service requirement",
                    "original declared residual-volume tolerance retained; raw shortfall and excess remain visible",
                ),
            )
        )
    else:
        checks.append(
            Check(
                "final_service_balance",
                CheckFinding.UNKNOWN,
                ("supported complete original service inputs and final relation state required",),
            )
        )
    return ConveyanceConditionAssessment(
        request,
        final,
        mapping,
        source,
        flow,
        state,
        balance,
        excess,
        shortfall,
        increment,
        rate,
        CheckSummary(tuple(checks)),
        zero,
        zero_checks,
        original_source,
    )
