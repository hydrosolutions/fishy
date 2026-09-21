"""Annual estimates from complete annual inputs, without daily data or a simulator."""

from dataclasses import replace
from datetime import UTC, datetime

from fishy.annual_statistics import (
    AnnualEstimator,
    AnnualReference,
    ExceedanceProbability,
    ImportedAnnualReference,
    ImportedDerivation,
    TrendTreatment,
    annual_use_checks,
    empirical_estimate,
    import_annual_estimate,
)
from fishy.evidence import (
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    ScientificAdequacy,
    UseRestriction,
)
from fishy.flows import FlowSample, Presence
from fishy.quantities import Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def annual_example():
    location = Location(
        Reach("example-reach", "1", WaterBody("example-river", "1")), CalculationSection("section", "1"), "1"
    )
    source = Provenance(
        "synthetic annual inputs",
        "illustration",
        "reference-A",
        "example-1",
        "data-1",
        "config-1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
    )
    observations = tuple(
        FlowSample(
            location,
            Interval(datetime(year, 1, 1, tzinfo=UTC), datetime(year + 1, 1, 1, tzinfo=UTC)),
            Flow(value),
            Presence.PRESENT,
            source,
        )
        for year, value in zip(range(2000, 2004), (40, 30, 20, 10), strict=True)
    )
    reference = AnnualReference(
        observations,
        Interval(observations[0].interval.start, observations[-1].interval.end),
        "synthetic common climate",
        1,
        0,
        (),
        TrendTreatment.COMMON_CLIMATE,
        "illustrative supplied climate appraisal",
    )
    median = empirical_estimate(reference, ExceedanceProbability(".5"), provenance=source, profile_version="study-1")
    use = "annual screening"
    finding = EvidenceFindings(
        median.scope(use),
        source,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("illustrative specialist decision permits annual screening only",),
        (UseRestriction("rating-range evidence does not support sizing", ("sizing",)),),
    )
    screening = annual_use_checks(median, finding, use)
    # A separate exact-scope finding still cannot waive the retained restriction.
    sizing = annual_use_checks(median, replace(finding, scope=median.scope("sizing")), "sizing")
    unsupported = empirical_estimate(
        reference, ExceedanceProbability(".99"), provenance=source, profile_version="study-1"
    )
    # An attributable specialist import need not provide its raw calibration values.
    import_reference = ImportedAnnualReference(
        location,
        source,
        reference.accepted_years,
        reference.reference_period,
        reference.climate_basis,
        1,
        0,
        (),
        reference.trend,
        reference.climate_evidence,
    )
    derivation = ImportedDerivation(
        "q(P)=a*(1-P)^b; a=100,b=0.5",
        "external study parameter estimate",
        "calibration artifact sha256 supplied by the real application",
        ("withheld diagnostic artifact",),
        "rare-tail applicability requires separate scientific review",
        "external joint uncertainty study",
        "versioned script, inputs and output artifact references",
    )
    imported = import_annual_estimate(
        import_reference,
        ExceedanceProbability(".99"),
        Flow(10),
        estimator=AnnualEstimator.IMPORTED_STATIONARY,
        profile_version="external-study-1",
        provenance=source,
        derivation=derivation,
    )
    return median, screening, sizing, unsupported, imported


if __name__ == "__main__":
    median, screening, sizing, unsupported, imported = annual_example()
    print("P50:", median.value, "screen:", screening.finding.value, "sizing:", sizing.finding.value)
    print("P99 ranking:", unsupported.value, unsupported.reasons)
    print("Imported P99:", imported.value, "scientific finding not supplied")
