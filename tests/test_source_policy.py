"""Actual source policy cannot drift behind common configuration labels."""

from dataclasses import replace
from fractions import Fraction

import pytest
from test_requirement_finalization import inputs

from fishy.design_conditions import DesignClass
from fishy.evidence import CheckFinding
from fishy.natural_baseline import AdvisorySpawning, ReachCoefficients, RiverRegulation, WinterProvision
from fishy.quality_activation import ActivationMode
from fishy.quantities import Flow
from fishy.source_policy import floor_policy_checks, source_policy_checks


@pytest.fixture(scope="module")
def sources():
    return tuple(c.source for c in inputs(ActivationMode.HYPOTHETICAL)[3])


def test_reference_members_and_scientific_data_are_not_policy(sources):
    assert sources[0].provenance != sources[1].provenance
    assert source_policy_checks(sources).finding is CheckFinding.PASS


@pytest.mark.parametrize("field", ("alpha", "winter", "spawning"))
def test_actual_baseline_coefficients_are_policy_even_with_same_version(sources, field):
    source = sources[0]
    calendar = source.result.inputs.patterns[0].calendar
    policy = {
        "alpha": ReachCoefficients(tuple((c, Fraction(1, 2)) for c in DesignClass), "qualified", "different policy"),
        "winter": WinterProvision(
            RiverRegulation.REGULATED_NATURAL, Flow(2), Fraction(1, 4), "different share", "supported reference"
        ),
        "spawning": AdvisorySpawning((Fraction(2),) * calendar.days, calendar, "different timing", "different policy"),
    }[field]
    changed = replace(source, result=replace(source.result, inputs=replace(source.result.inputs, **{field: policy})))
    assert changed.profile_version == source.profile_version
    assert source_policy_checks((source, changed)).finding is CheckFinding.FAIL


def test_actual_scientific_acceptance_threshold_is_not_just_profile_name(sources):
    source = sources[0]
    first, *rest = source.result.inputs.patterns
    assessment = first.magnitude_assessment
    assert assessment is not None
    record = replace(
        assessment.record, criteria=tuple(replace(c, limit=c.limit + 1) for c in assessment.record.criteria)
    )
    changed_pattern = replace(first, magnitude_assessment=replace(assessment, record=record))
    changed = replace(
        source, result=replace(source.result, inputs=replace(source.result.inputs, patterns=(changed_pattern, *rest)))
    )
    assert source_policy_checks((source, changed)).finding is CheckFinding.FAIL


def without_assessment(source):
    first, *rest = source.result.inputs.patterns
    return replace(
        source,
        result=replace(
            source.result,
            inputs=replace(
                source.result.inputs,
                patterns=(replace(first, magnitude_assessment=None, magnitude_evidence=None), *rest),
            ),
        ),
    )


def test_missing_scientific_assessment_is_unknown_not_policy_drift(sources):
    result = source_policy_checks((sources[0], without_assessment(sources[1])))
    assert result.finding is CheckFinding.UNKNOWN
    assert not any(c.finding is CheckFinding.FAIL for c in result.checks)


def test_known_alpha_drift_survives_missing_scientific_assessment(sources):
    missing = without_assessment(sources[1])
    changed = replace(
        missing,
        result=replace(
            missing.result,
            inputs=replace(
                missing.result.inputs,
                alpha=ReachCoefficients(
                    tuple((c, Fraction(1, 2)) for c in DesignClass), "qualified", "different policy"
                ),
            ),
        ),
    )
    result = source_policy_checks((sources[0], changed))
    assert result.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks)
    assert any(c.finding is CheckFinding.FAIL and "alpha" in c.check_id for c in result.checks)


@pytest.fixture(scope="module")
def floor_source():
    from examples.graduated_entry import supplied_entry
    from fishy.floor_construction import EntryFloorSource
    from fishy.graduated_entry import evaluate_graduated_entry

    route = inputs(ActivationMode.HYPOTHETICAL)[3][0].route
    assert route is not None
    return EntryFloorSource(evaluate_graduated_entry(*supplied_entry()), route)


