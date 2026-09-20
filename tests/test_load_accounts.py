from datetime import UTC, datetime
from fractions import Fraction

import pytest

from fishy.evidence import CorrectionState, ProductionMethod, Provenance
from fishy.load_accounts import (
    AccountingUncertainty,
    AccountProcess,
    AccountTransfer,
    ConservationState,
    ControlState,
    Inventory,
    LoadAccount,
    Mass,
    ResidualSourceKind,
    SourceControlEvidence,
    SourceTag,
    assess_load_accounts,
)
from fishy.quality import ChemicalBehavior, ChemicalIdentity
from fishy.quantities import Volume
from fishy.time import Interval

PERIOD = Interval(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC))
PROVENANCE = Provenance(
    "inventory", "synthetic", None, "v1", "v1", "v1", ProductionMethod.ILLUSTRATIVE, CorrectionState.ORIGINAL
)
SALT = ChemicalIdentity("salt", "dissolved salt", "salt mass", "dissolved", ChemicalBehavior.CONSERVATIVE)


def inventory(water, mass):
    return Inventory(Volume(water), Mass(mass))


def account(location, initial, final, **kwargs):
    return LoadAccount(
        location, SALT, PERIOD, "synthetic", inventory(*initial), inventory(*final), PROVENANCE, **kwargs
    )


def test_local_and_basin_internal_cancellation_and_source_tags():
    accounts = (account("upstream", (0, 0), (0, 0)), account("downstream", (0, 0), (0, 0)))
    tag = SourceTag("background", "boundary", PERIOD, Mass(8), "documented mixing")
    transfers = (
        AccountTransfer("in", None, "upstream", inventory(15, "8.75"), (tag,)),
        AccountTransfer("internal", "upstream", "downstream", inventory(15, "8.75")),
        AccountTransfer("out", "downstream", None, inventory(15, "8.75")),
    )
    result = assess_load_accounts(accounts, transfers)
    assert result.state is ConservationState.VALID
    assert result.basin.mass_kg == 0
    assert result.internal_transfer_ids == ("internal",)
    assert result.transfers[0].unallocated_mass == Mass("0.75")
    assert result.transfers[0].source_tags == (tag,)
    result.require_valid()


def test_conservation_fixture_interval_load_is_not_multiplied_twice():
    # Original conservation fixture: 8 + 7.5 * 0.1 = 8.75 kg/s.
    seconds = PERIOD.seconds
    total = inventory(Fraction(35, 2) * seconds, Fraction(35, 4) * seconds)
    result = assess_load_accounts(
        (account("section", (0, 0), (0, 0)),),
        (
            AccountTransfer("in", None, "section", total),
            AccountTransfer("out", "section", None, total),
        ),
    )
    assert result.basin.mass_kg == 0
    assert result.basin.water_m3 == 0


def test_local_failure_does_not_cancel_into_basin_pass_or_precision_warning():
    result = assess_load_accounts(
        (
            account("a", (1, 1), (1, 2), precision_disclosures=("concentration display rounded",)),
            account("b", (1, 2), (1, 1)),
        ),
        (),
    )
    assert result.basin.state is ConservationState.VALID
    assert result.state is ConservationState.INVALID
    assert result.local[0].mass_kg == 1
    assert result.accounts[0].precision_disclosures
    with pytest.raises(ValueError, match="invalidates"):
        result.require_valid()


def test_explicit_evaporation_retains_salt_and_process_is_not_inferred():
    evaporation = AccountTransfer("evaporation", "store", None, inventory(2, 0))
    result = assess_load_accounts((account("store", (10, 5), (8, 5)),), (evaporation,))
    assert result.state is ConservationState.VALID
    bad = assess_load_accounts((account("store", (10, 5), (8, 4)),), (evaporation,))
    assert bad.local[0].mass_kg == -1
    assert bad.state is ConservationState.INVALID
    treatment = AccountProcess("treatment", Fraction(0), Fraction(-1), "supported removal to treatment account")
    explicit = assess_load_accounts((account("store", (10, 5), (8, 4), processes=(treatment,)),), (evaporation,))
    assert explicit.state is ConservationState.VALID


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), True])
def test_mass_rejects_invalid_physical_values(bad):
    with pytest.raises((ValueError, TypeError)):
        Mass(bad)


