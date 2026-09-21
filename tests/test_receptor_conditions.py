"""receptor_condition_tests : OriginalReceptorGoal × FreshSchedule → SourceBoundChecks.

Synthetic supported accounts distinguish changed physical values from erased goals.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from examples.requirement_chain import TARGET, accepted_evidence, lateral, samples, wetland_step
from fishy.evidence import CheckFinding
from fishy.quality import ChemicalBehavior, ChemicalIdentity
from fishy.quantities import Flow, Volume
from fishy.receptor_conditions import assess_receptor_conditions
from fishy.receptor_delivery import (
    BoundInclusion,
    CoupledStateObjective,
    ProcessTest,
    SalinitySupport,
    SupportedProcessTest,
    assess_delivery,
    delivery_scope,
)
from fishy.receptor_states import Compartment, ReceptorDomain, ReceptorVariable, StateStatistic
from fishy.requirement_checks import sample_subject


def approve(step):
    """Exact synthetic final records → newly scoped physical and independent audit evidence."""
    ctx = step.balance.context

    def evidence(subject, audit=False):
        p = replace(ctx.provenance, source="independent synthetic audit") if audit else ctx.provenance
        return accepted_evidence(delivery_scope(ctx, subject), p)

    step = replace(
        step,
        evidence=evidence(step.balance),
        pathways=tuple(replace(p, evidence=evidence(p.pathway)) for p in step.pathways),
        processes=tuple(replace(p, evidence=evidence(p.test)) for p in step.processes),
    )
    if step.state_objective is not None:
        objective = step.state_objective
        step = replace(
            step,
            state_objective=replace(
                objective, quantity=replace(objective.quantity, evidence=evidence(objective.quantity.test))
            ),
        )
        step = replace(
            step, coupled_evidence=evidence(step.coupled_subject), inventory_evidence=evidence(step.inventory_subject)
        )
    return replace(step, checking_evidence=evidence(step.checking_subject, audit=True))


def case(flow=10):
    final = samples(TARGET, flow, "A", "U")[0]
    source = wetland_step(final.interval, "A", "original-pre-quality-source")
    fresh = wetland_step(final.interval, "A", sample_subject(final))
    mapping = lateral(Flow(flow - 1), final.interval, "A", sample_subject(final))
    return source, final, fresh, mapping


def assessed(source, final, fresh, mapping):
    native = assess_delivery((fresh,), period=fresh.balance.context.period)
    return assess_receptor_conditions(source, final, native, mapping)


def coupled(step):
    ctx = step.balance.context
    domain = ReceptorDomain(
        ReceptorVariable.SALINITY,
        Compartment.RESIDENT_WATER,
        "resident dissolved salt",
        ChemicalIdentity("salt", "salt", "salt mass", "dissolved", ChemicalBehavior.CONSERVATIVE),
    )
    salt = replace(step.processes[0].test, variable="salinity", reference=domain.basis)
    area = ProcessTest(
        "wet-area",
        ctx,
        "wet_area",
        "m2",
        "surveyed footprint",
        Fraction(120),
        Fraction(100),
        None,
        BoundInclusion.INCLUSIVE,
        "fixed supported area response",
    )
    objective = CoupledStateObjective(
        SupportedProcessTest(area, None),
        Volume(86400),
        "fixed coupled water/state relation",
        "fixed geometry and boundary",
        "exact synthetic",
        StateStatistic.WHOLE_INTERVAL,
        StateStatistic.WHOLE_INTERVAL,
        (ctx.period,),
        "salt",
        domain,
        SalinitySupport.COUPLED_MODEL,
    )
    return approve(
        replace(
            step,
            balance=replace(step.balance, target=None),
            processes=(SupportedProcessTest(salt, None),),
            state_objective=objective,
        )
    )


@pytest.mark.parametrize("flow", [10, 12])
def test_actual_receiver_need_survives_equal_or_higher_final_throughflow(flow):
    source, final, fresh, mapping = case(flow)
    result = assessed(source, final, fresh, mapping)
    assert result.original.checks.finding is CheckFinding.PASS
    assert result.recomputed is not None and result.recomputed.checks.finding is CheckFinding.PASS
    assert result.checks.finding is CheckFinding.PASS
    assert result.source.balance.context.candidate == "original-pre-quality-source"
    assert result.source.balance.context.candidate != sample_subject(final)


def test_changed_drain_and_zero_release_cannot_erase_original_receiver_need():
    source, final, fresh, mapping = case()
    ctx = fresh.balance.context
    path = replace(fresh.pathways[0].pathway, predecessor=Flow(0))
    fresh = approve(
        replace(
            fresh,
            balance=replace(fresh.balance, exchanges=(replace(fresh.balance.exchanges[0], amount=Volume(0)),)),
            pathways=(replace(fresh.pathways[0], pathway=path, release=Volume(0)),),
        )
    )
    m = replace(mapping.mapping, continuing=final.value, receptor=Flow(0))
    from fishy.receptor_delivery import control_equivalent

    mapping = control_equivalent(m, accepted_evidence(delivery_scope(ctx, m), ctx.provenance))
    # Native fresh physics can support its changed zero-water question. It cannot
    # replace the original supported drain/arrival1 under the same receiver need.
    native = assess_delivery((fresh,))
    assert native.checks.finding is CheckFinding.PASS
    result = assess_receptor_conditions(source, final, native, mapping)
    assert result.checks.finding is CheckFinding.FAIL
    assert next(c for c in result.constraints if c.check_id == "storage_exchanges").finding is CheckFinding.FAIL


def test_fresh_salinity_weakening_cannot_pass_original_supported_limit():
    source, final, fresh, mapping = case()
    salt = replace(fresh.processes[0].test, value=Fraction(5, 1000), upper=Fraction(10, 1000))
    fresh = approve(replace(fresh, processes=(SupportedProcessTest(salt, None),)))
    assert assess_delivery((fresh,)).checks.finding is CheckFinding.PASS
    result = assessed(source, final, fresh, mapping)
    assert result.checks.finding is CheckFinding.FAIL
    assert (
        next(c for c in result.constraints if c.check_id == "process:salt:original_value").finding is CheckFinding.FAIL
    )


def test_supported_new_salinity_value_with_original_limit_passes():
    source, final, fresh, mapping = case()
    salt = replace(fresh.processes[0].test, value=Fraction(1, 2000))
    fresh = approve(replace(fresh, processes=(SupportedProcessTest(salt, None),)))
    assert assessed(source, final, fresh, mapping).checks.finding is CheckFinding.PASS


def test_missing_required_process_does_not_disappear_from_original_manifest():
    source, final, fresh, mapping = case()
    fresh = approve(replace(fresh, processes=(), required_processes=()))
    result = assessed(source, final, fresh, mapping)
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert any(c.check_id == "process:salt" and c.finding is CheckFinding.UNKNOWN for c in result.constraints)


def test_known_changed_storage_failure_survives_missing_process():
    source, final, fresh, mapping = case()
    fresh = approve(
        replace(fresh, balance=replace(fresh.balance, initial=Volume(90000)), processes=(), required_processes=())
    )
    result = assessed(source, final, fresh, mapping)
    assert result.checks.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks.checks)


@pytest.mark.parametrize("change", ["capacity", "ramping", "loss", "target"])
def test_fresh_supported_physical_policy_cannot_relax_original(change):
    source, final, fresh, mapping = case()
    if change == "target":
        fresh = replace(fresh, balance=replace(fresh.balance, target=Volume(0)))
    else:
        path = fresh.pathways[0].pathway
        if change == "capacity":
            path = replace(path, capacity=Flow(3))
        elif change == "ramping":
            path = replace(path, rise_m3_s2=Fraction(1), fall_m3_s2=Fraction(1))
        else:
            path = replace(path, initial_storage=Volume(1), final_storage=Volume(1))
        fresh = replace(fresh, pathways=(replace(fresh.pathways[0], pathway=path),))
    result = assessed(source, final, approve(fresh), mapping)
    assert result.checks.finding is CheckFinding.FAIL


def test_exact_fresh_candidate_identity_required_even_with_supported_native_physics():
    source, final, _, mapping = case()
    stale = wetland_step(final.interval, "A", "another-final-candidate")
    assert assess_delivery((stale,)).checks.finding is CheckFinding.PASS
    assert assessed(source, final, stale, mapping).checks.finding is CheckFinding.FAIL


def test_missing_fresh_assessment_or_mapping_is_not_a_pass():
    source, final, fresh, mapping = case()
    assert assess_receptor_conditions(source, final, None, mapping).checks.finding is CheckFinding.UNKNOWN
    assert assessed(source, final, fresh, None).checks.finding is CheckFinding.UNKNOWN


def test_coupled_state_original_area_goal_is_retained_after_fresh_reacceptance():
    source, final, fresh, mapping = case()
    source, fresh = coupled(source), coupled(fresh)
    assert assessed(source, final, fresh, mapping).checks.finding is CheckFinding.PASS
    objective = fresh.state_objective
    assert objective is not None
    quantity = replace(objective.quantity.test, lower=Fraction(10), value=Fraction(20))
    fresh = approve(replace(fresh, state_objective=replace(objective, quantity=SupportedProcessTest(quantity, None))))
    assert assess_delivery((fresh,)).checks.finding is CheckFinding.PASS
    result = assessed(source, final, fresh, mapping)
    assert result.checks.finding is CheckFinding.FAIL
    assert next(c for c in result.constraints if c.check_id == "quantity:original_value").finding is CheckFinding.FAIL


def test_forged_fresh_summary_is_recomputed_from_actual_state():
    source, final, fresh, mapping = case()
    passing = assess_delivery((fresh,))
    salt = replace(fresh.processes[0].test, value=Fraction(1, 100))
    bad = assess_delivery((approve(replace(fresh, processes=(SupportedProcessTest(salt, None),))),))
    forged = replace(bad, checks=passing.checks)
    assert assess_receptor_conditions(source, final, forged, mapping).checks.finding is CheckFinding.FAIL


def test_missing_original_or_fresh_pathway_remains_unknown():
    source, final, fresh, mapping = case()
    fresh = approve(replace(fresh, pathways=()))
    result = assessed(source, final, fresh, mapping)
    # Missing pathway input is not an observed zero release.
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert any(c.check_id == "pathway:lateral" and c.finding is CheckFinding.UNKNOWN for c in result.constraints)


def test_stronger_salinity_limit_and_changed_supported_value_preserve_original_goal():
    source, final, fresh, mapping = case()
    salt = replace(fresh.processes[0].test, value=Fraction(1, 2000), upper=Fraction(1, 2000))
    fresh = approve(replace(fresh, processes=(SupportedProcessTest(salt, None),)))
    assert assessed(source, final, fresh, mapping).checks.finding is CheckFinding.PASS


def test_changed_coupled_temporal_requirement_cannot_replace_whole_interval_goal():
    source, final, fresh, mapping = case()
    source, fresh = coupled(source), coupled(fresh)
    objective = fresh.state_objective
    assert objective is not None
    fresh = approve(
        replace(
            fresh,
            state_objective=replace(
                objective,
                temporal_support=StateStatistic.INTERVAL_END,
                required_temporal_support=StateStatistic.INTERVAL_END,
            ),
        )
    )
    assert assess_delivery((fresh,)).checks.finding is CheckFinding.PASS
    assert assessed(source, final, fresh, mapping).checks.finding is CheckFinding.FAIL


def test_original_supported_failure_survives_completely_missing_final_inputs():
    source, final, _, _ = case()
    salt = replace(source.processes[0].test, value=Fraction(2, 1000))
    source = approve(replace(source, processes=(SupportedProcessTest(salt, None),)))
    result = assess_receptor_conditions(source, final, None, None)
    assert result.checks.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks.checks)


def test_missing_original_goal_cannot_be_replaced_by_fresh_supported_goal():
    source, final, fresh, mapping = case()
    source = approve(replace(coupled(source), state_objective=None, coupled_evidence=None, inventory_evidence=None))
    fresh = coupled(fresh)
    result = assessed(source, final, fresh, mapping)
    assert result.checks.finding is CheckFinding.UNKNOWN


def test_same_water_receiver_carries_full_final_flow_not_only_lower_bound():
    from fishy.receptor_delivery import WaterRelationship, control_equivalent

    source, final, fresh, mapping = case(12)

    def shared(step):
        period = step.balance.context.period
        path = replace(
            step.pathways[0].pathway,
            capacity=Flow(20),
            predecessor=Flow(12),
            boundary_conditions="explicit fixed shared-flow12 predecessor; no wrap inferred",
        )
        return approve(
            replace(
                step,
                balance=replace(
                    step.balance,
                    exchanges=(replace(step.balance.exchanges[0], amount=Volume(12 * period.seconds)),),
                    relation="steady shared receiver:12 in,12 drain, fixed stock; zero loss or storage change",
                ),
                pathways=(replace(step.pathways[0], pathway=path, release=Volume(12 * period.seconds)),),
            )
        )

    source, fresh = shared(source), shared(fresh)
    m = replace(mapping.mapping, relationship=WaterRelationship.SAME_WATER, continuing=Flow(12), receptor=Flow(1))
    mapping = control_equivalent(m, accepted_evidence(delivery_scope(m.context, m), m.context.provenance))
    assert mapping.upstream == Flow(12)
    result = assessed(source, final, fresh, mapping)
    assert result.original.checks.finding is CheckFinding.PASS
    assert result.recomputed is not None and result.recomputed.checks.finding is CheckFinding.PASS
    assert result.checks.finding is CheckFinding.PASS
    assert next(c for c in result.constraints if c.check_id == "mapped_release").finding is CheckFinding.PASS
