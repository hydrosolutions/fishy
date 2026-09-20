"""Assess supplied quality and solve an exact conditional arrival interval.

All values and support declarations below are synthetic, not local evidence or policy.
Run: uv run python examples/imported_quality.py
"""

from datetime import UTC, datetime
from fractions import Fraction

from fishy.evidence import CorrectionState, ProductionMethod, Provenance
from fishy.flows import Presence
from fishy.mixing import BoundarySupport, FixedBoundary, FlowConstraints, LoadRate, MixingConstituent, solve_mixing
from fishy.quality import (
    ChemicalBehavior,
    ChemicalIdentity,
    Comparison,
    ObservationKind,
    ProfileStatus,
    QualityBounds,
    QualityObservation,
    QualityProfile,
    QualityTarget,
    QualityValue,
    assess_quality,
)
from fishy.quantities import Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def main():
    location = Location(
        Reach("river-reach", "1", WaterBody("river", "1")), CalculationSection("mixed-section", "1"), "map-1"
    )
    interval = Interval(datetime(2020, 2, 29, tzinfo=UTC), datetime(2020, 3, 1, tzinfo=UTC))
    provenance = Provenance(
        "synthetic imported evidence",
        "illustration",
        None,
        "fishy",
        "1",
        "1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )
    salt = ChemicalIdentity("salt", "NaCl", "as NaCl", "dissolved", ChemicalBehavior.CONSERVATIVE)
    basis = "interval representative complete-mixing concentration"
    target = QualityTarget("salt-upper", salt, Comparison.LE, QualityValue(500, "mg/l"), basis, "synthetic upper limit")
    profile = QualityProfile(
        "illustration",
        "1",
        "synthetic",
        "supplied illustration",
        "1",
        "example",
        "quality screening",
        location,
        interval,
        "illustration",
        ProfileStatus.SCENARIO,
        (target.identifier,),
        (target,),
        "this section/interval only",
        "point case, no uncertainty claim",
        "explicit inclusive scenario",
    )
    value = QualityValue(600, "mg/l")
    observation = QualityObservation(
        "salt",
        salt,
        QualityBounds(value, value, "supplied point case", provenance.source),
        location,
        interval,
        basis,
        Presence.PRESENT,
        provenance,
        ObservationKind.SYNTHETIC,
        "illustrative complete mixing",
        "conservative aqueous salt",
    )
    assessed = assess_quality(profile, (observation,))
    support = BoundarySupport(
        "Synthetic fixed complete-mixing boundary; all background carriers included once, "
        "arrival water/load excluded, concentrations/loads fixed as arrival varies"
    )
    boundary = FixedBoundary(
        location,
        interval,
        Flow(10),
        (MixingConstituent(salt, LoadRate(8), QualityValue(100, "mg/l")),),
        support,
        provenance,
    )
    solved = solve_mixing(boundary, (target,), FlowConstraints(location, interval, ecological_total=Flow(20)))
    assert solved.candidate is not None
    assert solved.quality_total is not None
    assert solved.quality_interval.minimum == Fraction(15, 2)
    assert solved.candidate.arrival.value == 10
    print(f"Imported concentration: 600 mg/l; upper limit: 500 mg/l; finding: {assessed.summary.finding.value}")
    print(
        f"Quality-only arrival minimum: {solved.quality_interval.minimum} m3/s; conditional total: {solved.quality_total.value} m3/s"
    )
    print(f"Combined arrival: {solved.candidate.arrival.value} m3/s; total: {solved.candidate.total.value} m3/s")
    print("Combined concentration: 450 mg/l; screen only, no activated requirement or permit")


if __name__ == "__main__":
    main()
