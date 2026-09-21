"""finalize_regime : SelectedRequirementFamily × FinalPhysicalInputs × DurationTests → FinalRegime.

A whole-family failure declines new requirement/floor publication. Existing issued
versions remain unchanged. Route selection/descent is a separate caller operation.
"""

from dataclasses import dataclass, replace

from fishy.design_conditions import DesignClass
from fishy.duration_minima import DurationThreshold
from fishy.duration_windows import WindowUncertaintySupport
from fishy.duties import Floor
from fishy.evidence import Check, CheckFinding, CheckSummary, Provenance
from fishy.floor_construction import FloorConstruction, FloorConstructionAssessment, assess_floor_construction
from fishy.flows import FlowSample
from fishy.low_flow_safeguard import AssessmentStage, CandidateReferenceRelation, LowFlowAssessment, assess_low_flow
from fishy.natural_baseline import EcologicalRegimeMethod
from fishy.natural_floor import FloorInvariant, natural_floor
from fishy.natural_routing import NaturalRoute, RouteFailure
from fishy.requirement_checks import FinalCondition, RequirementAssessment, recheck_requirement
from fishy.requirement_construction import ConstructionAssessment, MemberConstruction, assess_construction
from fishy.requirement_family import FamilySelection, FloorSeries, RequirementFamily, assess_selected_family
from fishy.scientific_acceptance import ScientificAssessment, UsePurpose


@dataclass(frozen=True)
class ClassAssessment:
    design: DesignClass
    result: RequirementAssessment

    def __post_init__(self) -> None:
        if not isinstance(self.design, DesignClass) or not isinstance(self.result, RequirementAssessment):
            raise TypeError("class assessment requires design and exact requirement assessment")


@dataclass(frozen=True)
class MemberPhysical:
    member: str
    assessment: ClassAssessment

    def __post_init__(self) -> None:
        if (
            not isinstance(self.member, str)
            or not self.member.strip()
            or not isinstance(self.assessment, ClassAssessment)
        ):
            raise TypeError("member physical assessment requires named member and class assessment")


@dataclass(frozen=True)
class DurationTest:
    """One configured retained-reference test, with explicit class-specific context."""

    identifier: str
    member: str
    design: DesignClass
    threshold: DurationThreshold
    predecessors: tuple[FlowSample, ...]
    predecessor_basis: str | None
    scientific_assessment: ScientificAssessment | None
    uncertainty_support: WindowUncertaintySupport | None
    reference_relation: CandidateReferenceRelation | None
    purpose: UsePurpose

    def __post_init__(self) -> None:
        if not self.identifier.strip() or not self.member.strip():
            raise ValueError("duration test and retained member require identities")
        if not isinstance(self.design, DesignClass) or not isinstance(self.threshold, DurationThreshold):
            raise TypeError("duration test requires DesignClass and DurationThreshold")
        if not isinstance(self.predecessors, tuple) or any(not isinstance(s, FlowSample) for s in self.predecessors):
            raise TypeError("predecessor samples must be immutable")
        if self.threshold.reference.provenance.reference_member != self.member:
            raise ValueError("duration test member must identify its threshold reference")


@dataclass(frozen=True)
class ClassDurationAssessment:
    test: DurationTest
    result: LowFlowAssessment


@dataclass(frozen=True)
class FinalRegime:
    selection: FamilySelection
    constructions: tuple[ConstructionAssessment, ...]
    method: EcologicalRegimeMethod
    physical: tuple[ClassAssessment, ...]
    duration: tuple[ClassDurationAssessment, ...]
    provisional: tuple[LowFlowAssessment, ...]
    invariant: FloorInvariant | None
    checks: CheckSummary
    requirement: RequirementFamily | None
    floor: Floor | None
    member_physical: tuple[MemberPhysical, ...] = ()
    member_duration: tuple[ClassDurationAssessment, ...] = ()

    @property
    def route_failure(self) -> RouteFailure | None:
        """Feed this diagnosed attempt into select_natural_route; never retry it silently."""
        if self.checks.finding is CheckFinding.PASS:
            return None
        route = {
            EcologicalRegimeMethod.BASELINE: NaturalRoute.BASELINE,
            EcologicalRegimeMethod.TRANSFER: NaturalRoute.TRANSFER,
            EcologicalRegimeMethod.STUDY: NaturalRoute.TOP,
        }[self.method]
        reasons = tuple(
            f"{check.check_id}: {check.finding.value}: {'; '.join(check.reasons)}"
            for check in self.checks.checks
            if check.finding is not CheckFinding.PASS
        )
        return RouteFailure(route, self.checks.finding, reasons or ("final requirement unresolved",))


