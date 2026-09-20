"""Public prepared-spatial acceptance: classification, identity and declared mappings."""

from dataclasses import FrozenInstanceError, replace

import pytest

from fishy.spatial import (
    CalculationSection,
    ClassificationBasis,
    CompliancePoint,
    DesignationState,
    Eligibility,
    Location,
    ModelLocation,
    ObservationPoint,
    Origin,
    PlanAssignment,
    PlanStatus,
    PlanUnit,
    PreparedClassification,
    PreparedMapping,
    Reach,
    Track,
    UseCategory,
    WaterBody,
    assessment_track,
)


def location() -> Location:
    return Location(
        Reach("reach", "geometry-1", WaterBody("river", "geometry-1")), CalculationSection("section", "1"), "1"
    )


def classification(origin: Origin, category: UseCategory) -> PreparedClassification:
    return PreparedClassification(
        origin,
        DesignationState.NONE,
        Eligibility.NOT_APPLICABLE,
        category,
        ("documented use",),
        "survey and designation search 2026-09",
        "1",
    )


@pytest.mark.parametrize(
    ("origin", "category", "use", "expected"),
    [
        (Origin.NATURAL, UseCategory.AGRICULTURE_IRRIGATION, "irrigation river", Track.NATURAL),
        (Origin.ARTIFICIAL, UseCategory.DRINKING_DOMESTIC, "drinking-water canal", Track.POTENTIAL),
        (Origin.ARTIFICIAL, UseCategory.AGRICULTURE_IRRIGATION, "collector-drain", Track.POTENTIAL),
        (Origin.ARTIFICIAL, UseCategory.UNDETERMINED, "constructed reservoir", Track.POTENTIAL),
        (Origin.NATURAL, UseCategory.UNDETERMINED, "reservoir-linked natural reach", Track.NATURAL),
    ],
)
def test_c1_origin_is_independent_of_use(origin, category, use, expected):
    record = replace(classification(origin, category), uses=(use,))
    result = assessment_track(record)
    assert result.track is expected
    assert result.classification is record
    assert result.reason


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (DesignationState.NONE, Track.NATURAL),
        (DesignationState.NOT_SEARCHED, Track.UNDETERMINED),
        (DesignationState.PENDING, Track.UNDETERMINED),
        (DesignationState.DESIGNATED, Track.POTENTIAL),
        (DesignationState.EXPIRED, Track.NATURAL),
        (DesignationState.REJECTED, Track.NATURAL),
    ],
)
def test_c1_six_designation_states_preserved(state, expected):
    record = replace(
        classification(Origin.NATURAL, UseCategory.FISHERIES),
        designation=state,
        designation_eligibility=Eligibility.ACCEPTED
        if state is DesignationState.DESIGNATED
        else Eligibility.NOT_APPLICABLE,
    )
    result = assessment_track(record)
    assert result.track is expected
    assert result.classification.designation is state


@pytest.mark.parametrize("eligibility", [Eligibility.UNRESOLVED, Eligibility.REJECTED, Eligibility.NOT_APPLICABLE])
def test_c1_designation_without_safeguards_cannot_downgrade(eligibility):
    record = replace(
        classification(Origin.NATURAL, UseCategory.FISHERIES),
        designation=DesignationState.DESIGNATED,
        designation_eligibility=eligibility,
    )
    assert assessment_track(record).track is Track.UNDETERMINED


@pytest.mark.parametrize("origin", [Origin.UNKNOWN, Origin.NOT_ASSESSED])
def test_c1_unknown_origin_is_not_inferred_from_category(origin):
    assert assessment_track(classification(origin, UseCategory.AGRICULTURE_IRRIGATION)).track is Track.UNDETERMINED


def test_c1_hypothetical_assignment_remains_labelled():
    original = classification(Origin.UNKNOWN, UseCategory.UNDETERMINED)
    scenario = replace(original, origin=Origin.NATURAL, basis=ClassificationBasis.HYPOTHETICAL, version="scenario-1")
    assert assessment_track(scenario).track is Track.NATURAL
    assert assessment_track(scenario).classification.basis is ClassificationBasis.HYPOTHETICAL
    assert assessment_track(original).track is Track.UNDETERMINED