@pytest.mark.parametrize("missing", ("curve", "screen"))
def test_missing_floor_component_is_unknown(floor_source, missing):
    changed = replace(floor_source, result=replace(floor_source.result, **{missing: None}))
    assert floor_policy_checks((floor_source, changed)).finding is CheckFinding.UNKNOWN


def test_changed_known_screen_survives_missing_curve(floor_source):
    screen = floor_source.result.screen
    assert screen is not None
    changed = replace(
        floor_source, result=replace(floor_source.result, curve=None, screen=replace(screen, minimum_input=Flow(200)))
    )
    result = floor_policy_checks((floor_source, changed))
    assert result.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks)
    assert any(c.finding is CheckFinding.FAIL and "screen" in c.check_id for c in result.checks)


def test_missing_presumptive_profile_is_unknown(sources, floor_source):
    from fishy.floor_construction import PresumptiveFloorSource
    from fishy.presumptive_floor import (
        PresumptiveProfile,
        SeasonalFraction,
        presumptive_floor,
        presumptive_reference_identity,
    )

    pattern = sources[0].result.inputs.patterns[0]
    profile = PresumptiveProfile(
        "test",
        "natural pattern",
        presumptive_reference_identity(pattern),
        (SeasonalFraction("year", 0, pattern.calendar.days, Fraction(1, 2)),),
        "hypothetical",
        "fixed",
    )
    source = PresumptiveFloorSource(presumptive_floor(pattern, profile), floor_source.route)
    missing = replace(source, result=replace(source.result, profile=None))
    assert floor_policy_checks((source, missing)).finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize("left,right", ((1, 1.0), (0.0, -0.0)))
def test_equal_scientific_numeric_limits_are_same_policy(sources, left, right):
    source = sources[0]
    first, *rest = source.result.inputs.patterns
    assessment = first.magnitude_assessment
    assert assessment is not None

    def with_limit(value):
        record = replace(assessment.record, criteria=tuple(replace(c, limit=value) for c in assessment.record.criteria))
        pattern = replace(first, magnitude_assessment=replace(assessment, record=record))
        return replace(
            source, result=replace(source.result, inputs=replace(source.result.inputs, patterns=(pattern, *rest)))
        )

    assert source_policy_checks((with_limit(left), with_limit(right))).finding is CheckFinding.PASS


def test_unresolved_unused_habitat_does_not_gate_supported_hydraulic_policy():
    from datetime import date

    from examples.requirement_chain import TARGET, potential_study, provenance
    from examples.study_requirements import POTENTIAL
    from fishy.evidence import ReferenceKind
    from fishy.floor_construction import PotentialFloorSource, assess_floor_source
    from fishy.potential_requirements import Applicability, PotentialFloorResult, PotentialRoute, PotentialStudy
    from fishy.study_requirements import StudyNeed

    selected, relations, _, _ = potential_study(
        Flow(3),
        TARGET.interval,
        replace(provenance("potential"), reference_kind=ReferenceKind.MANAGED),
        "policy-hydraulic",
    )
    source = PotentialFloorSource(
        selected.scope,
        POTENTIAL,
        PotentialStudy(Applicability.UNRESOLVED, "habitat study pending", None, ()),
        PotentialStudy(Applicability.APPLICABLE, "supported hydraulic fallback", selected, relations),
        None,
        StudyNeed("remaining habitat study", "review owner", date(2027, 1, 1)),
    )
    result, _ = assess_floor_source(source)
    assert isinstance(result, PotentialFloorResult)
    assert result.selected_route is PotentialRoute.HYDRAULIC
    assert result.routes[0].checks.finding is CheckFinding.UNKNOWN
    assert floor_policy_checks((source,)).finding is CheckFinding.PASS