def _physical_checks(family, required, assessments):
    if (
        not isinstance(required, tuple)
        or len(set(required)) != len(required)
        or any(not isinstance(c, FinalCondition) for c in required)
    ):
        raise TypeError("required final conditions must be unique immutable FinalCondition records")
    expected = {(c.design, s.interval): s for c in family.classes for s in c.samples}
    supplied = {}
    for item in assessments:
        key = item.design, item.result.sample.interval
        if key in supplied:
            raise ValueError("duplicate class/day assessment")
        if key not in expected or item.result.sample != expected[key]:
            raise ValueError("final assessment refers to a different class/day candidate")
        if item.result.required != required:
            raise ValueError("final condition manifest cannot change by class or day")
        supplied[key] = item
    checks = []
    for (design, interval), _ in expected.items():
        item = supplied.get((design, interval))
        label = f"physical:{design.value}:{interval.start.isoformat()}"
        if item is None:
            checks.append(Check(label, CheckFinding.UNKNOWN, ("required final class/day checks missing",)))
        else:
            checks.append(Check(label, item.result.checks.finding))
            if any(c.finding is CheckFinding.UNKNOWN for c in item.result.checks.checks):
                checks.append(
                    Check(label + ":coverage", CheckFinding.UNKNOWN, ("required physical conditions unresolved",))
                )
    return checks


def _duration_checks(family, duration_tests, expected, version):
    checks = []
    supplied_tests = {}
    configured = {}
    for test in duration_tests:
        config_key = test.member, test.identifier
        if config_key in configured and configured[config_key] != (test.threshold, test.purpose):
            raise ValueError("one configured duration test cannot change threshold or purpose by class")
        configured[config_key] = test.threshold, test.purpose
        key = test.member, test.identifier, test.design
        if key not in expected or key in supplied_tests:
            raise ValueError("undeclared or duplicate member/class/duration test")
        supplied_tests[key] = test
    duration = []
    for member, name, design in sorted(expected, key=lambda x: (x[0], x[1], x[2].value)):
        key = member, name, design
        label = f"duration:{member}:{name}:{design.value}"
        if key not in supplied_tests:
            checks.append(Check(label, CheckFinding.UNKNOWN, ("required class-specific duration inputs missing",)))
            continue
        test = supplied_tests[key]
        if test.purpose is not UsePurpose.SIZING:
            checks.append(
                Check(
                    label + ":sizing",
                    CheckFinding.FAIL,
                    ("screening-only duration permission cannot authorize new sizing",),
                )
            )
        if any(s.interval.end > family.basis.period.start for s in test.predecessors):
            raise ValueError("predecessor inputs cannot replace final candidate days")
        candidate = family.samples(design)
        result = assess_low_flow(
            (*test.predecessors, *candidate),
            family.basis.period,
            test.threshold,
            stage=AssessmentStage.FINAL,
            candidate_basis=f"{version}:class-{design.value}",
            provenance=candidate[0].provenance,
            predecessor_basis=test.predecessor_basis,
            scientific_assessment=test.scientific_assessment,
            uncertainty_support=test.uncertainty_support,
            purpose=test.purpose,
            reference_relation=test.reference_relation,
        )
        duration.append(ClassDurationAssessment(test, result))
        # Preserve known failure AND unknown required windows/uncertainty as independent findings.
        for component, summary in (("point", result.point), ("uncertainty", result.uncertainty)):
            checks.append(Check(label + ":" + component, summary.finding))
            if any(c.finding is CheckFinding.UNKNOWN for c in summary.checks):
                checks.append(
                    Check(
                        label + ":" + component + ":coverage",
                        CheckFinding.UNKNOWN,
                        ("required window support incomplete",),
                    )
                )
        checks.append(Check(label + ":scientific", result.permission.finding, result.permission.reasons))
    return tuple(duration), checks