def test_c6_pending_plan_does_not_block_location_and_assignment_is_not_split():
    loc = location()
    pending = PlanAssignment(loc.reach, "1", PlanStatus.PENDING, None, "plan not adopted")
    assigned = replace(pending, version="2", status=PlanStatus.ADOPTED, plan_unit=PlanUnit("plan-unit", "1"))
    assert assigned.reach == pending.reach == loc.reach
    assert loc == location()
    assert hash(loc) == hash(location())
    assert PreparedMapping("1", (loc.reach,), (loc,)).locations == (loc,)
    split = Reach("new-reach", "2", loc.reach.water_body, (loc.reach,))
    assert split.predecessors == (loc.reach,)
    assert replace(loc, reach=split) != loc
    assert pending.plan_unit is None


def test_boundary_change_cannot_reuse_identifier():
    reach = location().reach
    with pytest.raises(ValueError, match="new reach identifier"):
        Reach(reach.identifier, "2", reach.water_body, (reach,))


def test_multiple_and_shared_sections_only_when_declared():
    first = location()
    second = replace(first, section=CalculationSection("second", "1"))
    other = replace(first, reach=Reach("other", "1", first.reach.water_body))
    with pytest.raises(ValueError, match="declared exactly"):
        PreparedMapping("1", (first.reach, other.reach), (first, second, other))
    mapping = PreparedMapping(
        "1",
        (first.reach, other.reach),
        (first, second, other),
        shared_sections=(first.section,),
        multiple_section_reaches=(first.reach,),
    )
    assert mapping.locations == (first, second, other)


def test_observation_and_compliance_are_distinct_even_when_colocated():
    section = location().section
    gauge = ObservationPoint("point", "1", section)
    control = CompliancePoint("point", "1", section, "designation-act-1")
    assert gauge != control
    assert gauge.section == control.section
    with pytest.raises(ValueError):
        CompliancePoint("point", "1", section, "")


def test_model_mapping_retains_physical_identity_and_owner():
    loc = location()
    output = ModelLocation(loc, "model", "1", "outlet", "channel-routing")
    mapping = PreparedMapping("1", (loc.reach,), (loc,), model_locations=(output,))
    assert mapping.model_locations[0].location == loc
    assert mapping.model_locations[0].process_owner == "channel-routing"
    with pytest.raises(ValueError, match="undeclared physical"):
        replace(mapping, model_locations=(replace(output, location=replace(loc, mapping_version="2")),))


@pytest.mark.parametrize(
    "change",
    [
        {"reaches": ()},
        {"locations": ()},
        {"version": "2"},
        {"reaches": (Reach("missing", "1", WaterBody("river", "1")),)},
    ],
)
def test_invalid_mapping_declarations_fail(change):
    loc = location()
    with pytest.raises(ValueError):
        replace(PreparedMapping("1", (loc.reach,), (loc,)), **change)


def test_duplicate_and_spurious_declarations_fail():
    loc = location()
    with pytest.raises(ValueError, match="Duplicate"):
        PreparedMapping("1", (loc.reach,), (loc, loc))
    with pytest.raises(ValueError, match="declared exactly"):
        PreparedMapping("1", (loc.reach,), (loc,), shared_sections=(loc.section,))


def test_identity_requires_versions_and_cannot_mutate():
    with pytest.raises(ValueError):
        WaterBody("river", "")
    loc = location()
    assert replace(loc, mapping_version="2") != loc
    assert replace(loc, section=replace(loc.section, version="2")) != loc
    with pytest.raises(FrozenInstanceError):
        loc.mapping_version = "changed"  # ty: ignore[invalid-assignment]


def test_inconsistent_assignment_and_designation_fail():
    loc = location()
    with pytest.raises(ValueError):
        PlanAssignment(loc.reach, "1", PlanStatus.PENDING, PlanUnit("plan", "1"), "source")
    with pytest.raises(ValueError):
        PlanAssignment(loc.reach, "1", PlanStatus.ADOPTED, None, "source")
    with pytest.raises(ValueError):
        replace(classification(Origin.NATURAL, UseCategory.FISHERIES), designation_eligibility=Eligibility.ACCEPTED)
