"""ConfiguredEntryEvidence → FloorOnlyResult demonstration (hypothetical).

Run: uv run python -m examples.graduated_entry
"""

from fractions import Fraction

from examples.natural_baseline import PROVENANCE, synthetic_acceptance
from fishy.evidence import Check, CheckFinding, EvidenceScope
from fishy.graduated_entry import (
    EntryStatistic,
    GraduatedCurve,
    GraduatedSegment,
    LargeRiverScreen,
    ParameterBasis,
    evaluate_graduated_entry,
)
from fishy.natural_routing import select_entry_variant
from fishy.pattern_calendar import AccountingYear
from fishy.quantities import Flow
from fishy.scientific_acceptance import HydrologicalProduct, HydrologicalProductKind, TemporalResolution, UsePurpose
from fishy.spatial import CalculationSection, Location, Reach, WaterBody


def supplied_entry():
    location = Location(
        Reach("entry-reach", "v1", WaterBody("river", "v1")), CalculationSection("section", "v1"), "mapping-v1"
    )
    period = AccountingYear(2024, 1, 0).interval
    subject = HydrologicalProduct(
        EvidenceScope(
            "synthetic daily Q347", "entry-reach", PROVENANCE.reference_member, period, UsePurpose.SIZING.value
        ),
        PROVENANCE,
        HydrologicalProductKind.LOW_FLOW_STATISTIC,
        "pooled daily Q347",
        "m3/s",
        "UTC fixed 86400-second days",
        TemporalResolution.DAILY,
        UsePurpose.SIZING,
        Fraction(347, 365),
        None,
        location,
        "stipulated present climate",
        "complete daily record",
        "synthetic-reference-v1",
        "synthetic-Q347-10-v1",
        Flow(10),
    )
    statistic = EntryStatistic(subject, synthetic_acceptance(subject))
    curve = GraduatedCurve(
        "scenario-v1",
        (
            GraduatedSegment(Flow(0), Flow(0), Fraction(".8")),
            GraduatedSegment(Flow(10), Flow(8), Fraction(".2")),
        ),
        ParameterBasis.HYPOTHETICAL,
        "illustrative continuous concave curve, not policy",
    )
    screen = LargeRiverScreen(
        "scenario-v1",
        Flow(100),
        Fraction(".2"),
        Fraction(".3"),
        ParameterBasis.HYPOTHETICAL,
        "illustrative criterion, not policy",
        "documented hypothetical sensitivity across 90/100/110 m3/s",
    )
    return statistic, curve, screen


def main():
    statistic, curve, screen = supplied_entry()
    unavailable = Check("not_required_after_availability", CheckFinding.UNKNOWN)
    print("Domestic variant:", select_entry_variant(None, unavailable, unavailable).variant.value)
    result = evaluate_graduated_entry(statistic, curve, screen)
    print(result.status.value, "base floor:", result.floor, "no seasonal obligation")
    print("Missing screen:", evaluate_graduated_entry(statistic, curve, None).status.value)


if __name__ == "__main__":
    main()
