from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction

import pytest

from fishy.evidence import CorrectionState, ProductionMethod, Provenance
from fishy.load_accounts import (
    AccountTransfer,
    ControlState,
    Inventory,
    LoadAccount,
    Mass,
    ResidualSourceKind,
    SourceControlEvidence,
    assess_load_accounts,
)
from fishy.mixing import BoundarySupport, FixedBoundary, FlowConstraints, LoadRate, MixingConstituent
from fishy.quality import ChemicalBehavior, ChemicalIdentity, Comparison, QualityTarget, QualityValue
from fishy.quality_activation import (
    ActivationCondition,
    ActivationConditions,
    ActivationMode,
    BackgroundAccountMapping,
    ComponentStatus,
    EvidenceState,
    QualityActivation,
    QualityRoute,
    apply_quality_component,
)
from fishy.quantities import Flow, Volume
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

PERIOD = Interval(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC))
LOCATION = Location(Reach("r", "v1", WaterBody("river", "v1")), CalculationSection("section", "v1"), "v1")
CHEMICAL = ChemicalIdentity("salt", "dissolved salt", "salt mass", "dissolved", ChemicalBehavior.CONSERVATIVE)
PROVENANCE = Provenance(
    "synthetic inventory", "synthetic", None, "v1", "v1", "v1", ProductionMethod.ILLUSTRATIVE, CorrectionState.ORIGINAL
)
HELD = ActivationCondition(EvidenceState.HELD, "supplied evidence")
MISSING = ActivationCondition(EvidenceState.MISSING, "not held")
CONDITIONS = ActivationConditions(HELD, HELD, HELD, HELD, HELD)


def inputs():
    boundary = FixedBoundary(
        LOCATION,
        PERIOD,
        Flow(10),
        (MixingConstituent(CHEMICAL, LoadRate(8), QualityValue("0.1", "kg/m3")),),
        BoundarySupport("fixed complete mixing, carriers counted once"),
        PROVENANCE,
    )
    targets = (QualityTarget("upper", CHEMICAL, Comparison.LE, QualityValue("0.5", "kg/m3"), "interval", "synthetic"),)
    activation = QualityActivation(
        "synthetic", QualityRoute.REGIME, ActivationMode.REPORT, CONDITIONS, "explicit report decision"
    )
    controls = SourceControlEvidence(
        "synthetic",
        "section",
        PERIOD,
        ControlState.EXHAUSTED,
        (("return salinity", ResidualSourceKind.UNCONTROLLABLE_DIFFUSE),),
        "held source inventory",
    )
    inv = Inventory(Volume(0), Mass(0))
    account = LoadAccount(
        "section",
        ChemicalIdentity("salt", "dissolved salt", "salt mass", "dissolved", ChemicalBehavior.CONSERVATIVE),
        PERIOD,
        "synthetic",
        inv,
        inv,
        PROVENANCE,
    )
    background = Inventory(Volume(10 * PERIOD.seconds), Mass(8 * PERIOD.seconds))
    accounts = (
        assess_load_accounts(
            (account,),
            (
                AccountTransfer("background", None, "section", background),
                AccountTransfer("out", "section", None, background),
            ),
        ),
    )
    return {
        "base": Flow(10),
        "boundary": boundary,
        "targets": targets,
        "activation": activation,
        "source_control": controls,
        "accounts": accounts,
        "background_mapping": BackgroundAccountMapping(("background",), "identified background inventory", LOCATION),
    }


def match_background_accounts(args):
    boundary = args["boundary"]
    background = Inventory(
        Volume(boundary.background.value * PERIOD.seconds),
        Mass(boundary.constituents[0].background_load.value * PERIOD.seconds),
    )
    args["accounts"] = (
        assess_load_accounts(
            args["accounts"][0].accounts,
            (
                AccountTransfer("background", None, "section", background),
                AccountTransfer("out", "section", None, background),
            ),
        ),
    )


def test_feasible_report_retains_base_quality_and_combined():
    result = apply_quality_component(**inputs())
    assert result.base == Flow(10)
    assert result.quality.quality_total == Flow("17.5")
    assert result.combined == result.requirement == Flow("17.5")
    assert result.floor is None
    assert result.status is ComponentStatus.ACTIVE


