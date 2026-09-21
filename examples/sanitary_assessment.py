"""example : SyntheticSanitaryDuty × ImportedFindings → SeparateSanitaryEcologicalAssessments."""

from datetime import UTC, date, datetime, timedelta

from fishy.duties import Delivery, DutyApplicability, Obligation, Requirement, SuppliedDuty
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ScientificAdequacy,
)
from fishy.flows import FlowSample, Presence
from fishy.quantities import Flow, Volume
from fishy.sanitary_duties import (
    Authenticity,
    CombinedAssessment,
    Currency,
    EcologicalRequirementAssessment,
    InstrumentEvidence,
    RequirementConflict,
    SanitaryDuty,
    assess_sanitary_duty,
)
from fishy.sanitary_hydraulics import (
    HydraulicScope,
    HydraulicVariable,
    ImportedHydraulicFinding,
    TemporalSupport,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def synthetic_inputs() -> tuple[SanitaryDuty, tuple[Delivery, ...], tuple[ImportedHydraulicFinding, ...]]:
    """No national season, law authentication or hydraulic threshold is implied."""
    location = Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "1")
    provenance = Provenance(
        "synthetic specialist study",
        "scenario-1",
        None,
        "example-1",
        "data-1",
        "config-1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )
    start = datetime(2020, 1, 1, tzinfo=UTC)
    periods = tuple(Interval(start + timedelta(days=i), start + timedelta(days=i + 1)) for i in range(2))
    whole = Interval(periods[0].start, periods[-1].end)
    components = (
        (
            "pre_impoundment_velocity",
            HydraulicVariable.DIRECTIONAL_VELOCITY,
            "downstream-positive",
            "§4.3 pre-impoundment minimum",
        ),
        (
            "current_continuity",
            HydraulicVariable.DIRECTIONAL_VELOCITY,
            "downstream-positive",
            "§4.3 current continuity",
        ),
        (
            "release_uniformity",
            HydraulicVariable.RELEASE_DISCHARGE,
            "outlet release",
            "§4.4 maximal possible uniformity",
        ),
        ("stage_change", HydraulicVariable.STAGE, "synthetic datum", "§4.4 within-day stage"),
        ("velocity_change", HydraulicVariable.DIRECTIONAL_VELOCITY, "downstream-positive", "§4.4 within-day velocity"),
    )
    scopes = tuple(
        HydraulicScope(
            name,
            location,
            "named downstream cascade domain",
            "candidate-1",
            "scenario-1",
            variable,
            whole,
            reference,
            TemporalSupport.WITHIN_DAY,
        )
        for name, variable, reference, _ in components
    )
    prescribed = SuppliedDuty(
        "sanitary-instrument",
        "issued-1",
        "synthetic §§4.2–4.4",
        DutyApplicability.HYPOTHETICAL,
        tuple(
            Obligation(FlowSample(location, period, Flow(value), Presence.PRESENT, provenance), "issued-1")
            for period, value in zip(periods, (2, 3), strict=True)
        ),
        "synthetic dated search",
        required_components=("discharge", *(scope.component for scope in scopes)),
    )
    instrument = InstrumentEvidence(
        "synthetic reproduction",
        "synthetic issuer",
        Authenticity.SECONDARY_COPY,
        Currency.UNRESOLVED,
        date(2026, 9, 21),
        prescribed.search_record,
        "obtain competent authenticity/currency/applicability findings",
    )
    supplied = SanitaryDuty(prescribed, instrument, scopes)
    deliveries = tuple(
        Delivery(FlowSample(location, period, Flow(value), Presence.PRESENT, provenance), "delivery-1")
        for period, value in zip(periods, (1.5, 3.5), strict=True)
    )
    findings = tuple(
        ImportedHydraulicFinding(
            scope,
            "synthetic hydraulic study/version-1",
            clause,
            EvidenceFindings(
                EvidenceScope(scope.candidate, location.reach.identifier, None, whole, scope.component),
                provenance,
                Computability.COMPUTABLE,
                NumericalValidity.VALID,
                Disclosure.COMPLETE,
                ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
                OfficialAdmissibility.PENDING,
                ("synthetic software witness, not site evidence",),
            ),
            CheckFinding.PASS,
            ("supplied specialist finding covers the named variable/domain and whole period",),
        )
        for scope, (_, _, _, clause) in zip(scopes, components, strict=True)
    )
    return supplied, deliveries, findings


def main() -> None:
    supplied, deliveries, findings = synthetic_inputs()
    result = assess_sanitary_duty(
        supplied, deliveries, candidate="candidate-1", scenario="scenario-1", hydraulic_findings=findings
    )
    assert result.flow_and_components.known_shortfall_volume == Volume(43200)
    ecological = EcologicalRequirementAssessment(
        "ecological-study-1",
        "independent supplied ecological study",
        "candidate-1",
        "scenario-1",
        tuple(Requirement(item.sample, "ecological-1") for item in supplied.duty.schedule),
        CheckSummary((Check("habitat", CheckFinding.UNKNOWN, ("study not supplied",)),)),
    )
    combined = CombinedAssessment(
        (result,),
        (ecological,),
        (
            RequirementConflict(
                "sanitary-instrument@issued-1",
                "ecological-study-1",
                "synthetic joint operating study",
                "supplied incompatible operating conditions; no precedence chosen",
            ),
        ),
    )
    print("Sanitary shortfall m3:", result.flow_and_components.known_shortfall_volume.value)
    print("Sanitary finding:", result.summary.finding.value, result.summary.completeness.value)
    print("Independent ecological finding:", combined.ecological[0].findings.finding.value)
    print("Retained conflicts:", len(combined.conflicts))
    print("Hypothetical supplied evidence; no legal compliance or ecological-entry permission.")


if __name__ == "__main__":
    main()
