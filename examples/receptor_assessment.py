"""A supplied mixed wetland inventory passes storage and fails its salinity target.

Run: uv run python examples/receptor_assessment.py
All quantities and permissions are synthetic, not ecological defaults.
"""

from datetime import UTC, datetime

from fishy.evidence import (
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
from fishy.load_accounts import AccountTransfer, Inventory, LoadAccount, Mass
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
    Compartment,
    ReceptorAssessment,
    ReceptorContext,
    ReceptorDomain,
    ReceptorProfile,
    ReceptorTarget,
    ReceptorValue,
    ReceptorVariable,
    StateStatistic,
    assess_receptor,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def assess_supplied_inventory() -> ReceptorAssessment:
    """Assess supplied 200 m3 / 250 kg; do not simulate mixing or choose a release."""
    period = Interval(datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 1, 2, tzinfo=UTC))
    receptor = Location(Reach("wetland", "1", WaterBody("lake", "1")), CalculationSection("water-column", "1"), "1")
    context = ReceptorContext(receptor, "selected-schedule", "hypothetical", "reference-1", period)
    provenance = Provenance(
        "synthetic study",
        context.scenario,
        context.reference_member,
        "example-1",
        "study-1",
        "profile-1",
        ProductionMethod.IMPORTED,
        CorrectionState.ORIGINAL,
    )

    def accepted(product: str) -> EvidenceFindings:
        return EvidenceFindings(
            context.evidence_scope(product, period),
            provenance,
            Computability.COMPUTABLE,
            NumericalValidity.VALID,
            Disclosure.COMPLETE,
            ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
            OfficialAdmissibility.PENDING,
            ("supported only for this illustrative use",),
        )

    chemical = ChemicalIdentity("salt", "dissolved", "salt mass", "dissolved", ChemicalBehavior.CONSERVATIVE)
    storage = ReceptorDomain(ReceptorVariable.STORAGE, Compartment.RESIDENT_WATER, "surveyed storage")
    salinity = ReceptorDomain(
        ReceptorVariable.SALINITY, Compartment.RESIDENT_WATER, "representative mixed water", chemical
    )
    targets = (
        ReceptorTarget(
            "storage",
            ReceptorValue(storage, 200, "m3"),
            Comparison.GE,
            StateStatistic.INTERVAL_END,
            "hypothetical wet season",
            "one-day interval endpoint",
            "locally supplied habitat objective",
            accepted("storage"),
        ),
        ReceptorTarget(
            "salinity",
            ReceptorValue(salinity, 1, "kg/m3"),
            Comparison.LE,
            StateStatistic.INTERVAL_END,
            "hypothetical wet season",
            "one-day interval endpoint",
            "locally supplied tolerance",
            accepted("salinity"),
        ),
    )
    profile = ReceptorProfile(
        "wetland-targets", "1", context, (period,), targets, ("storage",), ("salinity",), ProfileStatus.SCENARIO
    )
    # Final inventory is imported from an independent physical representation.
    # Fishy checks its balance; the equations are not a native process solver.
    account = LoadAccount(
        "wetland",
        chemical,
        period,
        context.scenario,
        Inventory(Volume(100), Mass(50)),
        Inventory(Volume(200), Mass(250)),
        provenance,
    )
    arrival = AccountTransfer("arrival", None, "wetland", Inventory(Volume(100), Mass(200)))
    balance = ReceptorBalance(account, (arrival,), (CountedLoad("arrival-salt", "arrival"),))
    state_evidence = accepted(context.candidate)
    representation = MixedCompartmentEvidence(salinity, state_evidence, Remobilisation.NOT_REQUIRED)
    imported = import_receptor_inventory(balance, context, storage, state_evidence, representation)
    imported.accounting.require_valid()
    return assess_receptor(profile, imported.states)


def main() -> None:
    result = assess_supplied_inventory()
    for test in result.tests:
        assert test.target is not None
        print(f"{test.target.identifier}: {test.supported.finding.value}")
    print(f"joint: {result.summary.finding.value}; coverage: {result.summary.completeness.value}")


if __name__ == "__main__":
    main()