@pytest.mark.parametrize(
    "condition",
    [
        "reach_season_screen",
        "fisheries_targets",
        "approved_harmfulness_grouping",
        "basin_salt_budget",
        "ncecc_approved_transport_model",
    ],
)
def test_each_of_five_conditions_is_necessary(condition):
    args = inputs()
    args["activation"] = replace(args["activation"], conditions=replace(CONDITIONS, **{condition: MISSING}))
    result = apply_quality_component(**args)
    assert result.status is ComponentStatus.ADVISORY
    assert result.combined == Flow(10)
    assert condition in result.reasons
    assert result.quality.quality_total == Flow("17.5")


@pytest.mark.parametrize("route", list(QualityRoute))
def test_hypothetical_activation_and_floor_only(route):
    args = inputs()
    args["activation"] = replace(
        args["activation"],
        route=route,
        mode=ActivationMode.HYPOTHETICAL,
        conditions=ActivationConditions(MISSING, MISSING, MISSING, MISSING, MISSING),
    )
    result = apply_quality_component(**args)
    assert result.status is ComponentStatus.HYPOTHETICAL
    assert result.activation.scenario == "synthetic"
    assert result.combined == Flow("17.5")
    if route is QualityRoute.FLOOR_ONLY:
        assert result.requirement is None
        assert result.floor == Flow("17.5")
    assert not hasattr(result, "obligation")
    assert not hasattr(result, "delivery_verdict")


def test_inactive_quality_fixture_retains_base():
    args = inputs()
    args["activation"] = replace(args["activation"], mode=ActivationMode.ADVISORY)
    result = apply_quality_component(**args)
    assert result.requirement == Flow(10)
    assert result.status is ComponentStatus.ADVISORY


def test_dirty_source_ecological_uplift_cannot_bypass_original_upper_test():
    args = inputs()
    args["boundary"] = replace(
        args["boundary"], constituents=(MixingConstituent(CHEMICAL, LoadRate(1), QualityValue(1, "kg/m3")),)
    )
    match_background_accounts(args)
    args["base"] = Flow(20)
    result = apply_quality_component(**args)
    assert result.status is ComponentStatus.INFEASIBLE
    assert result.combined == Flow(20)
    assert result.quality.combined_interval.empty


def test_capacity_and_final_supplied_candidate_rechecks():
    args = inputs()
    result = apply_quality_component(**args, bounds=FlowConstraints(LOCATION, PERIOD, capacity=Flow(5)))
    assert result.status is ComponentStatus.INFEASIBLE
    result = apply_quality_component(**args, candidate_arrival=Flow(1))
    assert result.status is ComponentStatus.INFEASIBLE
    assert result.combined == Flow(10)


def test_open_endpoint_requires_actual_candidate_not_epsilon():
    args = inputs()
    args["targets"] = (replace(args["targets"][0], operator=Comparison.LT),)
    result = apply_quality_component(**args)
    assert result.status is ComponentStatus.UNSIZED
    assert result.quality.quality_total is None
    assert apply_quality_component(**args, candidate_arrival=Flow("7.5")).status is ComponentStatus.INFEASIBLE
    assert apply_quality_component(**args, candidate_arrival=Flow(8)).combined == Flow(18)


def test_source_controls_gate_actual_sizing_before_any_calculation(monkeypatch):
    import fishy.quality_activation as module

    args = inputs()
    args["source_control"] = replace(args["source_control"], discharge_control=ControlState.OUTSTANDING)

    def forbidden(*args):
        pytest.fail("solver entered before discharge control")

    monkeypatch.setattr(module, "solve_mixing", forbidden)
    with pytest.raises(ValueError, match="exhausted"):
        apply_quality_component(**args)


def test_conservation_failure_invalidates_actual_assessment():
    args = inputs()
    account = args["accounts"][0].accounts[0]
    bad = replace(account, final=Inventory(Volume(0), Mass(1)), precision_disclosures=("rounding disclosed",))
    args["accounts"] = (assess_load_accounts((bad,), ()),)
    with pytest.raises(ValueError, match="invalidates"):
        apply_quality_component(**args)


def test_scenario_and_boundary_isolation():
    args = inputs()
    args["activation"] = replace(args["activation"], scenario="another")
    with pytest.raises(ValueError, match="scenario"):
        apply_quality_component(**args)
    with pytest.raises(ValueError, match="disagree"):
        apply_quality_component(**inputs(), bounds=FlowConstraints(LOCATION, PERIOD, ecological_total=Flow(5)))