def finalize_regime(
    selection: FamilySelection,
    method: EcologicalRegimeMethod,
    required: tuple[FinalCondition, ...],
    physical: tuple[ClassAssessment, ...],
    *,
    duration_tests: tuple[DurationTest, ...],
    expected_duration_tests: tuple[tuple[str, str], ...],
    version: str,
    provenance: Provenance,
    provisional: tuple[LowFlowAssessment, ...] = (),
    constructions: tuple[MemberConstruction, ...] = (),
    member_physical: tuple[MemberPhysical, ...] = (),
    member_duration_tests: tuple[DurationTest, ...] = (),
) -> FinalRegime:
    """Run every required selected-family safeguard before deriving an issuable floor.

    expected_duration_tests contains (retained member, configured test identifier).
    Every entry applies to all four classes. Baseline needs at least one configured
    test per retained member; other routes acquire no implicit statistical gate.
    """
    if not isinstance(method, EcologicalRegimeMethod):
        raise TypeError("final regime requires ecological route identity")
    if not version.strip() or not isinstance(provenance, Provenance):
        raise ValueError("final result requires immutable version/provenance")
    if not isinstance(physical, tuple) or any(not isinstance(a, ClassAssessment) for a in physical):
        raise TypeError("physical assessments must be an immutable tuple")
    selection = assess_selected_family(selection.members, selection.supplied, selection.specification)
    checks = list(selection.checks.checks)
    family = selection.supplied
    if family is None:
        checks.append(Check("selected_family", CheckFinding.UNKNOWN, ("selected requirement family missing",)))
        return FinalRegime(
            selection, (), method, physical, (), provisional, None, CheckSummary(tuple(checks)), None, None
        )
    if not isinstance(family, RequirementFamily):
        raise TypeError("floor-only routes cannot create a regime or obligation")
    if family.basis.method != method.value:
        raise ValueError("final route must match the selected family's immutable method basis")
    first = family.classes[0].samples[0]
    for field in ("scenario", "reference_member", "reference_kind", "configuration_version"):
        if getattr(first.provenance, field) != getattr(provenance, field):
            raise ValueError("final floor provenance must retain selected family identity")
    if not isinstance(constructions, tuple) or any(not isinstance(c, MemberConstruction) for c in constructions):
        raise TypeError("retained sources require immutable MemberConstruction records")
    if len({c.member for c in constructions}) != len(constructions):
        raise ValueError("duplicate member construction")
    by_member = {c.member: c for c in constructions}
    if set(by_member) - set(selection.specification.retained):
        raise ValueError("construction is not from the retained member set")
    source_results = []
    for member in selection.members:
        if member.identifier not in by_member:
            checks.append(
                Check(
                    f"source:{member.identifier}",
                    CheckFinding.UNKNOWN,
                    ("typed pre-quality source and full composition not supplied",),
                )
            )
            continue
        source_result = assess_construction(member, by_member[member.identifier])
        source_results.append(source_result)
        checks.extend(
            Check(f"member:{member.identifier}:{c.check_id}", c.finding, c.reasons) for c in source_result.checks.checks
        )
    physical = tuple(ClassAssessment(item.design, recheck_requirement(item.result)) for item in physical)
    checks.extend(_physical_checks(family, required, physical))
    # Same labels cannot conceal changed activation or target policies. Physical
    # loads may vary by reference; policy choices must match at each class/day.
    policies = {}
    for source_result in source_results:
        for item in source_result.compositions:
            q = item.result.quality
            key = item.design, item.result.base.interval
            policy = (q.activation, q.quality.targets) if q is not None else None
            if key in policies and policies[key] != policy:
                checks.append(
                    Check(
                        f"quality_policy:{source_result.member.identifier}:{item.design.value}:{key[1].start.isoformat()}",
                        CheckFinding.FAIL,
                        ("retained members use different quality/activation policies",),
                    )
                )
            else:
                policies[key] = policy
    for item in physical:
        key = item.design, item.result.sample.interval
        q = item.result.original_quality
        policy = (q.activation, q.quality.targets) if q is not None else None
        if key in policies and policies[key] != policy:
            checks.append(
                Check(
                    f"selected_quality_policy:{item.design.value}:{key[1].start.isoformat()}",
                    CheckFinding.FAIL,
                    ("final candidate changes the retained activation/quality policy",),
                )
            )
    if not isinstance(expected_duration_tests, tuple) or len(set(expected_duration_tests)) != len(
        expected_duration_tests
    ):
        raise ValueError("fixed unique duration-test manifest required")
    retained = set(selection.specification.retained)
    if any(member not in retained or not name.strip() for member, name in expected_duration_tests):
        raise ValueError("duration test manifest must identify retained members")
    if method is EcologicalRegimeMethod.BASELINE and {m for m, _ in expected_duration_tests} != retained:
        checks.append(
            Check(
                "baseline_safeguard_manifest",
                CheckFinding.UNKNOWN,
                ("baseline requires configured tests for every retained member",),
            )
        )
    expected = {(m, name, design) for m, name in expected_duration_tests for design in DesignClass}
    duration, duration_checks = _duration_checks(family, duration_tests, expected, version)
    checks.extend(duration_checks)
    if not isinstance(member_physical, tuple) or any(not isinstance(a, MemberPhysical) for a in member_physical):
        raise TypeError("immutable member physical assessments required")
    if any(a.member not in retained for a in member_physical):
        raise ValueError("physical assessment belongs to an excluded member")
    assessed_members = tuple(
        MemberPhysical(a.member, ClassAssessment(a.assessment.design, recheck_requirement(a.assessment.result)))
        for a in member_physical
    )
    if any((t.member, t.identifier, t.design) not in expected for t in member_duration_tests):
        raise ValueError("member duration input is outside the fixed test manifest")
    selected_test_inputs = {(t.member, t.identifier, t.design): t for t in duration_tests}
    for test in member_duration_tests:
        selected_test = selected_test_inputs.get((test.member, test.identifier, test.design))
        if selected_test is not None and (test.threshold, test.purpose) != (
            selected_test.threshold,
            selected_test.purpose,
        ):
            raise ValueError("selected family must repeat the exact retained-member threshold and purpose")
    member_duration = []
    for member in selection.members:
        if not isinstance(member.candidate, RequirementFamily):
            raise TypeError("regime member requires complete four-class candidate")
        physical_inputs = tuple(a.assessment for a in assessed_members if a.member == member.identifier)
        member_checks = _physical_checks(member.candidate, required, physical_inputs)
        checks.extend(Check(f"retained:{member.identifier}:{c.check_id}", c.finding, c.reasons) for c in member_checks)
        member_tests = tuple(t for t in member_duration_tests if t.member == member.identifier)
        member_expected = {key for key in expected if key[0] == member.identifier}
        computed, member_checks = _duration_checks(member.candidate, member_tests, member_expected, version)
        member_duration.extend(computed)
        checks.extend(Check(f"retained:{member.identifier}:{c.check_id}", c.finding, c.reasons) for c in member_checks)
        for item in physical_inputs:
            key = item.design, item.result.sample.interval
            q = item.result.original_quality
            policy = (q.activation, q.quality.targets) if q is not None else None
            if key in policies and policies[key] != policy:
                checks.append(
                    Check(
                        f"retained_policy:{member.identifier}:{key[0].value}:{key[1].start.isoformat()}",
                        CheckFinding.FAIL,
                        ("member final check changed its construction policy",),
                    )
                )
    invariant = natural_floor(family)
    checks.append(invariant.check)
    summary = CheckSummary(tuple(checks))
    floor = None
    requirement = None
    if summary.finding is CheckFinding.PASS:
        requirement = family
        floor = Floor(
            replace(
                first,
                interval=family.basis.period,
                value=invariant.candidate,
                provenance=provenance,
                uncertainty=None,
                components=(),
                reasons=("fixed annual minimum of final selected95; cross-class invariant passed",),
            ),
            version,
        )
    return FinalRegime(
        selection,
        tuple(source_results),
        method,
        physical,
        tuple(duration),
        provisional,
        invariant,
        summary,
        requirement,
        floor,
        assessed_members,
        tuple(member_duration),
    )


