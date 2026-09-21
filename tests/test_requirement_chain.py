"""U9 : CompleteSyntheticReferences × ScenarioProfile → ExpectedUncappedRequirement.

Numerical witnesses derive from the held synthetic_chain.json at stored precision.
Absolute tolerance 5e-12 m3/s covers binary log/normal inversion differences only.
Acceptance and physical relations are explicit synthetic assumptions, not policy.
"""

from dataclasses import replace
from datetime import timedelta
from fractions import Fraction
from typing import TypedDict

import pytest

from examples.requirement_chain import (
    TARGET,
    final_physics,
    quality,
    reference_patterns,
    wetland_step,
)
from fishy.daily_patterns import Extrapolation
from fishy.evidence import CheckFinding, Completeness
from fishy.quality_activation import ComponentStatus, QualityRoute
from fishy.quantities import Flow
from fishy.receptor_delivery import assess_delivery, delivery_scope
from fishy.time import Interval

TOLERANCE = 5e-12


# Derived test constants only; no private chapter or original fixture is copied.
class ReferenceWitness(TypedDict):
    wet: str
    dry: str
    magnitudes: tuple[float, ...]


EXPECTED: dict[str, ReferenceWitness] = {
    "A": {
        "wet": "13.498588075760033",
        "dry": "7.4081822068171785",
        "magnitudes": (10.000000000000002, 8.168115064021551, 6.808144549396242, 5.6879335534436075, 4.976270579072646),
    },
    "B": {
        "wet": "20.24788211364005",
        "dry": "11.112273310225769",
        "magnitudes": (15.000000000000007, 12.252172596032329, 10.212216824094366, 8.53190033016541, 7.464405868608971),
    },
}


@pytest.fixture(scope="module")
def prepared():
    return {member: reference_patterns(member, values["wet"], values["dry"]) for member, values in EXPECTED.items()}


def test_u9_real_annual_statistics_and_patterns_complete_calendar(prepared):
    for member, (reference, years, patterns) in prepared.items():
        assert tuple(y.calendar.year for y in years) == (2001, 2002)
        assert all(len(y.samples) == 365 for y in years)
        assert tuple(float(s.value.value) for s in reference.observations) == pytest.approx(
            (float(EXPECTED[member]["wet"]), float(EXPECTED[member]["dry"])), abs=TOLERANCE, rel=0
        )
        assert tuple(float(p.magnitude.value.value) for p in patterns.values()) == pytest.approx(
            EXPECTED[member]["magnitudes"], abs=TOLERANCE, rel=0
        )
        for pattern in patterns.values():
            assert pattern.shape == (Fraction(1),) * 365
            assert len(pattern.samples) == 365
            assert pattern.use_checks.finding is CheckFinding.PASS
            assert pattern.profile.band == 1
            assert pattern.membership.source_count == pattern.membership.climate_cluster_count == 2
        assert patterns[99].membership.shape_extrapolation is Extrapolation.OUTSIDE_SUPPORT


def test_u9_quality_and_candidate_bound_physical_relations():
    period = Interval(TARGET.interval.start, TARGET.interval.start + timedelta(days=1))
    q = quality(Flow(8), period, "A")
    assert q.quality.quality_total == Flow(9)
    assert q.quality.candidate.arrival == Flow(8)
    assert q.combined == Flow(9)
    final_quality, mapping, study, hydraulic = final_physics(Flow(12), period, "selected", "candidate12")
    assert final_quality.combined == mapping.mapping.continuing == Flow(11)
    assert mapping.upstream == Flow(12)
    assert study.selection.selected_flow == Flow(12)
    assert study.responses[0].value.lower == 120
    assert hydraulic.state.value.lower == Fraction(6, 5)
    assert study.checks.finding is hydraulic.check.finding is CheckFinding.PASS
    _, _, failed_study, failed_hydraulic = final_physics(Flow(9), period, "selected", "candidate9")
    assert failed_study.checks.finding is failed_hydraulic.check.finding is CheckFinding.FAIL
    assert assess_delivery((wetland_step(period, "selected", "candidate12"),)).checks.finding is CheckFinding.PASS