@pytest.mark.parametrize("kind", ["source_water", "missing_evidence"])
def test_all_five_cannot_activate_impossible_or_incomplete_screens(kind):
    from fishy.quality import UnresolvedTarget

    args = inputs()
    if kind == "source_water":
        args["boundary"] = replace(
            args["boundary"], constituents=(MixingConstituent(CHEMICAL, LoadRate(8), QualityValue("0.5", "kg/m3")),)
        )
    else:
        args["targets"] += (UnresolvedTarget("missing", "missing member", "source"),)
    match_background_accounts(args)
    result = apply_quality_component(**args)
    assert result.status is ComponentStatus.INFEASIBLE
    assert result.combined == result.base
    assert result.reasons


def test_chemical_fraction_accounts_cannot_substitute():
    args = inputs()
    original = args["accounts"][0].accounts[0]
    wrong = replace(original, constituent=replace(CHEMICAL, fraction="total"))
    args["accounts"] = (assess_load_accounts((wrong,), ()),)
    with pytest.raises(ValueError, match="fraction"):
        apply_quality_component(**args)


def test_dry_quality_without_standalone_minimum_can_bind_positive_base():
    args = inputs()
    args["boundary"] = replace(
        args["boundary"],
        background=Flow(0),
        constituents=(MixingConstituent(CHEMICAL, LoadRate(0), QualityValue("0.1", "kg/m3")),),
    )
    match_background_accounts(args)
    args["base"] = Flow(2)
    result = apply_quality_component(**args)
    assert result.quality.quality_total is None
    assert result.combined == Flow(2)
    assert result.status is ComponentStatus.ACTIVE


def test_boundary_provenance_scenario_cannot_be_relabelled():
    args = inputs()
    args["boundary"] = replace(args["boundary"], provenance=replace(PROVENANCE, scenario="another"))
    with pytest.raises(ValueError, match="provenance"):
        apply_quality_component(**args)


def test_empty_accounts_cannot_certify_wet_loaded_boundary():
    # Real path regression: the former implementation activated unrelated zero accounts.
    args = inputs()
    args["accounts"] = (assess_load_accounts(args["accounts"][0].accounts, ()),)
    with pytest.raises(ValueError, match="background"):
        apply_quality_component(**args)


@pytest.mark.parametrize(
    "field,value", [("data_version", "other"), ("configuration_version", "other"), ("reference_member", "other")]
)
def test_account_snapshot_cannot_certify_unrelated_boundary(field, value):
    args = inputs()
    ledger = args["accounts"][0]
    changed = replace(ledger.accounts[0], provenance=replace(PROVENANCE, **{field: value}))
    args["accounts"] = (assess_load_accounts((changed,), ledger.transfers),)
    with pytest.raises(ValueError, match="snapshot"):
        apply_quality_component(**args)


@pytest.mark.parametrize("water,mass", [(9, 8), (10, 7)])
def test_background_quantity_mapping_must_match_exactly(water, mass):
    args = inputs()
    ledger = args["accounts"][0]
    amount = Inventory(Volume(water * PERIOD.seconds), Mass(Fraction(mass) * PERIOD.seconds))
    args["accounts"] = (
        assess_load_accounts(
            ledger.accounts,
            (
                AccountTransfer("background", None, "section", amount),
                AccountTransfer("out", "section", None, amount),
            ),
        ),
    )
    with pytest.raises(ValueError, match="background"):
        apply_quality_component(**args)


def with_prior_arrival(args, water, mass):
    ledger = args["accounts"][0]
    arrival = Inventory(Volume(water * PERIOD.seconds), Mass(Fraction(mass) * PERIOD.seconds))
    args["accounts"] = (
        assess_load_accounts(
            ledger.accounts,
            ledger.transfers
            + (
                AccountTransfer("arrival", None, "section", arrival),
                AccountTransfer("arrival-out", "section", None, arrival),
            ),
        ),
    )