@dataclass(frozen=True)
class FloorMemberAssessment:
    member: str
    result: RequirementAssessment

    def __post_init__(self) -> None:
        if (
            not isinstance(self.member, str)
            or not self.member.strip()
            or not isinstance(self.result, RequirementAssessment)
        ):
            raise TypeError("direct-floor member checks require named member and actual assessment")


@dataclass(frozen=True)
class FinalFloors:
    selection: FamilySelection
    physical: tuple[RequirementAssessment, ...]
    checks: CheckSummary
    floors: tuple[Floor, ...]
    constructions: tuple[FloorConstructionAssessment, ...] = ()
    member_physical: tuple[FloorMemberAssessment, ...] = ()


def finalize_floors(
    selection: FamilySelection,
    required: tuple[FinalCondition, ...],
    physical: tuple[RequirementAssessment, ...],
    *,
    version: str,
    constructions: tuple[FloorConstruction, ...] = (),
    member_physical: tuple[FloorMemberAssessment, ...] = (),
) -> FinalFloors:
    """Carry final quality-adjusted direct floors, never derive a seasonal obligation."""
    if not version.strip():
        raise ValueError("floor version required")
    series = selection.supplied
    if not isinstance(series, FloorSeries):
        raise TypeError("direct floor route requires FloorSeries")
    physical = tuple(recheck_requirement(result) for result in physical)
    supplied = {}
    for result in physical:
        if result.sample.interval in supplied or result.sample not in series.samples or result.required != required:
            raise ValueError("floor checks must refer to each exact final floor and fixed conditions")
        supplied[result.sample.interval] = result
    selection = assess_selected_family(selection.members, selection.supplied, selection.specification)
    checks = list(selection.checks.checks)
    if not isinstance(constructions, tuple) or any(not isinstance(c, FloorConstruction) for c in constructions):
        raise TypeError("typed immutable floor constructions required")
    if len({c.member for c in constructions}) != len(constructions):
        raise ValueError("duplicate floor member construction")
    by_member = {c.member: c for c in constructions}
    if set(by_member) - set(selection.specification.retained):
        raise ValueError("direct-floor construction belongs to an excluded member")
    sources = []
    policies = {}
    for member in selection.members:
        if member.identifier not in by_member:
            checks.append(
                Check(
                    "source:" + member.identifier,
                    CheckFinding.UNKNOWN,
                    ("actual direct-floor source/composition missing",),
                )
            )
            continue
        source = assess_floor_construction(member, by_member[member.identifier])
        sources.append(source)
        checks.extend(
            Check(f"source:{member.identifier}:{c.check_id}", c.finding, c.reasons) for c in source.checks.checks
        )
        for item in source.compositions:
            q = item.quality
            policy = (q.activation, q.quality.targets) if q is not None else None
            key = item.base.interval
            if key in policies and policies[key] != policy:
                checks.append(
                    Check(
                        f"member_policy:{member.identifier}:{key.start.isoformat()}",
                        CheckFinding.FAIL,
                        ("direct floor members use different quality policies",),
                    )
                )
            policies[key] = policy
    if not isinstance(member_physical, tuple) or any(not isinstance(a, FloorMemberAssessment) for a in member_physical):
        raise TypeError("typed retained direct-floor physical assessments required")
    if any(a.member not in selection.specification.retained for a in member_physical):
        raise ValueError("physical assessment belongs to an excluded direct-floor member")
    original_checks = tuple(FloorMemberAssessment(a.member, recheck_requirement(a.result)) for a in member_physical)
    for member in selection.members:
        if not isinstance(member.candidate, FloorSeries):
            raise TypeError("direct floor member cannot be a regime family")
        rows = {}
        for assessment in original_checks:
            if assessment.member != member.identifier:
                continue
            result = assessment.result
            if (
                result.sample not in member.candidate.samples
                or result.sample.interval in rows
                or result.required != required
            ):
                raise ValueError(
                    "retained floor assessment must bind every exact member interval and required condition"
                )
            rows[result.sample.interval] = result
        for sample in member.candidate.samples:
            result = rows.get(sample.interval)
            label = f"retained:{member.identifier}:{sample.interval.start.isoformat()}"
            checks.append(
                Check(
                    label,
                    result.checks.finding if result else CheckFinding.UNKNOWN,
                    () if result else ("retained direct-floor final physical check missing",),
                )
            )
            if result and any(c.finding is CheckFinding.UNKNOWN for c in result.checks.checks):
                checks.append(Check(label + ":coverage", CheckFinding.UNKNOWN))
            if result and sample.interval in policies:
                q = result.original_quality
                policy = (q.activation, q.quality.targets) if q is not None else None
                if policy != policies[sample.interval]:
                    checks.append(
                        Check(
                            label + ":policy", CheckFinding.FAIL, ("member final checks changed direct-floor policy",)
                        )
                    )
    for sample in series.samples:
        result = supplied.get(sample.interval)
        if result is not None and sample.interval in policies:
            q = result.original_quality
            policy = (q.activation, q.quality.targets) if q is not None else None
            if policy != policies[sample.interval]:
                checks.append(
                    Check(
                        f"selected_policy:{sample.interval.start.isoformat()}",
                        CheckFinding.FAIL,
                        ("selected direct floor changes quality/activation policy",),
                    )
                )
        label = f"floor:{sample.interval.start.isoformat()}"
        checks.append(
            Check(
                label,
                result.checks.finding if result else CheckFinding.UNKNOWN,
                () if result else ("final floor feasibility/quality evidence missing",),
            )
        )
        if result and any(c.finding is CheckFinding.UNKNOWN for c in result.checks.checks):
            checks.append(Check(label + ":coverage", CheckFinding.UNKNOWN))
    summary = CheckSummary(tuple(checks))
    floors = tuple(Floor(s, version) for s in series.samples) if summary.finding is CheckFinding.PASS else ()
    return FinalFloors(selection, physical, summary, floors, tuple(sources), original_checks)
