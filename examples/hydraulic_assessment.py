"""example : SuppliedHydraulicStates → HydraulicAssessment (pure).

Run with uv run python examples/hydraulic_assessment.py.
All values are synthetic, not ecological defaults.
"""

from datetime import UTC, datetime
from fractions import Fraction

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
from fishy.hydraulics import (
    BoundState,
    CriterionStatus,
    HydraulicScope,
    HydraulicState,
    HydraulicVariable,
    StateBounds,
    StateCriterion,
    StateLimit,
    TemporalSupport,
    assess_hydraulics,
    assess_state_range,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def example():
    period = Interval(datetime(2020, 1, 1, tzinfo=UTC), datetime(2020, 1, 2, tzinfo=UTC))
    location = Location(Reach("reach", "v1", WaterBody("river", "v1")), CalculationSection("section", "v1"), "v1")
    scope = HydraulicScope(
        "depth",
        location,
        "surveyed section",
        "candidate",
        "hypothetical",
        HydraulicVariable.DEPTH,
        period,
        "survey bed v1",
        TemporalSupport.INTERVAL_MEANS,
    )
    evidence = EvidenceFindings(
        EvidenceScope(scope.candidate, "reach", None, period, "depth"),
        Provenance(
            "study", "hypothetical", None, "v1", "v1", "v1", ProductionMethod.ILLUSTRATIVE, CorrectionState.ORIGINAL
        ),
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("synthetic study accepted only for this demonstration",),
    )
    criterion = StateCriterion(
        scope,
        "selected study threshold v1",
        CriterionStatus.HYPOTHETICAL,
        StateLimit(BoundState.SUPPLIED, Fraction(".3")),
        StateLimit(BoundState.INTENTIONALLY_ABSENT, None),
    )
    state = HydraulicState(scope, StateBounds(Fraction(".4"), Fraction(".5")), evidence)
    assessed = assess_state_range(criterion, state)
    return assess_hydraulics((scope,), (assessed,))


if __name__ == "__main__":
    result = example()
    print(result.finding.value, result.completeness.value)
