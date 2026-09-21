"""Derived synthetic witnesses for the held receptor suite; no policy defaults."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

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
    UseRestriction,
)
from fishy.flows import Presence
from fishy.load_accounts import AccountProcess, AccountTransfer, Inventory, LoadAccount, Mass
from fishy.quality import ChemicalBehavior, ChemicalIdentity, Comparison, ProfileStatus
from fishy.quantities import Volume
from fishy.receptor_inventory import (
    CountedLoad,
    MixedCompartmentEvidence,
    ReceptorBalance,
    Remobilisation,
    import_receptor_inventory,
)
from fishy.receptor_states import (
    BoundaryHistory,
    Compartment,
    Duration,
    DurationCriterion,
    DurationOperator,
    ReceptorBounds,
    ReceptorContext,
    ReceptorDomain,
    ReceptorProfile,
    ReceptorState,
    ReceptorTarget,
    ReceptorValue,
    ReceptorVariable,
    StateStatistic,
    assess_joint_duration,
    assess_receptor,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

START = datetime(2025, 1, 1, tzinfo=UTC)
LOCATION = Location(Reach("wetland", "1", WaterBody("lake", "1")), CalculationSection("resident", "1"), "1")
CHEMICAL = ChemicalIdentity("salt", "dissolved", "salt mass", "dissolved", ChemicalBehavior.CONSERVATIVE)
WATER = ReceptorDomain(ReceptorVariable.STORAGE, Compartment.RESIDENT_WATER, "surveyed storage")
SALT = ReceptorDomain(ReceptorVariable.SALINITY, Compartment.RESIDENT_WATER, "representative mixed water", CHEMICAL)
PASS, FAIL, UNKNOWN = CheckFinding.PASS, CheckFinding.FAIL, CheckFinding.UNKNOWN


def context(days=1):
    return ReceptorContext(
        LOCATION, "schedule-A", "hypothetical", "member-A", Interval(START, START + timedelta(days=days))
    )


def provenance():
    return Provenance(
        "synthetic independent study",
        "hypothetical",
        "member-A",
        "test-1",
        "study-1",
        "config-1",
        ProductionMethod.IMPORTED,
        CorrectionState.ORIGINAL,
    )


def evidence(ctx, product, period=None):
    return EvidenceFindings(
        ctx.evidence_scope(product, period or ctx.period),
        provenance(),
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("hypothetical configured-use evidence only",),
    )


def profile(days=1, statistic=StateStatistic.INTERVAL_END, minimum=200):
    ctx = context(days)
    periods = tuple(Interval(START + timedelta(days=i), START + timedelta(days=i + 1)) for i in range(days))
    targets = (
        ReceptorTarget(
            "quantity",
            ReceptorValue(WATER, minimum, "m3"),
            Comparison.GE,
            statistic,
            "synthetic wet season",
            "declared daily slots",
            "supplied habitat objective",
            evidence(ctx, "quantity"),
        ),
        ReceptorTarget(
            "salinity",
            ReceptorValue(SALT, 1, "kg/m3"),
            Comparison.LE,
            statistic,
            "synthetic wet season",
            "declared daily slots",
            "supplied salt tolerance",
            evidence(ctx, "salinity"),
        ),
    )
    return ReceptorProfile(
        "joint-study", "1", ctx, periods, targets, ("quantity",), ("salinity",), ProfileStatus.SCENARIO
    )


def state(p, domain, value, index=0, presence=Presence.PRESENT, statistic=None):
    bounds = None
    if value is not None:
        v = ReceptorValue(domain, value, domain.unit)
        bounds = ReceptorBounds(v, v, "exact synthetic supplied bound", "study-1")
    return ReceptorState(
        p.context,
        p.intervals[index],
        domain,
        statistic or p.targets[0].statistic,
        bounds,
        presence,
        evidence(p.context, p.context.candidate, p.intervals[index]),
        () if presence is Presence.PRESENT else ("required state not supported",),
    )


def inventory_import(p, initial, final, arrival=(0, 0), evaporation=0):
    account = LoadAccount(
        "wetland",
        CHEMICAL,
        p.intervals[0],
        p.context.scenario,
        Inventory(Volume(initial[0]), Mass(initial[1])),
        Inventory(Volume(final[0]), Mass(final[1])),
        provenance(),
        (AccountProcess("evaporation", -Fraction(evaporation), Fraction(0), "nonvolatile conservative salt"),),
    )
    transfers = (AccountTransfer("arrival", None, "wetland", Inventory(Volume(arrival[0]), Mass(arrival[1]))),)
    loads = (CountedLoad("arrival-salt", "arrival"),) if arrival[1] else ()
    balance = ReceptorBalance(account, transfers, loads)
    ev = evidence(p.context, p.context.candidate, p.intervals[0])
    mixed = MixedCompartmentEvidence(SALT, ev, Remobilisation.NOT_REQUIRED)
    return import_receptor_inventory(balance, p.context, WATER, ev, mixed)


@pytest.mark.parametrize(
    "initial,arrival,evaporation,final,minimum,concentration,salinity",
    [
        ((100, 50), (100, 200), 0, (200, 250), 200, Fraction("1.25"), FAIL),
        ((100, 50), (100, 10), 0, (200, 60), 200, Fraction("0.30"), PASS),
        ((200, 160), (0, 0), 100, (100, 160), 100, Fraction("1.6"), FAIL),
    ],
    ids=["saline_arrival_quantity_pass_salt_fail", "fresh_arrival_endpoint_targets_pass", "evaporation_preserves_salt"],
)
def test_held_inventory(initial, arrival, evaporation, final, minimum, concentration, salinity):
    p = profile(minimum=minimum)
    imported = inventory_import(p, initial, final, arrival, evaporation)
    result = assess_receptor(p, imported.states)
    assert imported.accounting.local[0].water_m3 == 0
    assert imported.accounting.local[0].mass_kg == 0
    assert imported.balance.account.final == Inventory(Volume(final[0]), Mass(final[1]))
    assert imported.states[1].bounds.lower.value == concentration
    assert [t.supported.finding for t in result.tests] == [PASS, salinity]
    assert result.summary.finding == salinity
    assert result.summary.completeness is Completeness.COMPLETE
    assert all(t.target is not None and t.target.statistic is StateStatistic.INTERVAL_END for t in result.tests)
    assert result.profile.status is ProfileStatus.SCENARIO
    assert result.states[0].evidence.official_admissibility is OfficialAdmissibility.PENDING


@pytest.mark.parametrize(
    "volume,expected",
    [(100, FAIL), (200, UNKNOWN)],
    ids=["quantity_failure_with_unknown_salinity", "quantity_pass_unknown_salinity"],
)
def test_held_missing_salinity(volume, expected):
    p = profile()
    result = assess_receptor(p, (state(p, WATER, volume),))
    assert result.summary.finding is expected
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert result.tests[1].supported.finding is UNKNOWN


def test_transient_failure_hidden_by_final_pass():
    p = profile(3)
    states = tuple(
        s for i, salt in enumerate(["0.5", "1.2", "0.8"]) for s in (state(p, WATER, 200, i), state(p, SALT, salt, i))
    )
    result = assess_receptor(p, states)
    assert [
        t.supported.finding for t in result.tests if t.target is not None and t.target.identifier == "salinity"
    ] == [PASS, FAIL, PASS]
    assert result.summary.finding is FAIL
    assert result.interval_summary(p.intervals[-1]).finding is PASS


def test_dry_state_is_not_zero_concentration():
    p = profile(minimum=0)
    imported = inventory_import(p, (100, 10), (0, 10), evaporation=100)
    result = assess_receptor(p, imported.states)
    assert imported.balance.account.final.mass == Mass(10)
    assert imported.states[1].bounds is None
    assert imported.states[1].presence is Presence.DRY
    assert result.summary.finding is UNKNOWN


@pytest.mark.parametrize("compartment", [Compartment.INCOMING_WATER, Compartment.ROOT_ZONE, Compartment.GROUNDWATER])
def test_source_water_not_receptor_state(compartment):
    p = profile()
    different = replace(SALT, compartment=compartment)
    result = assess_receptor(p, (state(p, WATER, 200), state(p, different, "0.1")))
    assert result.summary.finding is UNKNOWN
    assert result.tests[1].state is None


def test_endpoint_only_cannot_certify_interval_maximum():
    p = profile(statistic=StateStatistic.WHOLE_INTERVAL)
    endpoint = state(p, SALT, "0.8", statistic=StateStatistic.INTERVAL_END)
    result = assess_receptor(p, (state(p, WATER, 200), endpoint))
    assert result.summary.finding is UNKNOWN
    endpoint_profile = replace(p, targets=tuple(replace(t, statistic=StateStatistic.INTERVAL_END) for t in p.targets))
    endpoint_result = assess_receptor(endpoint_profile, (state(endpoint_profile, WATER, 200), endpoint))
    assert endpoint_result.summary.finding is PASS
    assert result.summary.completeness is Completeness.INCOMPLETE


def test_unsupported_model_output_remains_exploratory():
    p = profile()
    states = tuple(
        replace(s, evidence=replace(s.evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED))
        for s in (state(p, WATER, 200), state(p, SALT, 2))
    )
    result = assess_receptor(p, states)
    assert result.numerical.finding is FAIL
    assert result.summary.finding is UNKNOWN
    assert result.summary.completeness is Completeness.INCOMPLETE


def test_missing_required_target_set():
    p = replace(profile(), targets=(), required_quantity=(), required_salinity=())
    result = assess_receptor(p, ())
    assert result.summary.finding is UNKNOWN
    assert len(result.tests) == 2


def duration_result(quantity, salinity, operator=DurationOperator.CUMULATIVE, comparison=Comparison.GE):
    p = profile(len(quantity), StateStatistic.WHOLE_INTERVAL)
    states = []
    for i, (q, s) in enumerate(zip(quantity, salinity, strict=True)):
        states.append(state(p, WATER, 200 if q else 0, i))
        if s is not None:
            states.append(state(p, SALT, 0 if s else 2, i))
    result = assess_receptor(p, tuple(states))
    criterion = DurationCriterion(
        "hydroperiod",
        Duration(2, "day"),
        comparison,
        operator,
        BoundaryHistory.WITHIN_PERIOD,
        evidence(p.context, "hydroperiod"),
    )
    return assess_joint_duration(result, criterion)


def test_separate_durations_do_not_supply_coincidence():
    result = duration_result([True, True, False, False], [False, False, True, True])
    assert result.lower == result.upper == Duration(0)
    assert result.check.finding is FAIL


def test_duration_bound_resolves_partial_coverage():
    result = duration_result([True] * 4, [True, True, None, None])
    assert (result.lower, result.upper) == (Duration(2, "day"), Duration(4, "day"))
    assert result.check.finding is PASS
    assert result.raw_coverage is Completeness.INCOMPLETE
    assert result.assessment.summary.finding is UNKNOWN


def test_consecutive_and_cumulative_duration_differ():
    cumulative = duration_result([True] * 4, [True, False, True, False])
    consecutive = duration_result([True] * 4, [True, False, True, False], DurationOperator.CONSECUTIVE)
    assert cumulative.lower == Duration(2, "day")
    assert consecutive.lower == consecutive.upper == Duration(1, "day")
    assert consecutive.check.finding is FAIL


def test_duration_strictness_unknown_bounds_and_missing_boundary_history():
    strict = duration_result([True] * 4, [True, True, None, None], comparison=Comparison.GT)
    assert strict.check.finding is UNKNOWN
    insufficient = duration_result([True] * 4, [False, False, False, None])
    assert insufficient.check.finding is FAIL
    assert insufficient.raw_coverage is Completeness.INCOMPLETE
    missing = assess_joint_duration(
        strict.assessment, replace(strict.criterion, boundary_history=BoundaryHistory.REQUIRED_MISSING)
    )
    assert missing.check.finding is UNKNOWN


def test_unknown_gaps_do_not_increase_consecutive_lower_bound_or_wrap():
    p = profile(4, StateStatistic.WHOLE_INTERVAL)
    p = replace(p, intervals=(p.intervals[0], p.intervals[-1]))
    states = tuple(state(p, domain, value, i) for i in range(2) for domain, value in ((WATER, 200), (SALT, 0)))
    assessment = assess_receptor(p, states)
    criterion = DurationCriterion(
        "duration",
        Duration(2, "day"),
        Comparison.GE,
        DurationOperator.CONSECUTIVE,
        BoundaryHistory.WITHIN_PERIOD,
        evidence(p.context, "duration"),
    )
    result = assess_joint_duration(assessment, criterion)
    assert result.lower == Duration(1, "day")
    assert result.upper == Duration(4, "day")
    assert result.check.finding is UNKNOWN


def test_point_samples_never_supply_duration():
    p = profile()
    assessment = assess_receptor(p, (state(p, WATER, 200), state(p, SALT, 0)))
    criterion = DurationCriterion(
        "duration",
        Duration(1, "day"),
        Comparison.GE,
        DurationOperator.CUMULATIVE,
        BoundaryHistory.WITHIN_PERIOD,
        evidence(p.context, "duration"),
    )
    result = assess_joint_duration(assessment, criterion)
    assert result.lower == Duration(0)
    assert result.upper == Duration(1, "day")
    assert result.check.finding is UNKNOWN


def test_bounds_range_and_signed_head_preserve_declared_domain():
    p = profile()
    head = ReceptorDomain(ReceptorVariable.GROUNDWATER_HEAD, Compartment.GROUNDWATER, "local datum-1")
    lower = replace(p.targets[0], limit=ReceptorValue(head, -2, "m"))
    upper = replace(
        lower,
        identifier="upper",
        limit=ReceptorValue(head, -1, "m"),
        operator=Comparison.LT,
        evidence=evidence(p.context, "upper"),
    )
    p = replace(p, targets=(lower, upper, p.targets[1]), required_quantity=("quantity", "upper"))
    sample = state(p, head, -1)
    result = assess_receptor(p, (sample, state(p, SALT, 0)))
    assert result.summary.finding is FAIL
    bounded = replace(
        sample,
        bounds=ReceptorBounds(
            ReceptorValue(head, -2, "m"), ReceptorValue(head, -1, "m"), "supplied supported interval", "survey"
        ),
    )
    result = assess_receptor(p, (bounded, state(p, SALT, 0)))
    assert result.summary.finding is UNKNOWN


@pytest.mark.parametrize(
    "presence", [Presence.MISSING, Presence.ABSENT, Presence.OUTSIDE_HORIZON, Presence.UNSUPPORTED]
)
def test_presence_and_use_restrictions_remain_explicit(presence):
    p = profile()
    result = assess_receptor(p, (state(p, WATER, 200), state(p, SALT, None, presence=presence)))
    assert result.summary.finding is UNKNOWN
    assert result.states[-1].presence is presence
    sample = state(p, SALT, 0)
    restricted = replace(
        sample,
        evidence=replace(
            sample.evidence, restrictions=(UseRestriction("outside rating range", ("receptor assessment",)),)
        ),
    )
    result = assess_receptor(p, (state(p, WATER, 200), restricted))
    assert result.numerical.finding is PASS
    assert result.summary.finding is UNKNOWN


@pytest.mark.parametrize("field,value", [("scenario", "other"), ("candidate", "other"), ("reference_member", "other")])
def test_incompatible_context_rejected(field, value):
    p = profile()
    changed = replace(p.context, **{field: value})
    sample = state(p, WATER, 200)
    ev = evidence(changed, changed.candidate)
    ev = replace(
        ev, provenance=replace(ev.provenance, scenario=changed.scenario, reference_member=changed.reference_member)
    )
    sample = replace(sample, context=changed, evidence=ev)
    with pytest.raises(ValueError, match="incompatible"):
        assess_receptor(p, (sample,))


def test_duplicate_and_temporal_domain_inputs_rejected():
    p = profile()
    sample = state(p, WATER, 200)
    with pytest.raises(ValueError, match="duplicate"):
        assess_receptor(p, (sample, sample))
    with pytest.raises(ValueError, match="overlapping"):
        replace(p, intervals=(p.intervals[0], p.intervals[0]))
    with pytest.raises(ValueError, match="outside"):
        replace(sample, interval=Interval(START - timedelta(days=1), START))
    with pytest.raises(ValueError, match="incompatible domain"):
        replace(sample, domain=SALT)


@pytest.mark.parametrize("value", [-1, "nan", "inf"])
def test_invalid_nonnegative_values(value):
    with pytest.raises(ValueError):
        ReceptorValue(WATER, value, "m3")
    with pytest.raises(ValueError):
        Duration(value)


def test_chemical_units_are_not_silently_converted():
    with pytest.raises(ValueError, match="domain/unit"):
        ReceptorValue(SALT, 1, "mg/l")
    with pytest.raises(ValueError, match="root-zone"):
        MixedCompartmentEvidence(
            replace(SALT, compartment=Compartment.ROOT_ZONE),
            evidence(context(), "schedule-A"),
            Remobilisation.NOT_REQUIRED,
        )


def test_balance_failure_invalidates_affected_support_without_erasing_residual():
    p = profile()
    imported = inventory_import(p, (100, 50), (200, 60), (100, 200))
    result = assess_receptor(p, imported.states)
    assert imported.accounting.local[0].mass_kg == -190
    assert result.tests[0].supported.finding is PASS
    assert result.tests[1].numerical.finding is PASS
    assert result.tests[1].supported.finding is UNKNOWN
    assert result.summary.finding is UNKNOWN


def test_no_implicit_remobilisation_on_refill():
    p = profile(minimum=100)
    imported = inventory_import(p, (0, 10), (100, 10), (100, 0))
    assert imported.states[1].presence is Presence.UNSUPPORTED
    assert "remobilisation" in " ".join(imported.states[1].reasons)
    assert imported.balance.account.final.mass == Mass(10)
    ev = evidence(p.context, p.context.candidate)
    accepted = replace(imported.representation, remobilisation=Remobilisation.SUPPORTED, remobilisation_evidence=ev)
    result = import_receptor_inventory(imported.balance, p.context, WATER, ev, accepted)
    assert assess_receptor(p, result.states).summary.finding is PASS


def test_duplicate_carrier_load_and_account_mismatch_rejected():
    p = profile()
    imported = inventory_import(p, (100, 50), (200, 250), (100, 200))
    balance = imported.balance
    with pytest.raises(ValueError, match="duplicate"):
        replace(balance, transfers=balance.transfers * 2)
    process = AccountProcess("extra-load", Fraction(0), Fraction(200), "the same arrival salt")
    with pytest.raises(ValueError, match="counted twice"):
        replace(
            balance,
            account=replace(balance.account, processes=(*balance.account.processes, process)),
            counted_loads=(*balance.counted_loads, CountedLoad("arrival-salt", "extra-load")),
        )
    with pytest.raises(ValueError, match="identity"):
        replace(balance, counted_loads=())
    ev = evidence(p.context, p.context.candidate)
    with pytest.raises(ValueError, match="incompatible"):
        import_receptor_inventory(
            replace(
                balance,
                account=replace(balance.account, location="other"),
                transfers=(replace(balance.transfers[0], destination="other"),),
            ),
            p.context,
            WATER,
            ev,
            imported.representation,
        )


def test_duration_known_failure_keeps_missing_component_raw_coverage():
    result = duration_result([False] * 4, [None] * 4)
    assert result.lower == result.upper == Duration(0)
    assert result.check.finding is FAIL
    assert result.raw_coverage is Completeness.INCOMPLETE


def test_supported_root_zone_import_and_target_evidence_restriction():
    p = profile()
    root_zone = replace(SALT, compartment=Compartment.ROOT_ZONE, basis="supported root-zone relation study R1")
    p = replace(p, targets=(p.targets[0], replace(p.targets[1], limit=ReceptorValue(root_zone, 1, "kg/m3"))))
    samples = (state(p, WATER, 200), state(p, root_zone, "0.8"))
    assert assess_receptor(p, samples).summary.finding is PASS
    target = replace(
        p.targets[1],
        evidence=replace(
            p.targets[1].evidence,
            restrictions=(UseRestriction("tolerance not accepted for sizing", ("receptor assessment",)),),
        ),
    )
    restricted = replace(p, targets=(p.targets[0], target))
    result = assess_receptor(restricted, samples)
    assert result.numerical.finding is PASS
    assert result.summary.finding is UNKNOWN
    assert "tolerance not accepted" in " ".join(result.tests[-1].supported.reasons)


def test_exact_evidence_scope_and_warmup_restrictions():
    p = profile()
    sample = state(p, SALT, "0.2")
    foreign_scope = replace(
        sample, evidence=replace(sample.evidence, scope=replace(sample.evidence.scope, product="other-schedule"))
    )
    result = assess_receptor(p, (state(p, WATER, 200), foreign_scope))
    assert result.summary.finding is UNKNOWN
    excluded = replace(
        sample,
        evidence=replace(
            sample.evidence, provenance=replace(sample.evidence.provenance, excluded_warmup=(p.context.period,))
        ),
    )
    assert assess_receptor(p, (state(p, WATER, 200), excluded)).summary.finding is UNKNOWN


def test_receptor_profile_immutable_scenario_isolation():
    p = profile()
    samples = (state(p, WATER, 200), state(p, SALT, "1.25"))
    before = assess_receptor(p, samples)
    relaxed = replace(
        p, version="2", targets=(p.targets[0], replace(p.targets[1], limit=ReceptorValue(SALT, 2, "kg/m3")))
    )
    assert assess_receptor(relaxed, samples).summary.finding is PASS
    assert before.summary.finding is FAIL
    assert before.profile.targets[1].limit.value == 1


def test_inventory_physical_warmup_cannot_be_erased_by_assessment_evidence():
    p = profile()
    imported = inventory_import(p, (100, 50), (200, 60), (100, 10))
    balance = replace(
        imported.balance,
        account=replace(
            imported.balance.account, provenance=replace(provenance(), excluded_warmup=(p.context.period,))
        ),
    )
    ev = evidence(p.context, p.context.candidate)
    result = import_receptor_inventory(balance, p.context, WATER, ev, imported.representation)
    assert assess_receptor(p, result.states).summary.finding is UNKNOWN


def test_public_receptor_example():
    from examples.receptor_assessment import assess_supplied_inventory

    result = assess_supplied_inventory()
    assert result.summary.finding is FAIL
    assert result.summary.completeness is Completeness.COMPLETE
    assert [test.supported.finding for test in result.tests] == [PASS, FAIL]


def test_receptor_example_never_imports_simulator(monkeypatch, capsys):
    import builtins
    import runpy

    original = builtins.__import__

    def without_simulator(name, *args, **kwargs):
        if name.split(".")[0] in ("taqsim", "incidence"):
            raise AssertionError("receptor assessment must not import a simulator")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_simulator)
    runpy.run_path("examples/receptor_assessment.py", run_name="__main__")
    assert "joint: fail; coverage: complete" in capsys.readouterr().out