def test_all_incoming_carriers_classified_and_prior_arrival_may_differ_from_candidate():
    args = inputs()
    with_prior_arrival(args, 2, "0.2")
    with pytest.raises(ValueError, match="classified"):
        apply_quality_component(**args)
    args["background_mapping"] = BackgroundAccountMapping(
        ("background",), "explicit background/arrival mapping", LOCATION, ("arrival",)
    )
    result = apply_quality_component(**args)
    assert result.status is ComponentStatus.ACTIVE
    assert result.quality.candidate is not None
    assert result.quality.candidate.arrival == Flow("7.5")
    assert result.background_mapping.arrival_transfer_ids == ("arrival",)


@pytest.mark.parametrize("water,mass", [(2, 1), (0, 1)])
def test_excluded_arrival_has_fixed_source_composition(water, mass):
    args = inputs()
    with_prior_arrival(args, water, mass)
    args["background_mapping"] = BackgroundAccountMapping(("background",), "explicit mapping", LOCATION, ("arrival",))
    with pytest.raises(ValueError, match="source composition"):
        apply_quality_component(**args)


def test_mapping_rejects_duplicate_and_overlapping_ids():
    with pytest.raises(ValueError, match="duplicate"):
        BackgroundAccountMapping(("background", "background"), "mapping", LOCATION)
    with pytest.raises(ValueError, match="overlapping"):
        BackgroundAccountMapping(("background",), "mapping", LOCATION, ("background",))


def test_shared_water_carrier_cannot_differ_across_constituent_ledgers():
    args = inputs()
    chemical = replace(CHEMICAL, identifier="other")
    args["boundary"] = replace(
        args["boundary"],
        constituents=args["boundary"].constituents
        + (MixingConstituent(chemical, LoadRate(8), QualityValue("0.1", "kg/m3")),),
    )
    ledgers = []
    for constituent, first_water in ((CHEMICAL, 4), (chemical, 5)):
        original = replace(args["accounts"][0].accounts[0], constituent=constituent)
        first = Inventory(Volume(first_water * PERIOD.seconds), Mass(4 * PERIOD.seconds))
        second = Inventory(Volume((10 - first_water) * PERIOD.seconds), Mass(4 * PERIOD.seconds))
        total = Inventory(Volume(10 * PERIOD.seconds), Mass(8 * PERIOD.seconds))
        ledgers.append(
            assess_load_accounts(
                (original,),
                (
                    AccountTransfer("first", None, "section", first),
                    AccountTransfer("second", None, "section", second),
                    AccountTransfer("out", "section", None, total),
                ),
            )
        )
    args["accounts"] = tuple(ledgers)
    args["background_mapping"] = BackgroundAccountMapping(("first", "second"), "physical carriers", LOCATION)
    with pytest.raises(ValueError, match="shared physical water carrier"):
        apply_quality_component(**args)


def test_explicit_empty_mapping_only_for_genuinely_dry_load_free_background():
    args = inputs()
    args["boundary"] = replace(
        args["boundary"],
        background=Flow(0),
        constituents=(MixingConstituent(CHEMICAL, LoadRate(0), QualityValue("0.1", "kg/m3")),),
    )
    args["accounts"] = (assess_load_accounts(args["accounts"][0].accounts, ()),)
    args["background_mapping"] = BackgroundAccountMapping((), "no background carriers or loads", LOCATION)
    assert apply_quality_component(**args).status is ComponentStatus.ACTIVE


def test_account_mapping_location_version_cannot_certify_changed_boundary():
    args = inputs()
    args["boundary"] = replace(args["boundary"], location=replace(LOCATION, mapping_version="another"))
    with pytest.raises(ValueError, match="prepared location"):
        apply_quality_component(**args)


def test_replaced_ledger_cannot_activate_with_stale_cached_residuals():
    args = inputs()
    ledger = args["accounts"][0]
    with pytest.raises(ValueError, match="residual|derived|conservation"):
        forged = replace(ledger, transfers=ledger.transfers[:1])
        args["accounts"] = (forged,)
        apply_quality_component(**args)


def test_excluded_account_warmup_cannot_activate_quality():
    args = inputs()
    ledger = args["accounts"][0]
    excluded = replace(ledger.accounts[0], provenance=replace(PROVENANCE, excluded_warmup=(PERIOD,)))
    args["accounts"] = (assess_load_accounts((excluded,), ledger.transfers),)
    with pytest.raises(ValueError, match="warm-up"):
        apply_quality_component(**args)