def test_u9_quality_upper_bound_after_uplift_cannot_be_hidden():
    period = Interval(TARGET.interval.start, TARGET.interval.start + timedelta(days=1))
    # U9 also supports a configured lower concentration target: clean uplift
    # beyond total9 violates C>=1mg/l despite passing the original upper bound.
    from fishy.mixing import CheckOutcome, recheck_mixing
    from fishy.quality import Comparison

    q = quality(Flow(9), period, "A")
    original = q.quality
    # Derive original inputs from the returned solver record, not a canned flag.
    lower = replace(original.targets[0], operator=Comparison.GE)
    assert recheck_mixing(original.boundary, (lower,), Flow(8)).outcome is CheckOutcome.PASS
    assert recheck_mixing(original.boundary, (lower,), Flow(9)).outcome is CheckOutcome.FAIL


def test_u9_floor_only_and_known_failure_with_missing_component():
    period = Interval(TARGET.interval.start, TARGET.interval.start + timedelta(days=1))
    floor = quality(Flow(3), period, "A", route=QualityRoute.FLOOR_ONLY)
    assert floor.floor == Flow(9)
    assert floor.requirement is None
    assert floor.status is ComponentStatus.HYPOTHETICAL
    step = wetland_step(period, "selected", "failure-and-gap")
    salt = replace(step.processes[0].test, value=Fraction(1))
    from examples.requirement_chain import accepted_evidence

    failed = replace(
        step.processes[0],
        test=salt,
        evidence=accepted_evidence(delivery_scope(salt.context, salt), salt.context.provenance),
    )
    step = replace(
        step, required_processes=("salt", "unknown-temperature"), processes=(failed,), checking_evidence=None
    )
    step = replace(
        step,
        checking_evidence=accepted_evidence(
            delivery_scope(step.balance.context, step.checking_subject),
            replace(step.balance.context.provenance, source="independent exact synthetic audit"),
        ),
    )
    result = assess_delivery((step,))
    assert result.checks.finding is CheckFinding.FAIL
    assert result.checks.completeness is Completeness.INCOMPLETE


def test_u9_final_gate_executes_every_old_physical_boundary_and_binds_candidate():
    from examples.requirement_chain import final_assessment, samples
    from fishy.requirement_checks import assess_requirement

    sample = samples(TARGET, 12, "selected", "U")[0]
    result = final_assessment(sample)
    assert result.checks.finding is CheckFinding.PASS
    assert result.receptor.checks.finding is CheckFinding.PASS
    assert result.quality.total == Flow(11)
    assert result.mapping.upstream == sample.value
    assert result.study.selection.selected_flow == sample.value
    assert result.hydraulics.checks.finding is CheckFinding.PASS
    missing = assess_requirement(sample, result.required)
    assert missing.checks.finding is CheckFinding.UNKNOWN
    changed = replace(sample, value=Flow(13))
    # Candidate12 evidence cannot certify candidate13, even though both are feasible.
    with pytest.raises(ValueError, match="exact final candidate"):
        assess_requirement(changed, result.required, mapping=result.mapping)


def test_u9_independent_duty_does_not_need_entry_or_ecological_sizing():
    from examples.requirement_chain import independent_duty
    from fishy.quantities import Volume

    result = independent_duty()
    assert tuple(row.shortfall for row in result.intervals) == (Flow(Fraction(1, 2)), Flow(0))
    assert result.known_shortfall_volume == Volume(43200)
    assert tuple(row.obligation.sample.value for row in result.intervals) == (Flow(2), Flow(3))


@pytest.fixture(scope="module")
def chain(prepared):
    from examples.requirement_chain import run_chain

    return run_chain(prepared)


