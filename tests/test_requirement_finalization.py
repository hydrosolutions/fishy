"""M11/M15 and U7: completed family gates retain failure, coverage and immutable candidates."""

from dataclasses import replace
from datetime import timedelta
from fractions import Fraction
from functools import lru_cache

import pytest

from examples.requirement_chain import (
    TARGET,
    accepted_evidence,
    provenance,
    quality,
    safeguard,
    samples,
    singleton,
    synthetic_acceptance,
)
from fishy.annual_statistics import ImportedDerivation, TrendTreatment
from fishy.duration_minima import construct_duration_reference, import_duration_threshold
from fishy.duration_windows import DurationWindowRule, WindowDomain, WindowUncertaintySupport
from fishy.evidence import CheckFinding, Completeness
from fishy.low_flow_frequency import LowFlowReturnPeriod
from fishy.low_flow_safeguard import AssessmentStage, CandidateReferenceRelation
from fishy.natural_baseline import EcologicalRegimeMethod, RecordedMinimum, baseline_family, recorded_minimum_product
from fishy.quality_activation import ActivationMode
from fishy.quantities import Flow
from fishy.requirement_checks import FinalCondition, assess_requirement
from fishy.requirement_composition import compose_requirement
from fishy.requirement_construction import BaselineSource, ClassComposition, MemberConstruction
from fishy.requirement_family import (
    ClassRequirement,
    FamilyBasis,
    ReconstructionNeed,
    RequirementFamily,
    RequirementMember,
    SelectionSpecification,
    assess_selected_family,
    candidate_scope,
)
from fishy.requirement_finalization import ClassAssessment, DurationTest, MemberPhysical, finalize_regime
from fishy.scientific_acceptance import UsePurpose
from fishy.time import Interval

REQUIRED = (FinalCondition.QUALITY,)
SUPPORT = WindowUncertaintySupport(
    "fixed synthetic joint enclosing support", "fixture", "singleton assumptions, no independence claim"
)


def threshold(member, value=10):
    from fishy.pattern_calendar import AccountingYear

    rule = DurationWindowRule(7, WindowDomain.ANNUAL, 1, 0, None, "configured synthetic annual seven-day rule")
    reference_samples = samples(AccountingYear(2001, 1, 0), 10, member)
    first = reference_samples[0]
    prefix = tuple(
        replace(
            first,
            interval=Interval(first.interval.start - timedelta(days=i), first.interval.start - timedelta(days=i - 1)),
        )
        for i in range(6, 0, -1)
    )
    reference = construct_duration_reference(
        (*prefix, *reference_samples),
        AccountingYear(2001, 1, 0).interval,
        rule,
        location=first.location,
        provenance=first.provenance,
        predecessor_basis="explicit six constant synthetic reference days",
        climate_basis="synthetic common climate",
        trend=TrendTreatment.COMMON_CLIMATE,
        climate_evidence="stipulated common climate",
        dependence="fixed scenario values; dependence not inferred",
    )
    derivation = ImportedDerivation(
        "hypothetical supplied threshold",
        "synthetic",
        "full reference year",
        ("not basin validation",),
        "none claimed",
        "supported fixed value",
        "D.5 M11/M15",
    )
    return import_duration_threshold(
        reference,
        LowFlowReturnPeriod(2),
        Flow(value),
        profile_version="synthetic-threshold-v1",
        derivation=derivation,
        uncertainty=singleton(Flow(value)),
    )


