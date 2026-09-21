"""import_receptor_inventory : ReceptorBalance × MixedCompartmentEvidence → ReceptorStates (pure).

Check supplied physical inventories. Closure is not a native transport solver or
scientific suitability. The full account, carrier identities and residuals survive.
"""

from dataclasses import dataclass
from enum import StrEnum

from fishy.evidence import CheckFinding, EvidenceFindings, _text, permitted_use, warmup_restrictions
from fishy.flows import Presence
from fishy.load_accounts import AccountAssessment, AccountTransfer, LoadAccount, assess_load_accounts
from fishy.quality import ChemicalBehavior
from fishy.receptor_states import (
    Compartment,
    ReceptorBounds,
    ReceptorContext,
    ReceptorDomain,
    ReceptorState,
    ReceptorValue,
    ReceptorVariable,
    StateStatistic,
)


@dataclass(frozen=True)
class CountedLoad:
    """Identify an indivisible physical load already represented in one carrier/process."""

    load: str
    account_entry: str

    def __post_init__(self) -> None:
        _text(self.load, "physical load")
        _text(self.account_entry, "carrier/process entry")


@dataclass(frozen=True)
class ReceptorBalance:
    account: LoadAccount
    transfers: tuple[AccountTransfer, ...]
    counted_loads: tuple[CountedLoad, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.account, LoadAccount):
            raise TypeError("receptor balance requires LoadAccount")
        if not isinstance(self.transfers, tuple) or any(not isinstance(t, AccountTransfer) for t in self.transfers):
            raise TypeError("immutable AccountTransfer tuple required")
        if not isinstance(self.counted_loads, tuple) or any(
            not isinstance(load, CountedLoad) for load in self.counted_loads
        ):
            raise TypeError("immutable CountedLoad tuple required")
        entries = [t.identifier for t in self.transfers] + [p.identifier for p in self.account.processes]
        if len(set(entries)) != len(entries):
            raise ValueError("duplicate carrier/process entry")
        loads = [load.load for load in self.counted_loads]
        if len(set(loads)) != len(loads):
            raise ValueError("physical load counted twice in carrier/separate load")
        if any(load.account_entry not in entries for load in self.counted_loads):
            raise ValueError("load references unknown accounting entry")
        mass_entries = {t.identifier for t in self.transfers if t.amount.mass.value} | {
            p.identifier for p in self.account.processes if p.mass_change_kg
        }
        if mass_entries - {load.account_entry for load in self.counted_loads}:
            raise ValueError("every nonzero mass entry requires physical load identity")
        # Validate boundaries and duplicate carriers without concealing residuals.
        assess_load_accounts((self.account,), self.transfers)


class Remobilisation(StrEnum):
    NOT_REQUIRED = "not_required"
    SUPPORTED = "supported"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class MixedCompartmentEvidence:
    domain: ReceptorDomain
    evidence: EvidenceFindings
    remobilisation: Remobilisation
    remobilisation_evidence: EvidenceFindings | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.domain, ReceptorDomain) or self.domain.variable is not ReceptorVariable.SALINITY:
            raise ValueError("mixed compartment requires explicit salinity domain")
        if self.domain.compartment is not Compartment.RESIDENT_WATER:
            raise ValueError("bulk mixing cannot provide root-zone, groundwater or incoming-water state")
        if not isinstance(self.evidence, EvidenceFindings) or not isinstance(self.remobilisation, Remobilisation):
            raise TypeError("mixing evidence and remobilisation meaning required")
        if self.remobilisation is Remobilisation.SUPPORTED:
            if not isinstance(self.remobilisation_evidence, EvidenceFindings):
                raise ValueError("remobilisation needs separate attributable evidence")
        elif self.remobilisation_evidence is not None:
            raise ValueError("remobilisation evidence conflicts with declared status")


@dataclass(frozen=True)
class InventoryStateImport:
    balance: ReceptorBalance
    accounting: AccountAssessment
    representation: MixedCompartmentEvidence
    states: tuple[ReceptorState, ...]