def test_u9_complete_uncapped_selected_chain_and_floor(chain):
    from fishy.requirement_family import SelectionBranch

    final = chain.final
    assert final.checks.finding is CheckFinding.PASS
    assert chain.selection.branch is SelectionBranch.UPPER
    assert float(chain.selection.maximum_spread) == pytest.approx(0.3703703703703707, abs=TOLERANCE, rel=0)
    expected = (16.000000000000007, 13.252172596032329, 12.112273310225769, 12.112273310225769)
    assert tuple(float(c.samples[0].value.value) for c in final.requirement.classes) == pytest.approx(
        expected, abs=TOLERANCE, rel=0
    )
    for cls, value in zip(final.requirement.classes, expected, strict=True):
        assert len(cls.samples) == 365
        assert tuple(float(s.value.value) for s in cls.samples) == pytest.approx((value,) * 365, abs=TOLERANCE, rel=0)
    assert float(final.floor.sample.value.value) == pytest.approx(12.112273310225769, abs=TOLERANCE, rel=0)
    assert final.invariant.crossings == ()
    from fishy.natural_routing import NaturalRoute

    assert len(final.constructions) == 2
    assert all(c.route.selected is NaturalRoute.BASELINE for c in final.constructions)
    assert all(c.route.highest_data_supported is NaturalRoute.BASELINE for c in final.constructions)
    assert all(c.checks.finding is CheckFinding.PASS for c in final.constructions)
    assert len(final.physical) == 1460
    assert all(item.result.checks.finding is CheckFinding.PASS for item in final.physical)
    assert all(item.result.quality.total.value == item.result.sample.value.value - 1 for item in final.physical)
    assert all(item.result.mapping.upstream == item.result.sample.value for item in final.physical)
    assert all(item.result.study.selection.selected_flow == item.result.sample.value for item in final.physical)
    for member, expected_threshold in (("A", 4.976270579072646), ("B", 7.464405868608971)):
        threshold = chain.thresholds[member]
        assert float(threshold.value.value) == pytest.approx(expected_threshold, abs=TOLERANCE, rel=0)
        assert tuple(float(q.value) for q in threshold.reference.values) == pytest.approx(
            (float(EXPECTED[member]["wet"]), float(EXPECTED[member]["dry"])), abs=TOLERANCE, rel=0
        )
        assert all(len(m.windows.windows) == 365 for m in threshold.reference.minima)
        assert len(chain.provisional[member]) == len(chain.member_duration[member]) == 4
        assert len(chain.member_physical[member]) == 1460
    assert len(final.duration) == 8
    assert all(len(a.result.comparisons) == 365 for a in final.duration)
    assert all(
        a.result.point.finding is a.result.uncertainty.finding is a.result.permission.finding is CheckFinding.PASS
        for a in final.duration
    )


def test_u9_complete_issued_dry_class_preserves_requirement_floor_and_shortfall(chain):
    from fishy.comparison_evidence import NumericalFinding

    final = chain.final
    assert len(chain.issued) == 365
    for issue, delivery in chain.issued:
        assert issue.obligation.sample.value == Flow(6)
        assert float(issue.ecological_deficit.value) == pytest.approx(6.112273310225769, abs=TOLERANCE, rel=0)
        assert delivery.raw_shortfall == Flow(1)
        assert delivery.numerical is NumericalFinding.BELOW
        assert delivery.official.finding is CheckFinding.UNKNOWN
        assert delivery.responsibility.finding is CheckFinding.UNKNOWN
        assert issue.requirement.sample.value == final.floor.sample.value
    assert sum(delivery.raw_shortfall_volume.value for _, delivery in chain.issued) == 365 * 86400


def test_u9_missing_predecessor_declines_whole_final_family(chain):
    from fishy.requirement_checks import FinalCondition
    from fishy.requirement_finalization import finalize_regime

    final = chain.final
    tests = tuple(item.test for item in final.duration)
    missing = replace(tests[0], predecessors=(), predecessor_basis=None)
    declined = finalize_regime(
        final.selection,
        final.method,
        tuple(FinalCondition),
        final.physical,
        duration_tests=(missing, *tests[1:]),
        expected_duration_tests=(("A", "annual7-T100"), ("B", "annual7-T100")),
        version="missing-context-v2",
        provenance=final.floor.sample.provenance,
        provisional=final.provisional,
        constructions=tuple(a.construction for a in final.constructions),
        member_physical=final.member_physical,
        member_duration_tests=tuple(a.test for a in final.member_duration),
    )
    assert declined.checks.finding is CheckFinding.UNKNOWN
    assert declined.floor is declined.requirement is None
    assert final.floor is not None
    assert declined.duration[0].result.point.completeness is Completeness.INCOMPLETE
    assert sum(c.point is CheckFinding.UNKNOWN for c in declined.duration[0].result.comparisons) == 6