@lru_cache
def source_baseline(member):
    from fishy.annual_statistics import (
        AnnualEstimator,
        AnnualReference,
        ExceedanceProbability,
        annual_mean,
        import_annual_estimate,
    )
    from fishy.daily_patterns import DailyReferenceYear, annual_magnitude_product, import_pattern, pattern_product
    from fishy.evidence import Check, CheckSummary
    from fishy.pattern_calendar import AccountingYear

    calendar = AccountingYear(2001, 1, 0)
    source_samples = samples(calendar, 8, member)
    year = DailyReferenceYear(
        calendar,
        source_samples,
        "fixed-synthetic-year",
        CheckSummary((Check("fixed", CheckFinding.PASS, ("stipulated fixed full synthetic reference",)),)),
    )
    reference = AnnualReference(
        (annual_mean(source_samples, accounting_start_month=1, utc_offset_minutes=0, provenance=provenance(member)),),
        calendar.interval,
        "fixed-common-climate",
        1,
        0,
        (),
        TrendTreatment.COMMON_CLIMATE,
        "synthetic common-climate support",
    )
    derivation = ImportedDerivation(
        "fixed8 quantiles and shape",
        "synthetic imported constant distribution",
        "complete daily reference year",
        ("not field validation",),
        "hypothetical rare shape support",
        "supported exact synthetic values",
        "M11 final-gate fixture",
    )
    patterns = []
    for probability in (50, 75, 90, 97, 99):
        annual = import_annual_estimate(
            reference,
            ExceedanceProbability(Fraction(probability, 100)),
            Flow(8),
            estimator=AnnualEstimator.IMPORTED_STATIONARY,
            profile_version="fixed-distribution-v1",
            provenance=provenance(member),
            derivation=derivation,
        )
        annual_acceptance = synthetic_acceptance(
            annual_magnitude_product(annual, intended_use="sizing", purpose=UsePurpose.SIZING)
        )
        imported = import_pattern(
            annual,
            TARGET,
            samples(TARGET, 8, member),
            derivation,
            intended_use="sizing",
            purpose=UsePurpose.SIZING,
            magnitude_assessment=annual_acceptance,
        )
        pattern_acceptance = synthetic_acceptance(
            pattern_product(imported, intended_use="sizing", purpose=UsePurpose.SIZING)
        )
        patterns.append(
            import_pattern(
                annual,
                TARGET,
                samples(TARGET, 8, member),
                derivation,
                intended_use="sizing",
                purpose=UsePurpose.SIZING,
                magnitude_assessment=annual_acceptance,
                shape_assessment=pattern_acceptance,
            )
        )
    recorded = RecordedMinimum(reference, (year,), "complete no infill", "supported fixed synthetic values")
    recorded = replace(
        recorded,
        assessment=synthetic_acceptance(
            recorded_minimum_product(recorded, intended_use="sizing", purpose=UsePurpose.SIZING)
        ),
    )
    return baseline_family(
        tuple(patterns), recorded, provenance=provenance(member), profile_version="constant-baseline-v1"
    )


def route_inputs(baseline):
    from fishy.evidence import Check
    from fishy.natural_routing import (
        Availability,
        NaturalRoute,
        ScopedRequirement,
        TierEvidence,
        reconstruction_disclosure_scope,
    )
    from fishy.requirement_construction import NaturalRouteInputs
    from fishy.spatial import (
        ClassificationBasis,
        DesignationState,
        Eligibility,
        Origin,
        PreparedClassification,
        UseCategory,
    )

    patterns = baseline.inputs.patterns
    reference = patterns[0].magnitude.reference
    disclosure = reconstruction_disclosure_scope(reference)
    classification = PreparedClassification(
        Origin.NATURAL,
        DesignationState.NONE,
        Eligibility.NOT_APPLICABLE,
        UseCategory.AGRICULTURE_IRRIGATION,
        ("irrigation",),
        "explicit synthetic natural origin/no designation",
        "v1",
        ClassificationBasis.HYPOTHETICAL,
    )
    tier = TierEvidence(
        NaturalRoute.BASELINE,
        patterns[0].location,
        "synthetic-eligibility-v1",
        Availability.AVAILABLE,
        Availability.AVAILABLE,
        Check("priority", CheckFinding.UNKNOWN, ("no top-tier priority assumed",)),
        ("reconstruction_disclosure",),
        (),
        (
            ScopedRequirement(
                "reconstruction_disclosure", disclosure, accepted_evidence(disclosure, reference.provenance)
            ),
        ),
        (),
        "fixed supplied eligible baseline",
        patterns,
        baseline.inputs.recorded,
    )
    return NaturalRouteInputs(patterns[0].location, classification, (tier,))


def quality_family(member, mode):
    baseline = source_baseline(member)
    classes = []
    records = []
    for cls in baseline.candidate.classes:
        composed = []
        for sample in cls.samples:
            q = quality(
                sample.value, sample.interval, member, background_concentration=Fraction(1, 100), activation_mode=mode
            )
            result = compose_requirement(sample, provenance(member), quality=q)
            assert result.candidate is not None
            records.append(ClassComposition(cls.design, result))
            composed.append(replace(result.candidate, uncertainty=singleton(result.candidate.value)))
        classes.append(ClassRequirement(cls.design, tuple(composed)))
    first = classes[0].samples[0]
    assert first.provenance.reference_kind is not None
    basis = FamilyBasis(
        first.location,
        TARGET.interval,
        first.provenance.scenario,
        EcologicalRegimeMethod.BASELINE.value,
        first.provenance.configuration_version,
        "hypothetical-quality" if mode is ActivationMode.HYPOTHETICAL else "advisory-quality",
        first.provenance.reference_kind,
    )
    family = RequirementFamily(basis, tuple(classes))
    construction = MemberConstruction(
        member,
        BaselineSource(baseline, provenance(member), "constant-baseline-v1"),
        tuple(records),
        route_inputs(baseline),
    )
    return family, construction


