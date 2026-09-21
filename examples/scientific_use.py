"""Supplied annual screening study → scoped scientific finding (synthetic example).

Run with ``uv run python examples/scientific_use.py``. The evidence below is
illustrative. A real application supplies a frozen specialist-reviewed study.
"""

from dataclasses import replace
from datetime import UTC, datetime

from fishy.evidence import (
    CheckFinding,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ReferenceKind,
)
from fishy.quantities import Flow
from fishy.scientific_acceptance import (
    AcceptanceRecord,
    Aggregation,
    ClimateTreatment,
    Comparison,
    CriterionRole,
    DailyDerivation,
    DiagnosticObservation,
    ErrorMeasure,
    EvidenceItem,
    HydrologicalProduct,
    HydrologicalProductKind,
    RatingSupport,
    ScientificCriterion,
    ScientificEvidence,
    TemporalResolution,
    UsePurpose,
    ValidationEvidence,
    ValidationMethod,
    assess_scientific_use,
    minimum_evidence,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def annual_screening_study() -> tuple[AcceptanceRecord, ScientificEvidence]:
    """Construct a fully specified synthetic annual-only study, not a basin finding."""
    location = Location(Reach("upstream", "1", WaterBody("river", "1")), CalculationSection("gauge", "1"), "1")
    provenance = Provenance(
        "illustrative imported annual estimate",
        "screening-study",
        "natural-a",
        "example-v1",
        "synthetic-data-v1",
        "annual-profile-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
    )
    period = Interval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC))
    scope = EvidenceScope("annual magnitude P50", "upstream", "natural-a", period, "annual water-resource screen")
    product = HydrologicalProduct(
        scope,
        provenance,
        HydrologicalProductKind.ANNUAL_MAGNITUDE,
        "annual mean discharge at P50",
        "m3/s",
        "January-December UTC fixed 86400-second days",
        TemporalResolution.ANNUAL,
        UsePurpose.SCREENING,
        0.5,
        None,
        location,
        "present climate 2000-2019",
        "complete annual means, zero and tied observations retained",
        "synthetic-reference-full-content-v1",
        "synthetic-imported-estimate-content-v1",
        Flow(25),
    )
    criterion = ScientificCriterion(
        "annual_error",
        CriterionRole.MANDATORY,
        "candidate annual mean minus reference annual mean",
        "complete withheld accounting year",
        "m3/s",
        ErrorMeasure.ABSOLUTE,
        Aggregation.EACH_CASE,
        Comparison.AT_MOST,
        3.0,
        ("withheld-year-2010",),
        "Synthetic annual screening precision of 3 m3/s; not policy",
    )
    record = AcceptanceRecord(
        product,
        "annual-screen-v1",
        "preparer",
        "independent reviewer",
        datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 9, 10, tzinfo=UTC),
        (criterion,),
        "conditional sampling and rating uncertainty; 90% coverage supplied by study",
        ("structural alternatives not represented",),
        "annual P50 screening only; not daily or rare-tail use",
        (scope.intended_use,),
        (),
        "additional independent observations and updated frozen review",
        indicative_basis="Short record supports only the stated annual screen with disclosed sensitivity",
    )
    items = tuple(
        EvidenceItem(
            requirement,
            CheckFinding.PASS,
            "synthetic specialist appendix: " + requirement.value,
            "Illustrative supplied support for this exact annual screen; replace with application evidence",
        )
        for requirement in minimum_evidence(product, DailyDerivation.NATIVE)
    )
    observation = DiagnosticObservation(
        "annual_error",
        "withheld-year-2010",
        23.0,
        20.0,
        "m3/s",
        criterion.formula,
        criterion.domain,
        "synthetic independent annual observation",
    )
    validation = ValidationEvidence(
        ValidationMethod.WITHHELD,
        ("climate-year-2001",),
        ("climate-year-2010",),
        (),
        (),
        ("training-year-2001",),
        ("withheld-year-2010",),
        (),
        (),
        (),
        ("rating dependence disclosed by specialist",),
        datetime(2026, 9, 5, tzinfo=UTC),
        "complete annual withheld case; no shared climate cluster used for training",
    )
    evidence = ScientificEvidence(
        product,
        record.profile_version,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        OfficialAdmissibility.PENDING,
        items,
        (observation,),
        validation,
        RatingSupport.OUTSIDE_RANGE,
        ClimateTreatment.COMMON_BASIS,
        DailyDerivation.NATIVE,
        frozen_record=record,
    )
    return record, evidence


def main() -> None:
    record, evidence = annual_screening_study()
    result = assess_scientific_use(record, evidence)
    print(result.findings.scientific_adequacy.value)
    print(f"annual error: {result.comparisons[0].actual} <= {record.criteria[0].limit} m3/s")
    print("official use:", result.findings.official_admissibility.value)
    print("restriction:", result.findings.restrictions[0].reason)
    missing = assess_scientific_use(record, replace(evidence, validation=None))
    print("missing validation:", missing.findings.scientific_adequacy.value)


if __name__ == "__main__":
    main()
