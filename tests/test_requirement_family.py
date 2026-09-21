"""U5: complete fixed-family external selection at exact arithmetic boundaries."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from fishy.design_conditions import DesignClass
from fishy.evidence import (
    CheckFinding,
    Completeness,
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
)
from fishy.flows import FlowSample, Presence
from fishy.quantities import Flow
from fishy.requirement_family import (
    ClassRequirement,
    FamilyBasis,
    FloorSeries,
    MemberExclusion,
    ReconstructionNeed,
    RequirementFamily,
    RequirementMember,
    SelectionBranch,
    SelectionSpecification,
    assess_selected_family,
    candidate_scope,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def family(member, values, *, year=2004):
    location = Location(Reach("river", "v1", WaterBody("river", "v1")), CalculationSection("U", "v1"), "v1")
    period = Interval(datetime(year, 1, 1, tzinfo=UTC), datetime(year + 1, 1, 1, tzinfo=UTC))
    basis = FamilyBasis(
        location,
        period,
        "hypothetical",
        "natural-baseline",
        "parameters-v1",
        "quality-v1",
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
    )
    provenance = Provenance(
        "synthetic fixed values",
        basis.scenario,
        member,
        "test",
        "reference-v1",
        basis.parameter_version,
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
        basis.reference_kind,
    )
    days = int(period.seconds / 86400)
    classes = []
    for design in DesignClass:
        series = values[design] if isinstance(values, dict) else values
        if not isinstance(series, tuple):
            series = (series,) * days
        samples = tuple(
            FlowSample(
                location,
                Interval(period.start + timedelta(days=i), period.start + timedelta(days=i + 1)),
                Flow(value),
                Presence.PRESENT,
                provenance,
            )
            for i, value in enumerate(series)
        )
        classes.append(ClassRequirement(design, samples))
    return RequirementFamily(basis, tuple(classes))


def member(identifier, value, *, structure=None):
    candidate = family(identifier, value)
    evidence = EvidenceFindings(
        candidate_scope(candidate),
        candidate.classes[0].samples[0].provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("stipulated synthetic acceptance only",),
    )
    return RequirementMember(
        identifier, structure or identifier, candidate, evidence, "shared errors possible; no independence inferred"
    )


def specification(members, *, need=ReconstructionNeed.REQUIRED, exclusions=()):
    return SelectionSpecification(
        tuple(m.identifier for m in members), exclusions, Fraction(1, 5), need, "D.10 explicit hypothetical theta"
    )


@pytest.mark.parametrize(
    "values,expected,spread,branch",
    [
        ((8, 12), 12, Fraction(2, 5), SelectionBranch.UPPER),
        ((9, 11), 10, Fraction(1, 5), SelectionBranch.MEDIAN),
        ((0, 0), 0, 0, SelectionBranch.MEDIAN),
        ((0, 0, 3), 3, float("inf"), SelectionBranch.UPPER),
        ((8, 9, 10), 10, Fraction(2, 9), SelectionBranch.UPPER),
    ],
)
def test_complete_leap_year_selection(values, expected, spread, branch):
    members = tuple(member(str(i), value) for i, value in enumerate(values))
    supplied = family("selected", expected)
    result = assess_selected_family(members, supplied, specification(members))
    assert result.accepted == supplied
    assert result.maximum_spread == spread
    assert result.branch is branch
    assert len(result.slots) == 4 * 366
    assert result.checks.finding is CheckFinding.PASS
    assert all(s.interval.seconds == 86400 for s in result.slots)


def test_envelope_contributors_can_swap_but_retained_set_cannot():
    a = (8, 12) + (8,) * 364
    b = (12, 8) + (12,) * 364
    members = (member("A", a), member("B", b))
    result = assess_selected_family(members, family("selected", 12), specification(members))
    assert result.slots[0].upper_members == ("B",)
    assert result.slots[1].upper_members == ("A",)
    assert result.accepted is not None
    wrong = family("selected", a)
    assert assess_selected_family(members, wrong, specification(members)).checks.finding is CheckFinding.FAIL


def test_ties_and_even_middle_pair_contributors_retained():
    members = tuple(member(str(i), v) for i, v in enumerate((9, 9, 11, 11)))
    result = assess_selected_family(members, family("selected", 10), specification(members))
    assert result.slots[0].median_members == ("0", "1", "2", "3")
    assert result.slots[0].upper_members == ("2", "3")
    assert result.slots[0].lower_members == ("0", "1")


def test_single_member_screening_and_named_failed_exclusion():
    members = (member("A", 8),)
    exclusion = MemberExclusion("failed-B", ("incomplete reference year; numerical candidate retained externally",))
    result = assess_selected_family(members, family("selected", 8), specification(members, exclusions=(exclusion,)))
    assert result.accepted is None
    assert result.supplied is not None
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.specification.exclusions == (exclusion,)
    assert (
        assess_selected_family(
            (), None, SelectionSpecification((), (exclusion,), Fraction(1, 5), ReconstructionNeed.REQUIRED, "synthetic")
        ).supplied
        is None
    )


def test_same_structure_is_not_two_structural_reconstructions():
    members = (member("A", 9, structure="shared"), member("B", 11, structure="shared"))
    result = assess_selected_family(members, family("selected", 10), specification(members))
    assert result.checks.finding is CheckFinding.UNKNOWN


def test_observed_floor_route_does_not_acquire_reconstruction_requirement():
    f = family("observed", 8)
    floor = FloorSeries(f.basis, f.classes[0].samples)
    e = EvidenceFindings(
        candidate_scope(floor),
        floor.samples[0].provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("observed-statistic entry scenario",),
    )
    m = RequirementMember("observed", "observed input", floor, e, "not reconstruction")
    result = assess_selected_family((m,), floor, specification((m,), need=ReconstructionNeed.NOT_REQUIRED))
    assert result.accepted == floor
    assert all(s.design is None for s in result.slots)
    assert not hasattr(floor, "classes")


def test_stale_acceptance_cannot_follow_changed_values():
    m = member("A", 8)
    stale = replace(m, candidate=family("A", 12))
    result = assess_selected_family(
        (stale,), family("selected", 12), specification((stale,), need=ReconstructionNeed.NOT_REQUIRED)
    )
    assert result.accepted is None
    assert result.checks.finding is CheckFinding.UNKNOWN


def test_failed_member_support_survives_missing_selection():
    m = member("A", 8)
    assert m.evidence is not None
    failed = replace(m, evidence=replace(m.evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED))
    result = assess_selected_family((failed,), None, specification((failed,)))
    assert result.checks.finding is CheckFinding.FAIL
    assert result.checks.completeness is Completeness.INCOMPLETE


@pytest.mark.parametrize("field,value", [("scenario", "other"), ("method", "entry"), ("activation_version", "v2")])
def test_policy_or_scenario_changes_are_separate_studies(field, value):
    a, b = member("A", 8), member("B", 12)
    if field == "scenario":
        with pytest.raises(ValueError):
            replace(b.candidate, basis=replace(b.candidate.basis, **{field: value}))
    else:
        b = replace(b, candidate=replace(b.candidate, basis=replace(b.candidate.basis, **{field: value})))
        with pytest.raises(ValueError, match="separate studies"):
            assess_selected_family((a, b), family("selected", 12), specification((a, b)))


def test_incomplete_class_calendar_and_changing_member_refused():
    f = family("A", 8)
    with pytest.raises(ValueError, match="complete declared"):
        replace(f, classes=(replace(f.classes[0], samples=f.classes[0].samples[:-1]), *f.classes[1:]))
    with pytest.raises(ValueError, match="four-class"):
        replace(f, classes=f.classes[:-1])
    old = f.classes[0]
    changed = replace(old.samples[0], provenance=replace(old.samples[0].provenance, reference_member="B"))
    with pytest.raises(ValueError):
        replace(f, classes=(replace(old, samples=(changed, *old.samples[1:])), *f.classes[1:]))
    with pytest.raises(FrozenInstanceError):
        f.basis.method = "changed"


def test_retained_set_exclusion_overlap_and_delivery_capped_selection_refused():
    members = member("A", 8), member("B", 12)
    with pytest.raises(ValueError, match="fixed retained"):
        assess_selected_family(members[:1], family("selected", 12), specification(members))
    with pytest.raises(ValueError, match="disjoint"):
        specification(members, exclusions=(MemberExclusion("A", ("excluded",)),))
    result = assess_selected_family(members, family("selected", 5), specification(members))
    assert result.checks.finding is CheckFinding.FAIL


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_requirements_are_not_selectable(value):
    with pytest.raises(ValueError):
        family("A", value)


def test_uncapped_selection_precedes_actual_public_issuance_cap():
    from fishy.duties import Deliverability, Requirement
    from fishy.uzbek_issuance import issue_obligation

    members = (member("A", 8), member("B", 12))
    result = assess_selected_family(members, family("selected", 12), specification(members))
    assert isinstance(result.accepted, RequirementFamily)
    sample = result.accepted.classes[0].samples[0]
    issued = issue_obligation(
        Requirement(sample, "requirement-v1"),
        Deliverability(replace(sample, value=Flow(5)), "capacity-v1"),
        version="issue-v1",
        provenance=sample.provenance,
    )
    assert issued.obligation.sample.value == Flow(5)
    assert issued.ecological_deficit == Flow(7)
    assert result.maximum_spread == Fraction(2, 5)
    assert issued.requirement.sample.value == Flow(12)


def test_availability_deliverability_and_independent_duties_do_not_rewrite_history():
    from fishy.duties import (
        Availability,
        Deliverability,
        Delivery,
        DutyApplicability,
        Obligation,
        Requirement,
        SuppliedDuty,
        assess_duty,
    )
    from fishy.uzbek_issuance import issue_obligation

    original = family("selected", 10).classes[0].samples[0]
    availability = Availability(replace(original, value=Flow(8)), "water-account-v1")
    deliverability = Deliverability(replace(original, value=Flow(6)), "capacity-account-v1")
    old = issue_obligation(
        Requirement(original, "requirement-v1"), deliverability, version="issued-v1", provenance=original.provenance
    )
    actual = Delivery(replace(original, value=Flow(5)), "observed-scenario-v2")
    sanitary = SuppliedDuty(
        "sanitary",
        "prior-v1",
        "independent prescribed sanitary schedule",
        DutyApplicability.HYPOTHETICAL,
        (Obligation(replace(original, value=Flow(9)), "prior-v1"),),
        "supplied instrument, no assumed estimator",
    )
    foreign = SuppliedDuty(
        "foreign",
        "prior-v2",
        "independent prescribed Swiss residual flow",
        DutyApplicability.HYPOTHETICAL,
        (Obligation(replace(original, value=Flow(11)), "prior-v2"),),
        "supplied instrument; no Uzbek capping",
    )
    assert assess_duty(sanitary, (actual,)).intervals[0].shortfall == Flow(4)
    assert assess_duty(foreign, (actual,)).intervals[0].shortfall == Flow(6)
    revised = issue_obligation(
        Requirement(replace(original, value=Flow(12)), "requirement-v2"),
        Deliverability(replace(original, value=Flow(7)), "capacity-account-v2"),
        version="issued-v2",
        provenance=original.provenance,
    )
    assert availability.sample.value == Flow(8)
    assert old.requirement.sample.value == Flow(10)
    assert old.deliverability.sample.value == old.obligation.sample.value == Flow(6)
    assert old.ecological_deficit == Flow(4)
    assert revised.obligation.sample.value == Flow(7)
    assert revised.ecological_deficit == Flow(5)
    assert old.obligation.version == "issued-v1"
    assert revised.obligation.version == "issued-v2"
    assert sanitary.schedule[0].sample.value == Flow(9)
    assert foreign.schedule[0].sample.value == Flow(11)