def select(families):
    members = tuple(
        RequirementMember(
            name,
            name,
            f,
            accepted_evidence(candidate_scope(f), f.classes[0].samples[0].provenance),
            "two stipulated structures; common fixed scenario",
        )
        for name, f in families
    )
    f = members[0].candidate
    assert isinstance(f, RequirementFamily)
    selected = replace(
        f,
        classes=tuple(
            replace(c, samples=tuple(replace(s, provenance=provenance("selected"), components=()) for s in c.samples))
            for c in f.classes
        ),
    )
    return assess_selected_family(
        members,
        selected,
        SelectionSpecification(
            tuple(m.identifier for m in members), (), Fraction(1, 5), ReconstructionNeed.REQUIRED, "synthetic theta"
        ),
    )


def inputs(mode):
    prepared = tuple((m, quality_family(m, mode)) for m in ("A", "B"))
    selection = select(tuple((m, pair[0]) for m, pair in prepared))
    constructions = tuple(pair[1] for _, pair in prepared)
    selected = selection.supplied
    physical = tuple(
        ClassAssessment(
            c.design,
            assess_requirement(
                s,
                REQUIRED,
                quality=quality(
                    Flow(8), s.interval, "selected", background_concentration=Fraction(1, 100), activation_mode=mode
                ),
            ),
        )
        for c in selected.classes
        for s in c.samples
    )
    tests = []
    for member in ("A", "B"):
        t = threshold(member)
        for cls in selected.classes:
            first = cls.samples[0]
            prefix = tuple(
                replace(
                    first,
                    interval=Interval(
                        first.interval.start - timedelta(days=i), first.interval.start - timedelta(days=i - 1)
                    ),
                )
                for i in range(6, 0, -1)
            )
            tests.append(
                DurationTest(
                    "annual7",
                    member,
                    cls.design,
                    t,
                    prefix,
                    "explicit supported synthetic precursor",
                    synthetic_acceptance(t.product(UsePurpose.SIZING)),
                    SUPPORT,
                    CandidateReferenceRelation(
                        first.provenance, t.reference.identity, "selected family against retained reference"
                    ),
                    t.product(UsePurpose.SIZING).purpose,
                )
            )
    return selection, physical, tuple(tests), constructions


def finish(
    selection, physical, tests, constructions=(), *, expected=(("A", "annual7"), ("B", "annual7")), provisional=()
):
    member_physical = []
    member_tests = []
    sources = {c.member: c for c in constructions}
    for member in selection.members:
        if member.identifier in sources:
            originals = {(c.design, c.result.base.interval): c.result for c in sources[member.identifier].compositions}
            for cls in member.candidate.classes:
                for sample in cls.samples:
                    original = originals[(cls.design, sample.interval)]
                    assessment = assess_requirement(sample, REQUIRED, quality=original.quality)
                    member_physical.append(MemberPhysical(member.identifier, ClassAssessment(cls.design, assessment)))
        for test in tests:
            if test.member != member.identifier:
                continue
            first = member.candidate.samples(test.design)[0]
            prefix = tuple(
                replace(
                    first,
                    interval=Interval(
                        first.interval.start - timedelta(days=i), first.interval.start - timedelta(days=i - 1)
                    ),
                )
                for i in range(6, 0, -1)
            )
            member_tests.append(replace(test, predecessors=prefix, reference_relation=None))
    return finalize_regime(
        selection,
        EcologicalRegimeMethod.BASELINE,
        REQUIRED,
        physical,
        duration_tests=tests,
        expected_duration_tests=expected,
        version="new-synthetic-v1",
        provenance=provenance("selected"),
        provisional=provisional,
        constructions=constructions,
        member_physical=tuple(member_physical),
        member_duration_tests=tuple(member_tests),
    )


@pytest.fixture(scope="module")
def active_inputs():
    return inputs(ActivationMode.HYPOTHETICAL)


def test_m11_actual_active_quality_repairs_final_not_provisional(active_inputs):
    selection, physical, tests, constructions = active_inputs
    t = threshold("A")
    provisional = safeguard(samples(TARGET, 8, "A"), t, stage=AssessmentStage.PROVISIONAL)
    assert provisional.point.finding is CheckFinding.FAIL
    assert all(c.shortfall == Flow(2) for c in provisional.comparisons)
    result = finish(selection, physical, tests, constructions, provisional=(provisional,))
    assert result.checks.finding is CheckFinding.PASS
    assert result.floor.sample.value == Flow(10)
    assert result.provisional[0].point.finding is CheckFinding.FAIL
    assert all(len(d.result.comparisons) == 365 for d in result.duration)
    assert result.route_failure is None