def import_receptor_inventory(
    balance: ReceptorBalance,
    context: ReceptorContext,
    quantity_domain: ReceptorDomain,
    state_evidence: EvidenceFindings,
    representation: MixedCompartmentEvidence,
) -> InventoryStateImport:
    """Import an endpoint inventory, preserving dry mass and unsupported rewetting.

    The caller supplies the final inventory independently of the balance identities.
    This operation checks that inventory; it does not predict a mixed trajectory.
    """
    account = balance.account
    if (
        (account.location, account.scenario, account.provenance.reference_member)
        != (context.location.reach.identifier, context.scenario, context.reference_member)
        or account.interval.start < context.period.start
        or account.interval.end > context.period.end
    ):
        raise ValueError("account has incompatible receptor/scenario/member/time")
    if (
        quantity_domain.variable is not ReceptorVariable.STORAGE
        or quantity_domain.compartment is not Compartment.RESIDENT_WATER
    ):
        raise ValueError("inventory water is resident storage, not level, area or root-zone state")
    if representation.domain.chemical != account.constituent:
        raise ValueError("inventory chemical identity/reporting basis mismatch")
    for evidence in (state_evidence, representation.evidence, representation.remobilisation_evidence):
        if evidence is not None and (evidence.provenance.scenario, evidence.provenance.reference_member) != (
            context.scenario,
            context.reference_member,
        ):
            raise ValueError("import evidence has incompatible scenario/member")
    accounting = assess_load_accounts((account,), balance.transfers)
    residual = accounting.local[0]
    sources = (
        account.provenance.source,
        *account.provenance.dependencies,
        *(t.identifier for t in balance.transfers),
        *(p.identifier for p in account.processes),
        *account.precision_disclosures,
    )
    volume = ReceptorValue(quantity_domain, account.final.water.value, "m3")
    physical_restrictions = warmup_restrictions(account.provenance, account.interval)
    water_reason = (
        ("water conservation residual invalidates storage support",) if residual.water_m3 else ()
    ) + physical_restrictions
    quantity = ReceptorState(
        context,
        account.interval,
        quantity_domain,
        StateStatistic.INTERVAL_END,
        ReceptorBounds(
            volume, volume, "exact supplied inventory, not scientific uncertainty", account.provenance.source
        ),
        Presence.UNSUPPORTED if water_reason else Presence.PRESENT,
        state_evidence,
        water_reason,
        sources,
    )
    reasons = list(physical_restrictions + warmup_restrictions(representation.evidence.provenance, account.interval))
    permission = permitted_use(representation.evidence, context.evidence_scope(context.candidate, account.interval))
    if permission.finding is not CheckFinding.PASS:
        reasons.extend(("representative mixed compartment unsupported", *permission.reasons))
    if residual.water_m3 or residual.mass_kg:
        reasons.append("water/salt conservation residual invalidates concentration support")
    if account.constituent.behavior not in (ChemicalBehavior.CONSERVATIVE, ChemicalBehavior.TOTAL_DISSOLVED_SOLIDS):
        reasons.append("conservative bulk inventory cannot establish reactive process concentration")
    if account.initial.water.value == 0 and account.initial.mass.value > 0 and account.final.water.value > 0:
        evidence = representation.remobilisation_evidence
        if evidence is not None:
            reasons.extend(warmup_restrictions(evidence.provenance, account.interval))
        if (
            representation.remobilisation is not Remobilisation.SUPPORTED
            or evidence is None
            or permitted_use(evidence, context.evidence_scope(context.candidate, account.interval)).finding
            is not CheckFinding.PASS
        ):
            reasons.append("dry retained mass remobilisation is unresolved")
    concentration = None
    presence = Presence.UNSUPPORTED if reasons else Presence.PRESENT
    if account.final.water.value == 0:
        presence = Presence.DRY
        reasons.append("aqueous concentration undefined at zero volume; retained mass is not discarded")
    else:
        value = ReceptorValue(representation.domain, account.final.mass.value / account.final.water.value, "kg/m3")
        concentration = ReceptorBounds(
            value, value, "exact supplied mixed inventory ratio, not spatial evidence", account.provenance.source
        )
    salinity = ReceptorState(
        context,
        account.interval,
        representation.domain,
        StateStatistic.INTERVAL_END,
        concentration,
        presence,
        state_evidence,
        tuple(reasons),
        sources,
    )
    return InventoryStateImport(balance, accounting, representation, (quantity, salinity))
