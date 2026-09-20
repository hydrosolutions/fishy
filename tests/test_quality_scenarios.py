"""Caller-owned profile comparisons; no comparison engine or policy selection in Fishy."""

from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction

from fishy.evidence import CheckFinding, CorrectionState, ProductionMethod, Provenance
from fishy.flows import Presence
from fishy.mixing import BoundarySupport, FixedBoundary, LoadRate, MixingConstituent, solve_mixing
from fishy.quality import (
    ChemicalBehavior,
    ChemicalIdentity,
    Comparison,
    GroupMember,
    GroupTarget,
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

LOCATION = Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "1")
INTERVAL = Interval(datetime(2020, 1, 1, tzinfo=UTC), datetime(2020, 1, 2, tzinfo=UTC))
PROVENANCE = Provenance(
    "synthetic sensitivity inputs",
    "comparison",
    None,
    "fishy",
    "1",
    "1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
)
BASIS = "supported interval concentration"


def chemical(name):
    return ChemicalIdentity(name, name, "as " + name, "dissolved", ChemicalBehavior.CONSERVATIVE)


def profile(identifier, targets):
    return QualityProfile(
        identifier,
        "1",
        "synthetic",
        "explicit scenario interpretation",
        "1",
        "source-local",
        "configured sensitivity",
        LOCATION,
        INTERVAL,
        "comparison",
        ProfileStatus.SCENARIO,
        tuple(target.identifier for target in targets),
        targets,
        "synthetic sensitivity only",
        "point-case, no uncertainty qualification",
        identifier,
    )


def observation(identity, value):
    quantity = QualityValue(value, "kg/m3")
    return QualityObservation(
        identity.identifier,
        identity,
        QualityBounds(quantity, quantity, "point", "synthetic"),
        LOCATION,
        INTERVAL,
        BASIS,
        Presence.PRESENT,
        PROVENANCE,
        ObservationKind.SYNTHETIC,
        "synthetic complete-mixing point case",
        "conservative",
    )


def test_external_organoleptic_qualifier_sensitivity():
    taste, odour = chemical("taste-solute"), chemical("odour-solute")
    members = (GroupMember(taste, QualityValue(1, "kg/m3")), GroupMember(odour, QualityValue(1, "kg/m3")))
    common = GroupTarget(
        "organoleptic",
        members,
        Comparison.LE,
        BASIS,
        "report recommended scenario",
        "explicit hypothetical common organoleptic group; not official approval",
    )
    split = tuple(
        GroupTarget(
            name,
            (member,),
            Comparison.LE,
            BASIS,
            "qualifier-subgroup alternative",
            "explicit hypothetical qualifier reading; not official approval",
        )
        for name, member in zip(("taste", "odour"), members, strict=True)
    )
    observations = (observation(taste, "0.6"), observation(odour, "0.6"))
    single = assess_quality(profile("single-organoleptic", (common,)), observations)
    alternative = assess_quality(profile("qualifier-subgroups", split), observations)
    assert single.results[0].lower == Fraction(6, 5)
    assert single.summary.finding is CheckFinding.FAIL
    assert [result.lower for result in alternative.results] == [Fraction(3, 5), Fraction(3, 5)]
    assert alternative.summary.finding is CheckFinding.PASS
    assert single.profile.interpretation != alternative.profile.interpretation
    assert common.members == members  # Comparison never mutates source membership.


def test_assigned_category_sizes_flow_while_stricter_general_constraint_stays_failed():
    salt = chemical("salt")
    category = QualityTarget(
        "assigned-category",
        salt,
        Comparison.LE,
        QualityValue("0.5", "kg/m3"),
        BASIS,
        "DP-QUAL-1 working category reading; official applicability unresolved",
    )
    sanitary = QualityTarget(
        "general-sanitary",
        salt,
        Comparison.LE,
        QualityValue("0.4", "kg/m3"),
        BASIS,
        "separate general constraint, not substituted into sizing",
    )
    boundary = FixedBoundary(
        LOCATION,
        INTERVAL,
        Flow(10),
        (MixingConstituent(salt, LoadRate(8), QualityValue("0.1", "kg/m3")),),
        BoundarySupport("synthetic fixed conservative complete-mixing boundary; arrival excluded; all loads once"),
        PROVENANCE,
    )
    sized = solve_mixing(boundary, (category,))
    assert sized.quality_interval.minimum == Fraction(15, 2)
    assert sized.candidate is not None
    concentration = sized.candidate.predictions[0][1].value
    result = assess_quality(profile("independent-duties", (category, sanitary)), (observation(salt, concentration),))
    assert [test.check.finding for test in result.results] == [CheckFinding.PASS, CheckFinding.FAIL]
    assert result.summary.finding is CheckFinding.FAIL
    assert sized.targets == (category,)
    assert sized.quality_interval.minimum == Fraction(15, 2)


def test_scoped_scenarios_do_not_rewrite_imports_or_previous_results():
    salt = chemical("salt")
    target = QualityTarget("upper", salt, Comparison.LE, QualityValue(10, "mg/l"), BASIS, "source")
    original = profile("original", (target,))
    imported = observation(salt, "0.008")
    first = assess_quality(original, (imported,))
    override = original.override(
        identifier="stricter",
        version="2",
        scenario="other-scenario",
        targets=(replace(target, limit=QualityValue(5, "mg/l")),),
        interpretation="hypothetical override",
    )
    unmatched = assess_quality(override, (imported,))
    assert unmatched.summary.finding is CheckFinding.UNKNOWN
    supplied_other = replace(imported, provenance=replace(imported.provenance, scenario="other-scenario"))
    assert assess_quality(override, (supplied_other,)).summary.finding is CheckFinding.FAIL
    assert first.summary.finding is CheckFinding.PASS
    assert original.targets[0].limit == QualityValue(10, "mg/l")
    assert imported.provenance.scenario == "comparison"