def test_m11_advisory_quality_cannot_repair_final_gate():
    selection, physical, tests, constructions = inputs(ActivationMode.ADVISORY)
    result = finish(selection, physical, tests, constructions)
    assert result.checks.finding is CheckFinding.FAIL
    assert result.requirement is result.floor is None
    assert result.invariant.candidate == Flow(8)
    assert result.route_failure.finding is CheckFinding.FAIL
    assert all(d.result.point.finding is CheckFinding.FAIL for d in result.duration)


def test_m15_known_failed_test_plus_missing_class_keeps_failure_and_incompleteness(active_inputs):
    selection, physical, tests, constructions = active_inputs
    raised = threshold("A", 11)
    changed = tuple(
        replace(
            test,
            threshold=raised,
            scientific_assessment=synthetic_acceptance(raised.product(UsePurpose.SIZING)),
            reference_relation=CandidateReferenceRelation(
                provenance("selected"), raised.reference.identity, "changed configured threshold"
            ),
        )
        if test.member == "A"
        else test
        for test in tests
    )
    result = finish(selection, physical, (changed[0], *changed[2:]), constructions)
    assert result.checks.finding is CheckFinding.FAIL
    assert result.checks.completeness is Completeness.INCOMPLETE
    assert result.requirement is result.floor is None
    assert result.duration[0].result.comparisons[0].shortfall == Flow(1)


def test_missing_baseline_manifest_and_exact_method_cannot_bypass_gate(active_inputs):
    selection, physical, _, constructions = active_inputs
    result = finish(selection, physical, (), constructions, expected=())
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.floor is None
    with pytest.raises(ValueError, match="immutable method"):
        finalize_regime(
            selection,
            EcologicalRegimeMethod.TRANSFER,
            REQUIRED,
            physical,
            duration_tests=(),
            expected_duration_tests=(),
            version="v1",
            provenance=provenance("selected"),
        )


def test_stale_class_assessment_and_prefix_overwrite_refused(active_inputs):
    selection, physical, tests, constructions = active_inputs
    changed = replace(
        physical[0],
        result=replace(physical[0].result, sample=replace(physical[0].result.sample, value=Flow(12), uncertainty=None)),
    )
    with pytest.raises(ValueError, match="different class/day"):
        finish(selection, (changed, *physical[1:]), tests, constructions)
    bad = replace(tests[0], predecessors=(selection.supplied.classes[0].samples[0],))
    with pytest.raises(ValueError, match="cannot replace"):
        finish(selection, physical, (bad, *tests[1:]), constructions)


def test_failed_family_invokes_eligible_descent_without_repair(active_inputs):
    from test_natural_routing import natural, tier

    from fishy.natural_routing import NaturalRoute, select_natural_route

    selection, physical, _, constructions = active_inputs
    declined = finish(selection, physical, (), constructions, expected=())
    baseline = tier()
    entry = tier(NaturalRoute.ENTRY)
    routed = select_natural_route(natural(), (baseline, entry), (declined.route_failure,))
    assert routed.selected is NaturalRoute.ENTRY
    assert routed.failures == (declined.route_failure,)
    assert declined.requirement is declined.floor is None
    assert declined.invariant.candidate == Flow(10)


def test_changed_source_cannot_hide_behind_exact_final_candidate_acceptance(active_inputs):
    selection, physical, tests, constructions = active_inputs
    original = constructions[0]
    source = original.source
    changed = replace(source, result=replace(source.result, inputs=replace(source.result.inputs, recorded=None)))
    forged = replace(original, source=changed)
    result = finish(selection, physical, tests, (forged, *constructions[1:]))
    assert result.checks.finding is CheckFinding.FAIL
    assert result.floor is result.requirement is None
    assert any(
        c.check_id.endswith("source_result_binding") and c.finding is CheckFinding.FAIL for c in result.checks.checks
    )