def test_units_and_basis_and_boundary_refusals():
    assert Mass(1000, "g") == Mass(1)
    with pytest.raises(ValueError):
        Mass(1, "kg/s")
    with pytest.raises(ValueError):
        assess_load_accounts((), ())
    with pytest.raises(ValueError, match="endpoint"):
        assess_load_accounts((account("a", (0, 0), (0, 0)),), (AccountTransfer("missing", "a", "b", inventory(0, 0)),))
    with pytest.raises(ValueError, match="duplicate"):
        assess_load_accounts((account("a", (0, 0), (0, 0)),) * 2, ())


def test_dry_inventory_is_retained_and_independent_constituents_not_combined():
    assert assess_load_accounts((account("dry", (0, 5), (0, 5)),), ()).state is ConservationState.VALID
    other = LoadAccount(
        "other",
        ChemicalIdentity("salt", "other", "other", "dissolved", ChemicalBehavior.CONSERVATIVE),
        PERIOD,
        "synthetic",
        inventory(0, 0),
        inventory(0, 0),
        PROVENANCE,
    )
    with pytest.raises(ValueError, match="chemical basis"):
        assess_load_accounts((account("dry", (0, 5), (0, 5)), other), ())


@pytest.mark.parametrize("state", list(ControlState))
@pytest.mark.parametrize("kind", list(ResidualSourceKind))
def test_prior_controls_and_diffuse_only(state, kind):
    evidence = SourceControlEvidence("synthetic", "section", PERIOD, state, (("remaining", kind),), "source inventory")
    if state is ControlState.EXHAUSTED and kind is ResidualSourceKind.UNCONTROLLABLE_DIFFUSE:
        evidence.require_residual_dilution()
    else:
        with pytest.raises(ValueError):
            evidence.require_residual_dilution()


def test_storage_separate_load_and_export_enter_once():
    result = assess_load_accounts(
        (account("store", (10, 5), (12, 7)),),
        (
            AccountTransfer("water", None, "store", inventory(4, 2)),
            AccountTransfer("separate", None, "store", inventory(0, 1)),
            AccountTransfer("withdrawal", "store", None, inventory(2, 1)),
        ),
    )
    assert result.state is ConservationState.VALID
    transfer = AccountTransfer("water", None, "store", inventory(4, 2))
    with pytest.raises(ValueError, match="duplicate physical"):
        assess_load_accounts((account("store", (0, 0), (8, 4)),), (transfer, transfer))


def test_unallocated_mass_is_not_a_conservation_residual():
    transfer = AccountTransfer("natural", None, "store", inventory(1, 2))
    result = assess_load_accounts((account("store", (0, 0), (1, 2)),), (transfer,))
    assert result.basin.mass_kg == 0
    assert result.transfers[0].unallocated_mass == Mass(2)


def test_source_tags_do_not_silently_overallocate_or_change_interval():
    tag = SourceTag("source", "boundary", PERIOD, Mass(3), "evidence")
    with pytest.raises(ValueError, match="exceeds"):
        AccountTransfer("in", None, "store", inventory(1, 2), (tag,))


def test_supplied_uncertainty_survives_without_waiving_exact_residual():
    uncertainty = AccountingUncertainty(
        "laboratory interval 1.8 to 2.2 kg; water model bounds supplied separately", "laboratory record v2"
    )
    amount = Inventory(Volume(1), Mass(2), uncertainty)
    tag = SourceTag("source", "boundary", PERIOD, Mass(2), "routing record", uncertainty)
    result = assess_load_accounts(
        (account("store", (0, 0), (1, 1)),), (AccountTransfer("in", None, "store", amount, (tag,)),)
    )
    assert result.transfers[0].amount.uncertainty == uncertainty
    assert result.transfers[0].source_tags[0].uncertainty == uncertainty
    assert result.local[0].mass_kg == -1
    assert result.uncertainty_limitations == (
        "store: initial inventory uncertainty not supplied",
        "store: final inventory uncertainty not supplied",
    )
    with pytest.raises(ValueError, match="invalidates"):
        result.require_valid()
