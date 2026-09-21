"""Selected habitat and high-flow pulse assessment with synthetic study evidence.

Run: uv run python examples/study_requirements.py
"""

from dataclasses import replace
from datetime import UTC, date, datetime
from fractions import Fraction

from fishy.evidence import (
    CheckFinding,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    ScientificAdequacy,
)
from fishy.hydraulics import Comparison, HydraulicRelationEvidence, RelationDomain, StateBounds
from fishy.quantities import Flow
from fishy.spatial import (
    CalculationSection,
    DesignationState,
    Eligibility,
    Location,
    Origin,
    PreparedClassification,
    Reach,
    UseCategory,
    WaterBody,
)
from fishy.study_requirements import (
    FlowResponseRelation,
    HighFlowTrigger,
    Interpolation,
    NaturalStudyComponent,
    ResponsePoint,
    ResponseVariable,
    StudyCondition,
    StudyCriterion,
    StudyNeed,
    StudyScope,
    StudySelection,
    StudyVariable,
    TopTierEligibility,
    assess_natural_study,
)
from fishy.time import Interval

PERIOD = Interval(datetime(2026, 6, 1, tzinfo=UTC), datetime(2026, 6, 2, tzinfo=UTC))
LOCATION = Location(Reach("reach", "v1", WaterBody("river", "v1")), CalculationSection("section", "v1"), "mapping1")
SCOPE = StudyScope("candidate1", LOCATION, PERIOD, "hypothetical", "natural1", "sizing", "summer")
PROVENANCE = Provenance(
    "synthetic selected study",
    "hypothetical",
    "natural1",
    "test",
    "survey1",
    "criteria1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
    ReferenceKind.PRESENT_CLIMATE_NATURAL,
)
EVIDENCE = EvidenceFindings(
    EvidenceScope("candidate1", "reach", "natural1", PERIOD, "sizing"),
    PROVENANCE,
    Computability.COMPUTABLE,
    NumericalValidity.VALID,
    Disclosure.COMPLETE,
    ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
    OfficialAdmissibility.PENDING,
    ("synthetic only",),
)
HABITAT = ResponseVariable(StudyVariable.HABITAT, "m2", "survey bed", "surveyed wetted area")
DEPTH = ResponseVariable(StudyVariable.DEPTH, "m", "survey bed", "section mean")
VELOCITY = ResponseVariable(StudyVariable.VELOCITY, "m/s", "positive downstream", "section mean")
METADATA = HydraulicRelationEvidence(
    "relation1",
    "geometry1",
    "fixed downstream boundary",
    "0 to 10 m3/s",
    "linear envelopes accepted",
    "supplied bounds",
    "hypothetical sizing",
    RelationDomain.SUPPORTED,
)
NEED = StudyNeed("study and review", "basin reviewer", date(2027, 1, 1))
NATURAL = PreparedClassification(
    Origin.NATURAL,
    DesignationState.NONE,
    Eligibility.NOT_APPLICABLE,
    UseCategory.AGRICULTURE_IRRIGATION,
    ("irrigation",),
    "origin survey",
    "v1",
)
POTENTIAL = replace(NATURAL, origin=Origin.ARTIFICIAL)


def relation(variable=HABITAT, values=(0, 100, 20)):
    return FlowResponseRelation(
        SCOPE,
        variable,
        tuple(
            ResponsePoint(Flow(q), StateBounds(Fraction(v), Fraction(v)))
            for q, v in zip((0, 5, 10), values, strict=True)
        ),
        Interpolation.LINEAR,
        "channel survey1",
        METADATA,
        EVIDENCE,
    )


def criterion(variable=HABITAT, low=40, high=100):
    return StudyCriterion(
        variable.variable.value,
        variable,
        StateBounds(Fraction(low), Fraction(high)),
        Comparison.INCLUSIVE,
        Comparison.INCLUSIVE,
        "ecologist selected threshold",
    )


def condition(name, finding=CheckFinding.PASS):
    return StudyCondition(
        SCOPE,
        name,
        "study process",
        "declared study units",
        "reach and event",
        "specialist criterion v1",
        "supplied assessed process state",
        finding,
        EVIDENCE,
    )


def selection(flow=5, criteria=None, required=("ramping",)):
    return StudySelection(
        SCOPE,
        Flow(flow),
        "specialist selection v1",
        "selected potential habitat objective",
        EVIDENCE,
        (criterion(),) if criteria is None else criteria,
        required,
        tuple(condition(n) for n in required),
    )


def main():
    """An explicitly selected 8 m3/s pulse yields 52 m2 of synthetic habitat."""
    study = selection(8, required=("sediment", "hydraulic", "flood_safety", "ramping"))
    component = NaturalStudyComponent("pulse", study, (relation(),), "pulse")
    result = assess_natural_study(
        NATURAL,
        TopTierEligibility.TRIGGERED,
        ("pulse",),
        (component,),
        HighFlowTrigger.SEDIMENT_TRAPPING,
        NEED,
        "eligible_baseline_then_fallback",
        baseline_median_cap=Flow(3),
    )
    print(result.supported_components)
    print(result.components[0].responses[0].value)
    print(result.checks.finding, result.release_permission)
    return result


if __name__ == "__main__":
    main()