def test_active_uplift_and_passing_safeguard_cannot_repair_crossed_natural_bounds(active_inputs):
    from fishy.natural_baseline import RiverRegulation, WinterProvision, winter_scope

    selection, physical, tests, constructions = active_inputs
    original = constructions[0]
    source = original.source
    first = source.result.inputs.patterns[0]
    winter = WinterProvision(
        RiverRegulation.REGULATED_NATURAL,
        Flow(10),
        Fraction(9, 10),
        "hypothetical adoption",
        "fixed supported reference",
    )
    winter = replace(
        winter,
        findings=accepted_evidence(
            winter_scope(winter, first.location, first.calendar, source.provenance, first.requested_use),
            source.provenance,
        ),
    )
    failed = baseline_family(
        source.result.inputs.patterns,
        source.result.inputs.recorded,
        provenance=source.provenance,
        profile_version=source.profile_version,
        winter=winter,
    )
    assert failed.candidate is None
    assert failed.checks.finding is CheckFinding.FAIL
    altered = replace(original, source=replace(source, result=failed))
    result = finish(selection, physical, tests, (altered, *constructions[1:]))
    assert all(d.result.checks.finding is CheckFinding.PASS for d in result.duration)
    assert result.checks.finding is CheckFinding.FAIL
    assert result.floor is None


def test_missing_typed_member_source_cannot_issue(active_inputs):
    selection, physical, tests, _ = active_inputs
    result = finish(selection, physical, tests)
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.floor is result.requirement is None


def test_replaced_selection_summary_cannot_certify_wrong_uncapped_candidate(active_inputs):
    selection, _, tests, constructions = active_inputs
    wrong = replace(
        selection.supplied,
        classes=tuple(
            replace(c, samples=tuple(replace(s, value=Flow(9), uncertainty=singleton(Flow(9))) for s in c.samples))
            for c in selection.supplied.classes
        ),
    )
    forged = replace(selection, supplied=wrong)
    result = finish(forged, (), tests, constructions)
    assert result.checks.finding is CheckFinding.FAIL
    assert result.requirement is result.floor is None
    assert any(c.check_id == "external_selection" and c.finding is CheckFinding.FAIL for c in result.checks.checks)


def test_changed_duration_threshold_cannot_hide_under_same_configured_test(active_inputs):
    selection, physical, tests, constructions = active_inputs
    changed = replace(tests[0], threshold=threshold("A", 11))
    with pytest.raises(ValueError, match="cannot change threshold"):
        finish(selection, physical, (changed, *tests[1:]), constructions)


def test_retained_member_missing_physics_cannot_be_silently_dropped(active_inputs):
    selection, physical, tests, constructions = active_inputs
    # Explicit omission: selected family is feasible, but no retained-member
    # physical records were supplied. The fixed retained set remains A and B.
    result = finalize_regime(
        selection,
        EcologicalRegimeMethod.BASELINE,
        REQUIRED,
        physical,
        duration_tests=tests,
        expected_duration_tests=(("A", "annual7"), ("B", "annual7")),
        version="incomplete-members",
        provenance=provenance("selected"),
        constructions=constructions,
    )
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.selection.specification.retained == ("A", "B")
    assert result.floor is result.requirement is None


@pytest.mark.parametrize("fault", ["designated", "unresourced", "wrong-member-disclosure"])
def test_final_boundary_rechecks_classification_eligibility_and_exact_disclosure(active_inputs, fault):
    from fishy.natural_routing import Availability, NaturalRoute
    from fishy.requirement_construction import assess_construction
    from fishy.spatial import DesignationState, Eligibility

    selection, _, _, constructions = active_inputs
    original = constructions[0]
    route = original.route
    assert route is not None
    if fault == "designated":
        route = replace(
            route,
            classification=replace(
                route.classification,
                designation=DesignationState.DESIGNATED,
                designation_eligibility=Eligibility.ACCEPTED,
            ),
        )
    elif fault == "unresourced":
        route = replace(route, tiers=(replace(route.tiers[0], resourced=Availability.UNAVAILABLE),))
    else:
        tier = route.tiers[0]
        disclosure = tier.prerequisites[0]
        wrong = replace(
            disclosure,
            findings=replace(disclosure.findings, scope=replace(disclosure.findings.scope, member="another-member")),
        )
        route = replace(route, tiers=(replace(tier, prerequisites=(wrong,)),))
    result = assess_construction(selection.members[0], replace(original, route=route))
    assert result.checks.finding is (CheckFinding.UNKNOWN if fault == "unresourced" else CheckFinding.FAIL)
    assert result.route is not None
    assert result.route.selected is (NaturalRoute.POTENTIAL if fault == "designated" else NaturalRoute.PENDING)
    assert result.member.candidate == selection.members[0].candidate
    if fault == "unresourced":
        assert result.route.highest_data_supported is NaturalRoute.BASELINE


def test_missing_route_proof_is_diagnostic_not_new_eligibility(active_inputs):
    from fishy.requirement_construction import assess_construction

    selection, _, _, constructions = active_inputs
    result = assess_construction(selection.members[0], replace(constructions[0], route=None))
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.route is None
    assert len(result.compositions) == 1460
