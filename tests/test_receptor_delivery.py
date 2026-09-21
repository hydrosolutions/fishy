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
from fishy.quantities import Flow, Volume
from fishy.receptor_delivery import (
    BoundInclusion,
    ControlMapping,
    DeliveryContext,
    DeliveryStep,
    ExchangeDirection,
    Pathway,
    PathwayRelease,
    ProcessTest,
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
        "arrival_m3= 90\ncontrol_m3= 100\nfinal_storage_m3= 200\nfinding= pass\nofficial_admissibility= pending\n"
    )