def test_u9_final_floor_only_has_active_quality_without_baseline_gate(potential_example):
    from fishy.potential_requirements import PotentialRoute

    example = potential_example
    assert len(example.sources) == 365
    assert all(
        source.floor == Flow(3) and source.selected_route is PotentialRoute.HYDRAULIC for source in example.sources
    )
    assert all(source.routes[0].checks.finding is CheckFinding.UNKNOWN for source in example.sources)
    assert all(source.requirement_state == "pending_full_requirement" for source in example.sources)
    final = example.final
    assert final.checks.finding is CheckFinding.PASS
    assert tuple(floor.sample.value for floor in final.floors) == (Flow(9),) * 365
    assert len(final.physical) == len(final.member_physical) == 365
    assert len(final.constructions) == 1
    assert final.constructions[0].checks.finding is CheckFinding.PASS
    assert len(final.constructions[0].sources) == 365
    assert all(result.study.selection.selected_flow == Flow(9) for result in final.physical)
    assert not hasattr(final, "requirement") and not hasattr(final, "obligation")


def test_m1_seven_day_mean_pass_is_not_first_day_floor_pass(prepared):
    from examples.issued_duty import scenario_evidence
    from examples.requirement_chain import duration_threshold, samples, singleton, synthetic_acceptance
    from fishy.annual_statistics import ImportedDerivation
    from fishy.comparison_evidence import ButForFlow, MarginBounds, NumericalFinding
    from fishy.duration_minima import import_duration_threshold
    from fishy.duration_windows import WindowUncertaintySupport
    from fishy.duties import Delivery, Floor
    from fishy.floor_assessment import assess_floor
    from fishy.low_flow_frequency import LowFlowReturnPeriod
    from fishy.low_flow_safeguard import AssessmentStage, assess_low_flow
    from fishy.scientific_acceptance import UsePurpose

    # One explicit eligible seven-day window, not a miniature substitute for U9's full family.
    threshold = import_duration_threshold(
        duration_threshold("A", prepared["A"][1]).reference,
        LowFlowReturnPeriod(100),
        Flow(10),
        profile_version="M1-fixed-threshold-v1",
        derivation=ImportedDerivation(
            "q7,T100=10 by explicit synthetic assumption",
            "fixed fixture",
            "M1 supported scenario",
            ("not a fitted U9 estimate",),
            "no empirical validation claimed",
            "fixed synthetic support",
            "M1",
        ),
        uncertainty=singleton(Flow(10)),
    )
    series = tuple(
        replace(s, value=Flow(q), uncertainty=singleton(Flow(q)))
        for s, q in zip(samples(TARGET, 10, "A", "U")[:7], (4, 8, 12, 14, 12, 10, 10), strict=True)
    )
    result = assess_low_flow(
        series,
        series[-1].interval,
        threshold,
        stage=AssessmentStage.FINAL,
        candidate_basis="M1 observed-window-shape synthetic witness",
        provenance=series[0].provenance,
        predecessor_basis="all six preceding daily means explicitly supplied in the seven values",
        scientific_assessment=synthetic_acceptance(threshold.product(UsePurpose.SIZING)),
        uncertainty_support=WindowUncertaintySupport("fixed joint synthetic support", "M1", "singleton values"),
        purpose=UsePurpose.SIZING,
    )
    assert len(result.comparisons) == 1
    assert result.windows.minimum == Flow(10)
    assert result.checks.finding is CheckFinding.PASS
    first = series[0]
    floor = Floor(replace(first, value=Flow(6), uncertainty=None), "M1-floor-v1")
    actual = Delivery(first, "M1-actual-v1")
    but_for = ButForFlow(
        replace(first, value=Flow(8), uncertainty=singleton(Flow(8))), "M1-but-for-v1", "stipulated abstraction"
    )
    comparison = assess_floor(floor, actual, but_for, evidence=scenario_evidence(floor, actual, but_for))
    assert comparison.margin == MarginBounds(-2, -2)
    assert comparison.numerical is NumericalFinding.BELOW
    assert comparison.official.finding is comparison.responsibility.finding is CheckFinding.UNKNOWN
    assert floor.sample.value == Flow(6)


