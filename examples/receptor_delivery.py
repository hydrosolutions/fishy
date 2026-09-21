"""SyntheticStorageSchedule → DeliveryAssessment for a supplied fixed-delay pathway.

Run: uv run python examples/receptor_delivery.py
All numbers and scientific acceptances are illustrative, not site or policy data.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

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
from fishy.quality import ChemicalBehavior, ChemicalIdentity
from fishy.quantities import Flow, Volume
from fishy.receptor_delivery import (
    BoundInclusion,
    CoupledStateObjective,
    DeliveryAssessment,
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
    assess_delivery,
    delivery_scope,
    map_arrival,
    storage_arrival,
)
from fishy.receptor_states import Compartment, ReceptorDomain, ReceptorVariable, StateStatistic
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def supplied_delivery() -> DeliveryAssessment:
    """Construct and recheck one synthetic selected operating schedule."""
    reach = Reach("wetland-reach", "v1", WaterBody("wetland", "v1"))

    def location(name: str) -> Location:
        return Location(reach, CalculationSection(name, "v1"), "map-v1")

    start = datetime(2024, 1, 1, tzinfo=UTC)
    period = Interval(start, start + timedelta(days=1))
    provenance = Provenance(
        "synthetic storage study",
        "hypothetical operating schedule",
        "reference-1",
        "example-v1",
        "synthetic-v1",
        "config-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )
    context = DeliveryContext(
        location("wetland-storage"), period, "selected-schedule", "mixed wetland storage m3", provenance
    )

    def accepted(subject: object, source: str) -> EvidenceFindings:
        # This explicit illustrative acceptance does not authenticate site evidence.
        return EvidenceFindings(
            delivery_scope(context, subject),
            replace(provenance, source=source),
            Computability.COMPUTABLE,
            NumericalValidity.VALID,
            Disclosure.COMPLETE,
            ScientificAdequacy.ACCEPTED,
            OfficialAdmissibility.PENDING,
            ("synthetic example only; no ecological or legal certification",),
        )

    rain = WaterExchange("rain", context, ExchangeDirection.INFLOW, Volume(20), location("atmosphere"))
    evaporation = WaterExchange("evaporation", context, ExchangeDirection.OUTFLOW, Volume(10), location("atmosphere"))
    balance = StorageBalance(
        context,
        Volume(100),
        Volume(200),
        (rain, evaporation),
        "accepted synthetic storage balance v1",
        "exact synthetic inputs, not field uncertainty",
    )
    balance_evidence = accepted(balance, "synthetic storage study")
    need = storage_arrival(balance, balance_evidence)
    assert need.arrival is not None

    delay = timedelta(hours=6)
    release_period = Interval(period.start - delay, period.end - delay)
    seepage = WaterExchange("canal-seepage", context, ExchangeDirection.OUTFLOW, Volume(8), location("aquifer"))
    path = Pathway(
        "canal",
        context,
        location("control-gate"),
        release_period,
        delay,
        Volume(3),
        Volume(5),
        (seepage,),
        Flow(0),
        Flow(1),
        Flow(0),
        Interval(release_period.start - timedelta(days=1), release_period.start),
        Fraction(1),
        Fraction(1),
        "fixed-delay stock/loss account v1",
        "supplied in-transit stocks and fixed loss; adjacent interval means",
        "exact synthetic account, not field uncertainty",
    )
    candidate = map_arrival(path, need.arrival)
    assert candidate is not None
    selected = PathwayRelease(path, candidate, accepted(path, "synthetic pathway study"))

    # A supported compartment-model value, not the incoming water concentration.
    salinity = ProcessTest(
        "salinity",
        context,
        "resident conservative salt",
        "kg/m3",
        "representative mixed compartment; supplied whole-interval maximum",
        Fraction(3, 10),
        None,
        Fraction(1),
        BoundInclusion.INCLUSIVE,
        "synthetic independent process model v1",
    )
    step = DeliveryStep(
        balance,
        balance_evidence,
        (selected,),
        ("canal",),
        ("salinity",),
        (SupportedProcessTest(salinity, accepted(salinity, "synthetic process study")),),
        None,
    )
    step = replace(step, checking_evidence=accepted(step.checking_subject, "synthetic independent schedule audit"))
    return assess_delivery((step,), period=period)


def supplied_inundation() -> DeliveryAssessment:
    """Assess a coupled-model wet-area response without inventing a storage target."""
    storage_step = supplied_delivery().steps[0].step
    balance = replace(storage_step.balance, target=None)
    context = balance.context
    source = storage_step.evidence
    assert source is not None

    def accepted(subject: object, study: str) -> EvidenceFindings:
        return replace(
            source, scope=delivery_scope(context, subject), provenance=replace(source.provenance, source=study)
        )

    area = ProcessTest(
        "wet-area",
        context,
        "wet_area",
        "m2",
        "surveyed wetland footprint v1",
        Fraction(120),
        Fraction(100),
        Fraction(150),
        BoundInclusion.INCLUSIVE,
        "synthetic coupled inundation relation v1",
    )
    salt_domain = ReceptorDomain(
        ReceptorVariable.SALINITY,
        Compartment.RESIDENT_WATER,
        "representative mixed compartment; dissolved chloride",
        ChemicalIdentity("chloride", "Cl-", "as chloride", "dissolved", ChemicalBehavior.CONSERVATIVE),
    )
    salt = replace(storage_step.processes[0].test, variable="salinity", reference=salt_domain.basis)
    objective = CoupledStateObjective(
        SupportedProcessTest(area, accepted(area, "synthetic inundation response")),
        Volume(200),
        "coupled surface-groundwater model v1",
        "surveyed footprint and selected gate release; prescribed boundary head",
        "exact illustrative model response, not site calibration",
        StateStatistic.WHOLE_INTERVAL,
        StateStatistic.WHOLE_INTERVAL,
        (context.period,),
        "salinity",
        salt_domain,
        SalinitySupport.COUPLED_MODEL,
    )
    step = replace(
        storage_step,
        balance=balance,
        evidence=accepted(balance, "synthetic physical inventory study"),
        state_objective=objective,
        processes=(SupportedProcessTest(salt, accepted(salt, "synthetic coupled salt response")),),
        checking_evidence=None,
    )
    step = replace(step, coupled_evidence=accepted(step.coupled_subject, "synthetic coupled relation acceptance"))
    step = replace(step, checking_evidence=accepted(step.checking_subject, "synthetic independent inundation audit"))
    return assess_delivery((step,), period=context.period)


def main() -> None:
    result = supplied_delivery()
    step = result.steps[0]
    assert step.residual.arrival is not None and step.final_storage is not None
    print("arrival_m3=", step.residual.arrival.value)
    print("control_m3=", step.pathways[0].selected.release.value)
    print("final_storage_m3=", step.final_storage.value)
    print("finding=", result.checks.finding.value)
    assert step.step.evidence is not None
    print("official_admissibility=", step.step.evidence.official_admissibility.value)
    inundation = supplied_inundation()
    print("nonstorage_finding=", inundation.checks.finding.value)


if __name__ == "__main__":
    main()
