"""A synthetic supplied monthly spawning coefficient, not a legal finding."""

from datetime import UTC, datetime, timedelta

from fishy.design_conditions import DesignClass
from fishy.evidence import (
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
from fishy.quantities import SignedState, StateVariable
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.spawning import (
    BiologicalTiming,
    CoefficientInterpretation,
    EligibilityInterpretation,
    StarRelevance,
    TemporalBasis,
    coefficient_scope,
    spawning_schedule,
)
from fishy.time import Interval


def main() -> None:
    location = Location(
        Reach("synthetic-reach", "1", WaterBody("synthetic-river", "1")), CalculationSection("section", "1"), "1"
    )
    provenance = Provenance(
        "synthetic biological study",
        "scenario-1",
        "reference-1",
        "1",
        "1",
        "1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )
    onset = datetime(2024, 4, 15, tzinfo=UTC)
    period = Interval(onset, onset + timedelta(days=6))
    month = Interval(datetime(2024, 4, 1, tzinfo=UTC), datetime(2024, 5, 1, tzinfo=UTC))

    def evidence(scope: EvidenceScope) -> EvidenceFindings:
        return EvidenceFindings(
            scope,
            provenance,
            Computability.COMPUTABLE,
            NumericalValidity.VALID,
            Disclosure.COMPLETE,
            ScientificAdequacy.ACCEPTED,
            OfficialAdmissibility.PENDING,
            ("synthetic support, not field calibration",),
        )

    timing = BiologicalTiming(
        "Сазан",
        onset,
        0,
        (2, 2, 2),
        SignedState(StateVariable.TEMPERATURE, 15, "degC", "onset water temperature"),
        SignedState(StateVariable.TEMPERATURE, 15, "degC", "species onset threshold"),
        evidence(
            EvidenceScope(
                "spawning_timing", location.reach.identifier, provenance.reference_member, period, "spawning_correction"
            )
        ),
        location,
    )
    coefficients = spawning_schedule(
        location,
        (month,),
        provenance,
        DesignClass.MODERATELY_DRY,
        EligibilityInterpretation.PERCENTAGE_WORDING,
        TemporalBasis.MONTHLY_AVERAGE,
        CoefficientInterpretation.LISTED_VALUE,
        StarRelevance.NOT_RELIED_UPON,
        timing,
        (evidence(coefficient_scope(location, month, provenance)),),
        basin_row=2,
    )
    print(f"Aral–Syrdarya published monthly coefficient: {coefficients[0].value} (1.18)")
    print("Official admissibility remains pending; no daily-stage claim.")


if __name__ == "__main__":
    main()