def test_u9_final_family_declines_quality_upper_flow_bound_after_selected_uplift(chain):
    from examples.requirement_chain import final_physics, wetland_step
    from fishy.quality import Comparison
    from fishy.quality_activation import apply_quality_component
    from fishy.requirement_checks import FinalCondition, assess_requirement, sample_subject
    from fishy.requirement_finalization import ClassAssessment, finalize_regime

    final = chain.final
    sample = final.physical[0].result.sample
    # Two actual original concentration tests jointly require total R=9.
    # The initial active candidate R9 passes; selected R15 must fail its lower test.
    q = quality(Flow(9), sample.interval, "selected")
    lower = replace(q.quality.targets[0], identifier="hypothetical-minimum-concentration", operator=Comparison.GE)
    constrained = apply_quality_component(
        q.base,
        q.quality.boundary,
        (*q.quality.targets, lower),
        q.activation,
        q.source_control,
        q.accounts,
        q.background_mapping,
    )
    assert constrained.status is ComponentStatus.HYPOTHETICAL
    assert constrained.combined == Flow(9)
    candidate = sample_subject(sample)
    _, mapping, study, hydraulic = final_physics(sample.value, sample.interval, "selected", candidate)
    failed = assess_requirement(
        sample,
        tuple(FinalCondition),
        quality=constrained,
        mapping=mapping,
        receptor=wetland_step(sample.interval, "selected", candidate),
        hydraulic_required=(hydraulic.criterion.scope,),
        hydraulic_components=(hydraulic,),
        study_selection=study.selection,
        study_relations=tuple(r.relation for r in study.responses),
    )
    assert failed.checks.finding is CheckFinding.FAIL
    assert failed.mapping is not None and failed.receptor is not None
    assert failed.mapping.upstream == sample.value
    assert failed.receptor.checks.finding is CheckFinding.PASS
    declined = finalize_regime(
        final.selection,
        final.method,
        tuple(FinalCondition),
        (ClassAssessment(final.physical[0].design, failed), *final.physical[1:]),
        duration_tests=tuple(a.test for a in final.duration),
        expected_duration_tests=(("A", "annual7-T100"), ("B", "annual7-T100")),
        version="quality-conflict-v2",
        provenance=final.floor.sample.provenance,
        provisional=final.provisional,
        constructions=tuple(a.construction for a in final.constructions),
        member_physical=final.member_physical,
        member_duration_tests=tuple(a.test for a in final.member_duration),
    )
    assert declined.checks.finding is CheckFinding.FAIL
    assert declined.requirement is declined.floor is None
    assert final.floor.sample.value == chain.issued[0][0].requirement.sample.value


@pytest.fixture(scope="module")
def potential_example():
    from examples.requirement_chain import floor_only_example

    return floor_only_example()


@pytest.mark.parametrize("broken", ("missing-source", "natural-origin", "changed-source-flow"))
def test_u9_potential_floor_source_proof_cannot_be_omitted_or_relabelled(potential_example, broken):
    from fishy.requirement_finalization import finalize_floors
    from fishy.spatial import Origin

    final = potential_example.final
    construction = final.constructions[0].construction
    first = construction.components[0]
    if broken == "missing-source":
        constructions = ()
        expected = CheckFinding.UNKNOWN
    else:
        source = first.source
        if broken == "natural-origin":
            source = replace(source, classification=replace(source.classification, origin=Origin.NATURAL))
        else:
            source = replace(
                source,
                hydraulics=replace(
                    source.hydraulics, selection=replace(source.hydraulics.selection, selected_flow=Flow(4))
                ),
            )
        changed = replace(first, source=source)
        constructions = (replace(construction, components=(changed, *construction.components[1:])),)
        expected = CheckFinding.FAIL
    result = finalize_floors(
        final.selection,
        final.physical[0].required,
        final.physical,
        version="rejected-potential-v2",
        constructions=constructions,
        member_physical=final.member_physical,
    )
    assert result.checks.finding is expected
    assert result.floors == ()
    assert len(final.floors) == 365
    assert all(floor.sample.value == Flow(9) for floor in final.floors)
