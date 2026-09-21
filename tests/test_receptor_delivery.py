"""Synthetic executable crosswalk for Appendix A step 9 and component assembly."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from fishy.evidence import (
    CheckFinding,
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
from fishy.quality import ChemicalBehavior, ChemicalIdentity
from fishy.quantities import Flow, Volume
from fishy.receptor_delivery import (
    BoundInclusion,
    ControlMapping,
    CoupledStateObjective,
    DeliveryContext,
    DeliveryStep,
    ExchangeDirection,
    Pathway,
    PathwayRelease,
    ProcessTest,
    SalinitySupport,
    StorageBalance,
    SupportedProcessTest,
    WaterExchange,
    WaterRelationship,
    assess_delivery,
    control_equivalent,
    delivery_scope,
    map_arrival,
    storage_arrival,
)
from fishy.receptor_states import Compartment, ReceptorDomain, ReceptorVariable, StateStatistic
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def loc(point="lake"):
    return Location(Reach("receptor", "v1", WaterBody("lake", "v1")), CalculationSection(point, "v1"), "v1")


def context(day=0):
    start = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=day)
    return DeliveryContext(
        loc(),
        Interval(start, start + timedelta(days=1)),
        "selected-1",
        "mixed storage m3",
        Provenance(
            "synthetic storage study",
            "hypothetical",
            "member",
            "v1",
            "v1",
            "v1",
            ProductionMethod.ILLUSTRATIVE,
            CorrectionState.ORIGINAL,
        ),
    )


def evidence(ctx, subject, source=None):
    return EvidenceFindings(
        delivery_scope(ctx, subject),
        ctx.provenance if source is None else replace(ctx.provenance, source=source),
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("synthetic use only",),
    )


def exchange(ctx, carrier, amount, direction=ExchangeDirection.INFLOW):
    return WaterExchange(carrier, ctx, direction, Volume(amount), loc(carrier))


def balance(ctx=None, target=200):
    ctx = context() if ctx is None else ctx
    return StorageBalance(
        ctx,
        Volume(100),
        None if target is None else Volume(target),
        (exchange(ctx, "rain", 20), exchange(ctx, "evaporation", 10, ExchangeDirection.OUTFLOW)),
        "surveyed storage balance v1; constant supplied exchanges",
        "synthetic exact quantities",
    )


def pathway(ctx=None, name="canal", delay=timedelta(hours=6)):
    ctx = context() if ctx is None else ctx
    period = Interval(ctx.period.start - delay, ctx.period.end - delay)
    return Pathway(
        name,
        ctx,
        loc("gate"),
        period,
        delay,
        Volume(3),
        Volume(5),
        (exchange(ctx, name + "-seepage", 8, ExchangeDirection.OUTFLOW),),
        Flow(0),
        Flow(1),
        Flow(0),
        Interval(period.start - timedelta(days=1), period.start),
        Fraction(1),
        Fraction(1),
        "fixed-delay storage account v1",
        "supplied stocks and constant loss volume",
        "exact synthetic",
    )


def selected_step(b=None, paths=None):
    b = balance() if b is None else b
    if paths is None:
        p = pathway(b.context)
        paths = (PathwayRelease(p, Volume(100), evidence(b.context, p)),)
    test = ProcessTest(
        "salinity",
        b.context,
        "resident salt",
        "kg/m3",
        "mixed compartment; full interval",
        Fraction(3, 10),
        None,
        Fraction(1),
        BoundInclusion.INCLUSIVE,
        "independent process model v2",
    )
    step = DeliveryStep(
        b,
        evidence(b.context, b),
        paths,
        tuple(p.pathway.identifier for p in paths),
        ("salinity",),
        (SupportedProcessTest(test, evidence(b.context, test)),),
        None,
    )
    return reviewed(step)


def reviewed(step):
    return replace(
        step, checking_evidence=evidence(step.balance.context, step.checking_subject, "independent audit v1")
    )


def test_storage_residual_counts_rain_and_outflow_once():
    b = balance()
    result = storage_arrival(b, evidence(b.context, b))
    assert result.signed_residual_m3 == 90
    assert result.arrival == Volume(90)
    assert result.surplus == Volume(0)
    assert result.evidence is not None
    assert result.evidence.provenance.scenario == "hypothetical"
    assert result.evidence.official_admissibility is OfficialAdmissibility.PENDING


def test_negative_residual_is_surplus_not_satisfaction():
    b = balance(target=50)
    result = storage_arrival(b, evidence(b.context, b))
    assert result.signed_residual_m3 == -60
    assert result.arrival == Volume(0)
    assert result.surplus == Volume(60)
    assert "not established" in result.reasons[0]
    p = pathway()
    step = selected_step(b, (PathwayRelease(p, Volume(10), evidence(b.context, p)),))
    result = assess_delivery((step,))
    assert result.steps[0].final_storage == Volume(110)
    assert result.checks.finding is CheckFinding.FAIL


@pytest.mark.parametrize(
    "mode", ["missing_target", "missing_relation", "unsupported", "restricted", "changed_relation"]
)
def test_unsized_missing_or_unsupported(mode):
    b = balance(target=None if mode == "missing_target" else 200)
    ev = evidence(b.context, b)
    if mode == "missing_relation":
        ev = None
    elif mode == "unsupported":
        ev = replace(ev, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
    elif mode == "restricted":
        from fishy.evidence import UseRestriction

        ev = replace(ev, restrictions=(UseRestriction("outside surveyed range", ("receptor_delivery",)),))
    elif mode == "changed_relation":
        b = replace(b, relation="unaccepted revised relation")
    result = storage_arrival(b, ev)
    assert result.arrival is None
    assert result.reasons


def test_arrival_control_losses_delay_stocks_and_recheck():
    step = selected_step()
    p = step.pathways[0].pathway
    assert map_arrival(p, Volume(90)) == Volume(100)
    assert p.release_period.start + timedelta(hours=6) == p.context.period.start
    result = assess_delivery((step,))
    assert result.checks.finding is CheckFinding.PASS
    assert result.steps[0].pathways[0].arrival == Volume(90)
    assert result.steps[0].final_storage == Volume(200)
    assert result.steps[0].target_residual_m3 == 0
    assert result.steps[0].pathways[0].control_flow == Flow(Fraction(100, 86400))


@pytest.mark.parametrize("constraint", ["capacity", "ramping", "water_balance"])
def test_infeasible_schedule_never_reduces_requirement(constraint):
    p = pathway()
    if constraint == "capacity":
        p = replace(p, capacity=Flow(Fraction(99, 86400)))
    elif constraint == "ramping":
        p = replace(p, rise_m3_s2=Fraction(0))
    else:
        p = replace(p, final_storage=Volume(200))
    step = selected_step(paths=(PathwayRelease(p, Volume(100), evidence(p.context, p)),))
    result = assess_delivery((step,))
    assert result.checks.finding is CheckFinding.FAIL
    assert result.steps[0].residual.arrival == Volume(90)
    assert any(c.check_id.endswith(constraint) and c.finding is CheckFinding.FAIL for c in result.checks.checks)


def test_unresolved_multiple_paths_and_supplied_operating_selection():
    step = selected_step()
    unresolved = reviewed(replace(step, pathways=(), required_pathways=("canal", "river")))
    result = assess_delivery((unresolved,))
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.steps[0].residual.arrival == Volume(90)
    assert result.steps[0].final_storage is None
    p1, p2 = pathway(name="canal"), pathway(name="river")
    selected = selected_step(paths=tuple(PathwayRelease(p, Volume(55), evidence(p.context, p)) for p in (p1, p2)))
    result = assess_delivery((selected,))
    assert result.checks.finding is CheckFinding.PASS
    assert tuple(p.arrival for p in result.steps[0].pathways) == (Volume(45), Volume(45))


def test_unknown_quality_and_supported_failure_are_lossless():
    step = selected_step()
    test = replace(step.processes[0].test, value=Fraction(2))
    step = reviewed(
        replace(
            step,
            required_processes=("salinity", "temperature"),
            processes=(SupportedProcessTest(test, evidence(test.context, test)),),
        )
    )
    result = assess_delivery((step,))
    assert result.checks.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks.checks)
    unsupported = replace(step.processes[0].evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
    step = reviewed(replace(step, processes=(SupportedProcessTest(test, unsupported),)))
    assert assess_delivery((step,)).checks.finding is CheckFinding.UNKNOWN


def test_complete_discrete_trajectory_rechecks_intermediate_target():
    first = selected_step()
    b2 = replace(balance(context(1), target=300), initial=Volume(200))
    p2 = replace(pathway(context(1)), initial_storage=Volume(5), predecessor=Flow(Fraction(100, 86400)))
    second = selected_step(b2, (PathwayRelease(p2, Volume(98), evidence(b2.context, p2)),))
    result = assess_delivery((first, second))
    assert result.checks.finding is CheckFinding.PASS
    assert tuple(s.final_storage for s in result.steps) == (Volume(200), Volume(300))
    bad_balance = replace(first.balance, target=Volume(250))
    bad_first = reviewed(replace(first, balance=bad_balance, evidence=evidence(bad_balance.context, bad_balance)))
    result = assess_delivery((bad_first, second))
    assert result.steps[-1].checks.finding is CheckFinding.PASS
    assert result.checks.finding is CheckFinding.FAIL


def test_reject_duplicate_carriers_and_mismatched_identities():
    b = balance()
    with pytest.raises(ValueError, match="duplicate"):
        replace(b, exchanges=(b.exchanges[0], b.exchanges[0]))
    with pytest.raises(ValueError, match="incompatible"):
        replace(b, exchanges=(replace(b.exchanges[0], context=context(1)),))
    step = selected_step()
    p = replace(step.pathways[0].pathway, identifier="rain")
    with pytest.raises(ValueError, match="duplicate carrier"):
        replace(step, pathways=(PathwayRelease(p, Volume(100), evidence(p.context, p)),), required_pathways=("rain",))
    with pytest.raises(ValueError, match="scenario"):
        storage_arrival(b, replace(evidence(b.context, b), provenance=replace(b.context.provenance, scenario="other")))
    with pytest.raises(ValueError, match="delay"):
        replace(pathway(), travel_time=timedelta(hours=5))
    with pytest.raises(ValueError, match="nonadjacent"):
        assess_delivery((step, step))
    with pytest.raises(ValueError, match="incompatible"):
        replace(step, balance=replace(b, context=replace(b.context, domain="root zone"), exchanges=()))


def test_independent_check_and_missing_process_cannot_pass():
    step = selected_step()
    assert assess_delivery((replace(step, checking_evidence=None),)).checks.finding is CheckFinding.UNKNOWN
    step = reviewed(replace(step, processes=()))
    assert assess_delivery((step,)).checks.finding is CheckFinding.UNKNOWN
    assert assess_delivery(()).checks.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize("relationship, expected", [(WaterRelationship.SAME_WATER, 3), (WaterRelationship.LATERAL, 5)])
def test_source_component_crosswalk_same_water_3_lateral_5(relationship, expected):
    ctx = context()
    mapping = ControlMapping(
        ctx,
        loc("upstream"),
        loc("continuing"),
        Flow(3),
        Flow(2),
        relationship,
        "explicit supported zero-loss zero-delay equivalence",
    )
    result = control_equivalent(mapping, evidence(ctx, mapping))
    assert result.upstream == Flow(expected)
    assert result.mapping.continuing == Flow(3)
    assert result.mapping.receptor == Flow(2)
    assert control_equivalent(mapping, None).upstream is None


def test_nonnegative_and_exact_domain_validation():
    with pytest.raises(ValueError):
        replace(pathway(), rise_m3_s2=Fraction(-1))
    with pytest.raises(ValueError):
        Volume(float("nan"))
    with pytest.raises(ValueError):
        Volume(-1)
    p = replace(pathway(), initial_storage=Volume(1000))
    assert map_arrival(p, Volume(1)) is None


def test_required_empty_process_profile_does_not_certify_receptor():
    step = reviewed(replace(selected_step(), processes=(), required_processes=()))
    assert assess_delivery((step,)).checks.finding is CheckFinding.UNKNOWN


def test_declared_period_cannot_omit_first_or_last_step():
    step = selected_step()
    period = Interval(context().period.start, context(1).period.end)
    result = assess_delivery((step,), period=period)
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.steps[0].checks.finding is CheckFinding.PASS


def test_control_warmup_exclusion_is_not_hidden_by_later_arrival():
    step = selected_step()
    selected = step.pathways[0]
    p = selected.pathway
    excluded = Interval(p.release_period.start, p.context.period.start)
    ev = replace(selected.evidence, provenance=replace(selected.evidence.provenance, excluded_warmup=(excluded,)))
    step = reviewed(replace(step, pathways=(replace(selected, evidence=ev),)))
    assert assess_delivery((step,)).checks.finding is CheckFinding.UNKNOWN


def test_public_delivery_example_executes_without_simulator_import(monkeypatch, capsys):
    import builtins
    import runpy

    original_import = builtins.__import__

    def without_simulator(name, *args, **kwargs):
        if name.split(".")[0] in ("taqsim", "incidence"):
            raise AssertionError("the supplied delivery example must not import a simulator")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_simulator)
    runpy.run_module("examples.receptor_delivery", run_name="__main__")
    assert capsys.readouterr().out == (
        "arrival_m3= 90\ncontrol_m3= 100\nfinal_storage_m3= 200\nfinding= pass\nofficial_admissibility= pending\nnonstorage_finding= pass\n"
    )


def wet_area_step():
    """Selected schedule with a supported area target, not a storage target."""
    step = selected_step(balance(target=None))
    salinity_domain = ReceptorDomain(
        ReceptorVariable.SALINITY,
        Compartment.RESIDENT_WATER,
        "mixed compartment; conservative dissolved salt as supplied chloride",
        ChemicalIdentity("chloride", "Cl-", "as chloride", "dissolved", ChemicalBehavior.CONSERVATIVE),
    )
    salt = replace(step.processes[0].test, variable="salinity", reference=salinity_domain.basis)
    step = replace(step, processes=(SupportedProcessTest(salt, evidence(salt.context, salt)),))
    area = ProcessTest(
        "wet-area",
        step.balance.context,
        "wet_area",
        "m2",
        "surveyed wetland footprint v1",
        Fraction(120),
        Fraction(100),
        None,
        BoundInclusion.INCLUSIVE,
        "coupled inundation study v1",
    )
    objective = CoupledStateObjective(
        SupportedProcessTest(area, evidence(area.context, area)),
        Volume(200),
        "coupled surface-groundwater relation v1",
        "surveyed footprint, supplied boundary head and selected releases",
        "illustrative exact response; not a calibration",
        StateStatistic.WHOLE_INTERVAL,
        StateStatistic.WHOLE_INTERVAL,
        (step.balance.context.period,),
        "salinity",
        salinity_domain,
        SalinitySupport.COUPLED_MODEL,
    )
    step = replace(step, state_objective=objective)
    return coupled_reviewed(step)


def coupled_reviewed(step):
    return reviewed(
        replace(step, coupled_evidence=evidence(step.balance.context, step.coupled_subject, "coupled model study"))
    )


def test_supported_nonstorage_schedule_is_assessed_without_fake_storage_target():
    step = wet_area_step()
    result = assess_delivery((step,), period=step.balance.context.period)
    assert result.checks.finding is CheckFinding.PASS
    assert step.balance.target is None
    assert result.steps[0].final_storage == Volume(200)
    assert result.steps[0].residual.arrival is None


@pytest.mark.parametrize(
    "variable, units, value, lower, upper",
    [
        ("wet_area", "m2", Fraction(120), Fraction(100), Fraction(150)),
        ("groundwater_head", "m", Fraction(-2), Fraction(-3), Fraction(-1)),
        ("level", "m", Fraction(12), Fraction(10), Fraction(15)),
        ("hydroperiod", "s", Fraction(43200), Fraction(36000), Fraction(86400)),
    ],
)
def test_supported_coupled_quantity_domains(variable, units, value, lower, upper):
    step = wet_area_step()
    objective = step.state_objective
    assert objective is not None
    test = replace(objective.quantity.test, variable=variable, units=units, value=value, lower=lower, upper=upper)
    objective = replace(objective, quantity=SupportedProcessTest(test, evidence(test.context, test)))
    step = coupled_reviewed(replace(step, state_objective=objective))
    result = assess_delivery((step,), period=step.balance.context.period)
    assert result.checks.finding is CheckFinding.PASS
    assert result.steps[0].target_residual_m3 is None
    assert result.steps[0].step.state_objective == objective


@pytest.mark.parametrize(
    "mode",
    [
        "relation_missing",
        "relation_unsupported",
        "quantity_missing",
        "quantity_unsupported",
        "quality_missing",
        "independent_missing",
        "changed_schedule",
        "endpoint_only",
        "missing_interval",
    ],
)
def test_nonstorage_missing_or_unsupported_remains_unresolved(mode):
    step = wet_area_step()
    objective = step.state_objective
    assert objective is not None
    if mode == "relation_missing":
        step = replace(step, coupled_evidence=None)
    elif mode == "relation_unsupported":
        assert step.coupled_evidence is not None
        step = replace(
            step, coupled_evidence=replace(step.coupled_evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
        )
    elif mode in ("quantity_missing", "quantity_unsupported"):
        quantity = objective.quantity
        if mode == "quantity_missing":
            test = replace(quantity.test, value=None)
            quantity = SupportedProcessTest(test, evidence(test.context, test))
        else:
            assert quantity.evidence is not None
            quantity = replace(
                quantity, evidence=replace(quantity.evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
            )
        step = coupled_reviewed(replace(step, state_objective=replace(objective, quantity=quantity)))
    elif mode == "quality_missing":
        step = reviewed(replace(step, processes=()))
    elif mode == "independent_missing":
        step = replace(step, checking_evidence=None)
    elif mode == "changed_schedule":
        # Changing a physical study parameter without reacceptance cannot reuse the coupled result.
        path = replace(step.pathways[0].pathway, capacity=Flow(2))
        selected = PathwayRelease(path, step.pathways[0].release, evidence(path.context, path))
        step = reviewed(replace(step, pathways=(selected,)))
    elif mode == "endpoint_only":
        step = coupled_reviewed(
            replace(step, state_objective=replace(objective, temporal_support=StateStatistic.INTERVAL_END))
        )
    else:
        expected = (step.balance.context.period, context(1).period)
        step = coupled_reviewed(replace(step, state_objective=replace(objective, expected_intervals=expected)))
    result = assess_delivery((step,), period=step.balance.context.period)
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.steps[0].residual.arrival is None


@pytest.mark.parametrize("mode", ["quantity_failure", "strict_equality", "inventory_failure", "capacity_failure"])
def test_nonstorage_infeasible_candidate_preserves_quantity_requirement(mode):
    step = wet_area_step()
    objective = step.state_objective
    assert objective is not None
    if mode in ("quantity_failure", "strict_equality"):
        test = replace(
            objective.quantity.test,
            value=Fraction(99) if mode == "quantity_failure" else Fraction(100),
            boundary=BoundInclusion.INCLUSIVE if mode == "quantity_failure" else BoundInclusion.STRICT,
        )
        objective = replace(objective, quantity=SupportedProcessTest(test, evidence(test.context, test)))
        step = coupled_reviewed(replace(step, state_objective=objective))
    elif mode == "inventory_failure":
        step = coupled_reviewed(replace(step, state_objective=replace(objective, final_inventory=Volume(201))))
    else:
        path = replace(step.pathways[0].pathway, capacity=Flow(0))
        selected = PathwayRelease(path, Volume(100), evidence(path.context, path))
        step = coupled_reviewed(replace(step, pathways=(selected,)))
    result = assess_delivery((step,), period=step.balance.context.period)
    assert result.checks.finding is CheckFinding.FAIL
    assert step.state_objective is not None
    assert step.state_objective.quantity.test.lower == Fraction(100)
    assert step.balance.target is None


def test_nonstorage_cannot_replace_missing_storage_target_implicitly():
    step = selected_step(balance(target=None))
    assert assess_delivery((step,)).checks.finding is CheckFinding.UNKNOWN
    objective = wet_area_step().state_objective
    assert objective is not None
    with pytest.raises(ValueError, match="storage target"):
        replace(selected_step(), state_objective=objective)
    with pytest.raises(ValueError, match="variable/unit"):
        replace(
            objective,
            quantity=replace(
                objective.quantity, test=replace(objective.quantity.test, variable="salinity", units="kg/m3")
            ),
        )
    with pytest.raises(ValueError, match="variable/unit"):
        replace(objective, quantity=replace(objective.quantity, test=replace(objective.quantity.test, units="m")))
    with pytest.raises(ValueError, match="adjacent"):
        replace(objective, expected_intervals=(context().period, context(2).period))


def test_coupled_expected_subdaily_axis_cannot_be_replaced_by_daily_endpoint():
    step = wet_area_step()
    objective = step.state_objective
    assert objective is not None
    period = step.balance.context.period
    midpoint = period.start + timedelta(hours=12)
    with pytest.raises(ValueError, match="expected trajectory"):
        replace(objective, expected_intervals=(Interval(period.start, midpoint), Interval(midpoint, period.end)))


def coupled_trajectory():
    first = wet_area_step()
    objective = first.state_objective
    assert objective is not None
    ctx = context(1)
    b = replace(balance(ctx, target=None), initial=Volume(200))
    path = replace(pathway(ctx), initial_storage=Volume(5), predecessor=Flow(Fraction(100, 86400)))
    selected = PathwayRelease(path, Volume(98), evidence(ctx, path))
    second = selected_step(b, (selected,))
    salt = replace(first.processes[0].test, context=ctx)
    second = replace(second, processes=(SupportedProcessTest(salt, evidence(ctx, salt)),))
    area = replace(objective.quantity.test, context=ctx)
    expected = (first.balance.context.period, ctx.period)
    second_objective = replace(
        objective,
        quantity=SupportedProcessTest(area, evidence(ctx, area)),
        final_inventory=Volume(300),
        expected_intervals=expected,
    )
    first = coupled_reviewed(replace(first, state_objective=replace(objective, expected_intervals=expected)))
    second = coupled_reviewed(replace(second, state_objective=second_objective))
    return first, second


def test_coupled_complete_trajectory_rechecks_intermediate_quantity_and_balance():
    first, second = coupled_trajectory()
    period = Interval(first.balance.context.period.start, second.balance.context.period.end)
    assert assess_delivery((first, second), period=period).checks.finding is CheckFinding.PASS
    objective = first.state_objective
    assert objective is not None
    bad = replace(objective.quantity.test, value=Fraction(50))
    failed = coupled_reviewed(
        replace(
            first, state_objective=replace(objective, quantity=SupportedProcessTest(bad, evidence(bad.context, bad)))
        )
    )
    result = assess_delivery((failed, second), period=period)
    assert result.steps[-1].checks.finding is CheckFinding.PASS
    assert result.checks.finding is CheckFinding.FAIL
    # A terminal state pass does not repair the first independent physical balance.
    failed = coupled_reviewed(replace(first, state_objective=replace(objective, final_inventory=Volume(199))))
    result = assess_delivery((failed, second), period=period)
    assert result.steps[-1].checks.finding is CheckFinding.PASS
    assert result.checks.finding is CheckFinding.FAIL


def test_changed_release_invalidates_prior_coupled_evidence():
    step = wet_area_step()
    old_evidence = step.coupled_evidence
    changed = replace(step.pathways[0], release=Volume(101))
    objective = step.state_objective
    assert objective is not None
    step = reviewed(replace(step, pathways=(changed,), state_objective=replace(objective, final_inventory=Volume(201))))
    assert step.coupled_evidence == old_evidence
    result = assess_delivery((step,))
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert (
        next(c for c in result.steps[0].checks.checks if c.check_id == "coupled_relation").finding
        is CheckFinding.UNKNOWN
    )


def test_nonstorage_required_quantity_failure_survives_missing_salinity():
    step = wet_area_step()
    objective = step.state_objective
    assert objective is not None
    test = replace(objective.quantity.test, value=Fraction(50))
    objective = replace(objective, quantity=SupportedProcessTest(test, evidence(test.context, test)))
    step = coupled_reviewed(replace(step, state_objective=objective, processes=()))
    result = assess_delivery((step,))
    assert result.checks.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks.checks)
    assert objective.quantity.evidence is not None
    unsupported = replace(objective.quantity.evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
    step = coupled_reviewed(
        replace(step, state_objective=replace(objective, quantity=SupportedProcessTest(test, unsupported)))
    )
    assert assess_delivery((step,)).checks.finding is CheckFinding.UNKNOWN


def test_nonstorage_arbitrary_process_does_not_replace_named_salinity():
    step = wet_area_step()
    test = replace(step.processes[0].test, identifier="temperature", variable="temperature", units="degC")
    step = coupled_reviewed(
        replace(
            step,
            required_processes=("temperature",),
            processes=(SupportedProcessTest(test, evidence(test.context, test)),),
        )
    )
    result = assess_delivery((step,))
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert (
        next(c for c in result.steps[0].checks.checks if c.check_id == "salinity_profile").finding
        is CheckFinding.UNKNOWN
    )


def test_coupled_quantity_units_do_not_authenticate_salinity_variable():
    step = wet_area_step()
    wrong = replace(step.processes[0].test, variable="temperature")
    step = coupled_reviewed(replace(step, processes=(SupportedProcessTest(wrong, evidence(wrong.context, wrong)),)))
    assert assess_delivery((step,)).checks.finding is CheckFinding.UNKNOWN


def test_unsupported_coupled_model_cannot_support_its_numeric_salinity_failure():
    step = wet_area_step()
    salt = replace(step.processes[0].test, value=Fraction(2))
    step = coupled_reviewed(replace(step, processes=(SupportedProcessTest(salt, evidence(salt.context, salt)),)))
    assert step.coupled_evidence is not None
    step = replace(
        step, coupled_evidence=replace(step.coupled_evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
    )
    assert assess_delivery((step,)).checks.finding is CheckFinding.UNKNOWN


def test_coupled_salinity_domain_rejects_incoming_and_wrong_chemical_basis():
    step = wet_area_step()
    objective = step.state_objective
    assert objective is not None
    with pytest.raises(ValueError, match="incoming"):
        replace(objective, salinity_domain=replace(objective.salinity_domain, compartment=Compartment.INCOMING_WATER))
    wrong = replace(step.processes[0].test, reference="source water only")
    step = coupled_reviewed(replace(step, processes=(SupportedProcessTest(wrong, evidence(wrong.context, wrong)),)))
    assert assess_delivery((step,)).checks.finding is CheckFinding.UNKNOWN


def test_explicit_supported_root_zone_salinity_preserves_domain():
    step = wet_area_step()
    objective = step.state_objective
    assert objective is not None
    domain = replace(
        objective.salinity_domain, compartment=Compartment.ROOT_ZONE, basis="surveyed root zone dissolved chloride"
    )
    salt = replace(step.processes[0].test, reference=domain.basis)
    step = coupled_reviewed(
        replace(
            step,
            state_objective=replace(objective, salinity_domain=domain),
            processes=(SupportedProcessTest(salt, evidence(salt.context, salt)),),
        )
    )
    result = assess_delivery((step,))
    assert result.checks.finding is CheckFinding.PASS
    assert result.steps[0].step.state_objective is not None
    assert result.steps[0].step.state_objective.salinity_domain.compartment is Compartment.ROOT_ZONE


def test_independent_salinity_failure_survives_unsupported_coupled_model():
    step = wet_area_step()
    objective = step.state_objective
    assert objective is not None
    salt = replace(step.processes[0].test, value=Fraction(2))
    objective = replace(objective, salinity_support=SalinitySupport.INDEPENDENT_IMPORT)
    step = replace(step, state_objective=objective, processes=(SupportedProcessTest(salt, None),))
    # Independent acceptance binds chemical form, compartment, basis and numeric test.
    salt_evidence = evidence(salt.context, step.salinity_subject, "independent receptor sampling")
    step = coupled_reviewed(replace(step, processes=(SupportedProcessTest(salt, salt_evidence),)))
    assert step.coupled_evidence is not None
    step = replace(
        step, coupled_evidence=replace(step.coupled_evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
    )
    result = assess_delivery((step,))
    assert result.checks.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks.checks)
    # A generic numeric-test acceptance is insufficient for an independent chemical/domain claim.
    wrong = replace(step, processes=(SupportedProcessTest(salt, evidence(salt.context, salt)),))
    assert assess_delivery((wrong,)).checks.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize("field", ["value", "lower", "upper"])
def test_salinity_nonnegative_domain_rejects_negative_values_and_bounds(field):
    step = wet_area_step()
    salt = step.processes[0].test
    # Avoid an unrelated reversed-range rejection when probing a negative upper.
    if field == "upper":
        salt = replace(salt, lower=None)
    with pytest.raises(ValueError, match="concentration cannot be negative"):
        replace(salt, **{field: Fraction(-1)})


def test_unsupported_imported_inventory_cannot_supply_physical_failure():
    step = wet_area_step()
    objective = step.state_objective
    assert objective is not None
    step = replace(
        step,
        state_objective=replace(objective, final_inventory=Volume(201)),
        coupled_evidence=None,
        checking_evidence=None,
    )
    result = assess_delivery((step,))
    assert result.steps[0].final_storage == Volume(200)
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert (
        next(c for c in result.steps[0].checks.checks if c.check_id == "coupled_water_balance").finding
        is CheckFinding.UNKNOWN
    )


def test_independent_inventory_failure_survives_missing_model_and_checker():
    step = wet_area_step()
    assert step.state_objective is not None
    step = replace(
        step,
        state_objective=replace(step.state_objective, final_inventory=Volume(201)),
        coupled_evidence=None,
        checking_evidence=None,
    )
    step = replace(
        step, inventory_evidence=evidence(step.balance.context, step.inventory_subject, "independent water survey")
    )
    result = assess_delivery((step,))
    assert result.steps[0].inventory_residual_m3 == Fraction(-1)
    assert result.checks.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks.checks)
    assert (
        next(c for c in result.steps[0].checks.checks if c.check_id == "coupled_water_balance").finding
        is CheckFinding.FAIL
    )


def test_supported_coupled_inventory_failure_does_not_need_final_checker():
    step = wet_area_step()
    assert step.state_objective is not None
    step = coupled_reviewed(replace(step, state_objective=replace(step.state_objective, final_inventory=Volume(201))))
    result = assess_delivery((replace(step, checking_evidence=None),))
    assert result.steps[0].inventory_residual_m3 == Fraction(-1)
    assert result.checks.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks.checks)


@pytest.mark.parametrize("mode", ["missing", "generic_balance", "changed_final", "excluded", "unsupported"])
def test_inventory_acceptance_binds_actual_final_inventory_and_use(mode):
    step = wet_area_step()
    assert step.state_objective is not None
    step = replace(
        step,
        state_objective=replace(step.state_objective, final_inventory=Volume(201)),
        coupled_evidence=None,
        checking_evidence=None,
    )
    ev = evidence(step.balance.context, step.inventory_subject, "independent water survey")
    if mode == "missing":
        ev = None
    elif mode == "generic_balance":
        ev = evidence(step.balance.context, step.balance)
    elif mode == "changed_final":
        step = replace(step, state_objective=replace(step.state_objective, final_inventory=Volume(202)))
    elif mode == "excluded":
        ev = replace(ev, provenance=replace(ev.provenance, excluded_warmup=(step.balance.context.period,)))
    else:
        ev = replace(ev, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
    result = assess_delivery((replace(step, inventory_evidence=ev),))
    assert result.steps[0].inventory_residual_m3 in (Fraction(-1), Fraction(-2))
    assert result.checks.finding is CheckFinding.UNKNOWN


def test_inventory_evidence_cannot_change_scenario():
    step = wet_area_step()
    ev = evidence(step.balance.context, step.inventory_subject, "independent water survey")
    ev = replace(ev, provenance=replace(ev.provenance, scenario="other"))
    with pytest.raises(ValueError, match="scenario"):
        assess_delivery((replace(step, coupled_evidence=None, inventory_evidence=ev),))


@pytest.mark.parametrize("variable,unit", [("wet_area", "m2"), ("hydroperiod", "s")])
@pytest.mark.parametrize("field", ["value", "lower", "upper"])
def test_nonstorage_nonnegative_quantity_bounds(variable, unit, field):
    step = wet_area_step()
    objective = step.state_objective
    assert objective is not None
    test = replace(objective.quantity.test, variable=variable, units=unit, lower=None, upper=Fraction(100))
    test = replace(test, **{field: Fraction(-1)})
    with pytest.raises(ValueError, match="cannot be negative"):
        replace(objective, quantity=SupportedProcessTest(test, evidence(test.context, test)))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonstorage_process_requires_finite_exact_values(value):
    salt = wet_area_step().processes[0].test
    with pytest.raises(ValueError, match="finite exact"):
        replace(salt, value=value)
