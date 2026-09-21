"""assess_construction : RequirementMember × RegimeConstruction → ConstructionAssessment.

Recompute typed pre-quality sources and every composition. Exact final-family
acceptance cannot waive failed source hydrology, natural bounds or physical maps.
"""

from dataclasses import dataclass

from fishy.design_conditions import DesignClass
from fishy.ecological_transfer import TransferResult, transfer_ecological_regime
from fishy.evidence import Check, CheckFinding, CheckSummary, Provenance
from fishy.flows import FlowSample
from fishy.natural_baseline import BaselineResult, EcologicalRegimeMethod, baseline_family, recorded_minimum_product
from fishy.natural_routing import NaturalRoute, RouteDecision, RouteFailure, TierEvidence, select_natural_route
from fishy.quality_activation import apply_quality_component
from fishy.requirement_composition import IntervalComposition, compose_requirement
from fishy.requirement_family import RequirementFamily, RequirementMember
from fishy.scientific_acceptance import UsePurpose
from fishy.spatial import Location, PreparedClassification
from fishy.study_requirements import (
    HighFlowTrigger,
    NaturalStudyComponent,
    NaturalStudyResult,
    StudyNeed,
    TopTierEligibility,
    assess_natural_study,
)


@dataclass(frozen=True)
class BaselineSource:
    result: BaselineResult
    provenance: Provenance
    profile_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.result, BaselineResult) or not isinstance(self.provenance, Provenance):
            raise TypeError("baseline source needs typed result and original provenance")
        if not self.profile_version.strip():
            raise ValueError("original baseline profile version required")


@dataclass(frozen=True)
class ClassStudy:
    design: DesignClass
    required_components: tuple[str, ...]
    components: tuple[NaturalStudyComponent, ...]


@dataclass(frozen=True)
class StudySource:
    hydrology: BaselineSource
    classification: PreparedClassification
    eligibility: TopTierEligibility
    trigger: HighFlowTrigger
    need: StudyNeed
    studies: tuple[ClassStudy, ...]


@dataclass(frozen=True)
class ClassComposition:
    design: DesignClass
    result: IntervalComposition

    def __post_init__(self) -> None:
        if not isinstance(self.design, DesignClass) or not isinstance(self.result, IntervalComposition):
            raise TypeError("composition needs a class and retained interval operands")


@dataclass(frozen=True)
class NaturalRouteInputs:
    location: Location
    classification: PreparedClassification
    tiers: tuple[TierEvidence, ...]
    failures: tuple[RouteFailure, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location) or not isinstance(self.classification, PreparedClassification):
            raise TypeError("natural route inputs require located prepared classification")
        if not isinstance(self.tiers, tuple) or any(not isinstance(t, TierEvidence) for t in self.tiers):
            raise TypeError("immutable typed tier inputs required")
        if not isinstance(self.failures, tuple) or any(not isinstance(f, RouteFailure) for f in self.failures):
            raise TypeError("immutable typed failed attempts required")
        if any(t.location != self.location for t in self.tiers):
            raise ValueError("route tiers must belong to the classified location")


@dataclass(frozen=True)
class MemberConstruction:
    member: str
    source: BaselineSource | TransferResult | StudySource
    compositions: tuple[ClassComposition, ...]
    route: NaturalRouteInputs | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.member, str) or not self.member.strip():
            raise ValueError("construction member required")
        if not isinstance(self.source, (BaselineSource, TransferResult, StudySource)):
            raise TypeError("typed baseline, qualified transfer or natural study source required")
        if not isinstance(self.compositions, tuple) or any(
            not isinstance(c, ClassComposition) for c in self.compositions
        ):
            raise TypeError("complete immutable class/day compositions required")


@dataclass(frozen=True)
class ConstructionAssessment:
    construction: MemberConstruction
    member: RequirementMember
    recomputed_source: BaselineResult | TransferResult | tuple[NaturalStudyResult, ...]
    compositions: tuple[ClassComposition, ...]
    checks: CheckSummary
    route: RouteDecision | None


def _hydrology(source: BaselineSource) -> list[Check]:
    checks = []
    for p in source.result.inputs.patterns:
        checks.append(
            Check(
                f"sizing:{p.magnitude.target.value}",
                CheckFinding.PASS if p.purpose is UsePurpose.SIZING else CheckFinding.FAIL,
                ("screening permission cannot authorize new sizing",),
            )
        )
    record = source.result.inputs.recorded
    if record is not None and record.assessment is not None and source.result.inputs.patterns:
        first = source.result.inputs.patterns[0]
        permission = record.assessment.acceptance_for(
            recorded_minimum_product(record, intended_use=first.requested_use, purpose=UsePurpose.SIZING)
        )
        checks.append(Check("recorded_minimum_sizing", permission.finding, permission.reasons))
    else:
        checks.append(Check("recorded_minimum_sizing", CheckFinding.UNKNOWN, ("accepted recorded minimum missing",)))
    return checks


def _baseline(source: BaselineSource) -> BaselineResult:
    inputs = source.result.inputs
    return baseline_family(
        inputs.patterns,
        inputs.recorded,
        provenance=source.provenance,
        profile_version=source.profile_version,
        alpha=inputs.alpha,
        winter=inputs.winter,
        spawning=inputs.spawning,
    )


def _core_identity(sample: FlowSample):
    return (sample.location, sample.interval, sample.value, sample.provenance)


def assess_construction(member: RequirementMember, construction: MemberConstruction) -> ConstructionAssessment:
    """Recompute this member only; never run/choose alternative reference members."""
    if construction.member != member.identifier or not isinstance(member.candidate, RequirementFamily):
        raise ValueError("construction must identify the retained regime member")
    family = member.candidate
    source = construction.source
    base_samples = {}
    checks = []
    if isinstance(source, BaselineSource):
        method = EcologicalRegimeMethod.BASELINE
        recomputed = _baseline(source)
        checks.extend(_hydrology(source))
        checks.extend(Check("source:" + c.check_id, c.finding, c.reasons) for c in recomputed.checks.checks)
        candidate = recomputed.candidate
        if candidate is not None:
            base_samples = {(c.design, s.interval): s for c in candidate.classes for s in c.samples}
        # A replaced result carrying an unrelated candidate cannot supply source provenance.
        if source.result.candidate != candidate:
            checks.append(
                Check(
                    "source_result_binding",
                    CheckFinding.FAIL,
                    ("retained source candidate differs from recomputed original inputs",),
                )
            )
    elif isinstance(source, TransferResult):
        method = EcologicalRegimeMethod.TRANSFER
        recomputed = transfer_ecological_regime(
            source.donor,
            source.donor_natural,
            source.recipient_natural,
            source.profile,
            source.qualification,
            source.register,
            evaluated_at=source.evaluated_at,
        )
        checks.extend(Check("source:" + c.check_id, c.finding, c.reasons) for c in recomputed.checks.checks)
        candidate = recomputed.candidate
        if candidate is not None:
            base_samples = {(c.design, s.interval): s for c in candidate.classes for s in c.samples}
        if source.candidate != candidate:
            checks.append(
                Check(
                    "source_result_binding",
                    CheckFinding.FAIL,
                    ("retained transfer differs from recomputed qualified relationship",),
                )
            )
    else:
        method = EcologicalRegimeMethod.STUDY
        hydro = _baseline(source.hydrology)
        checks.extend(_hydrology(source.hydrology))
        # Top studies need accepted reference products, not the baseline median cap.
        checks.extend(
            Check("hydrology:" + c.check_id, c.finding, c.reasons)
            for c in hydro.checks.checks
            if c.check_id.startswith("pattern:")
        )
        studies = []
        for index, item in enumerate(source.studies):
            result = assess_natural_study(
                source.classification,
                source.eligibility,
                item.required_components,
                item.components,
                source.trigger,
                source.need,
                "baseline",
            )
            studies.append(result)
            checks.extend(Check(f"study:{index}:{c.check_id}", c.finding, c.reasons) for c in result.checks.checks)
            if result.checks.finding is CheckFinding.PASS and item.components:
                first = item.components[0].study
                if any(c.study.scope != first.scope for c in item.components):
                    raise ValueError("shared study components require the same location/interval/physical scope")
                flow = max((flow for _, flow in result.supported_components), key=lambda f: f.value)
                key = item.design, first.scope.period
                if key in base_samples:
                    raise ValueError("duplicate class/day study source")
                # Preserve actual source value/identity; no source sample is fabricated here.
                matches = [
                    c.result.base for c in construction.compositions if (c.design, c.result.base.interval) == key
                ]
                if (
                    len(matches) != 1
                    or matches[0].value != flow
                    or matches[0].location != first.scope.location
                    or matches[0].provenance != first.evidence.provenance
                ):
                    checks.append(
                        Check(
                            f"study:{index}:binding",
                            CheckFinding.FAIL,
                            ("study-selected same-water requirement differs from composition base",),
                        )
                    )
                else:
                    base_samples[key] = matches[0]
        recomputed = tuple(studies)
    if family.basis.method != method.value:
        raise ValueError("member method does not match its actual typed source")
    routing = None
    route_inputs = construction.route
    if route_inputs is None:
        checks.append(
            Check("route_selection", CheckFinding.UNKNOWN, ("prepared classification and exact route inputs missing",))
        )
    else:
        expected_route = {
            EcologicalRegimeMethod.BASELINE: NaturalRoute.BASELINE,
            EcologicalRegimeMethod.STUDY: NaturalRoute.TOP,
            EcologicalRegimeMethod.TRANSFER: NaturalRoute.TRANSFER,
        }[method]
        routing = select_natural_route(
            route_inputs.classification,
            route_inputs.tiers,
            route_inputs.failures,
            transfer=source if isinstance(source, TransferResult) else None,
        )
        route_finding = (
            CheckFinding.PASS
            if routing.selected is expected_route
            else CheckFinding.UNKNOWN
            if routing.selected is NaturalRoute.PENDING
            else CheckFinding.FAIL
        )
        checks.append(
            Check(
                "route_selection",
                route_finding,
                routing.reasons or (f"selected {routing.selected.value}; needed {expected_route.value}",),
            )
        )
        for tier in routing.tiers:
            if tier.evidence.route is expected_route:
                for kind, summary in (("data", tier.data), ("eligibility", tier.eligibility)):
                    checks.extend(Check(f"route:{kind}:{c.check_id}", c.finding, c.reasons) for c in summary.checks)
        if isinstance(source, TransferResult):
            locations = {p.location for p in source.recipient_natural}
            if locations and locations != {route_inputs.location}:
                raise ValueError("transfer route classification belongs to another receiving location")
        else:
            hydrology = source if isinstance(source, BaselineSource) else source.hydrology
            inputs = hydrology.result.inputs
            matching = next((t for t in route_inputs.tiers if t.route is expected_route), None)
            if matching is None:
                checks.append(Check("route_source_binding", CheckFinding.UNKNOWN, ("required route tier is absent",)))
            elif matching.natural_patterns != inputs.patterns or matching.recorded_minimum != inputs.recorded:
                checks.append(
                    Check(
                        "route_source_binding",
                        CheckFinding.FAIL,
                        ("tier hydrology differs from the actual member source",),
                    )
                )
            if inputs.patterns and route_inputs.location != inputs.patterns[0].location:
                raise ValueError("route classification belongs to another pre-quality location")
            if isinstance(source, StudySource):
                if route_inputs.classification != source.classification:
                    raise ValueError("top route and source classifications differ")
                bound = (
                    matching is not None
                    and any(
                        matching.studies == item.components
                        and matching.required_study_components == item.required_components
                        for item in source.studies
                    )
                    and matching.study_trigger is source.trigger
                    and matching.study_need == source.need
                )
                checks.append(
                    Check(
                        "route_study_binding",
                        CheckFinding.PASS if bound else CheckFinding.FAIL,
                        ("priority/trigger tier must use actual typed member study inputs",),
                    )
                )
    expected = {(c.design, s.interval): s for c in family.classes for s in c.samples}
    supplied = {}
    for item in construction.compositions:
        key = item.design, item.result.base.interval
        if key in supplied or key not in expected:
            raise ValueError("duplicate or undeclared class/day construction")
        supplied[key] = item
    compositions = []
    for key, final in expected.items():
        label = f"construction:{key[0].value}:{key[1].start.isoformat()}"
        if key not in supplied or key not in base_samples:
            checks.append(
                Check(label, CheckFinding.UNKNOWN, ("required accepted pre-quality source or composition missing",))
            )
            continue
        original = supplied[key].result
        if _core_identity(original.base) != _core_identity(base_samples[key]):
            checks.append(
                Check(label, CheckFinding.FAIL, ("composition base does not match the actual pre-quality source",))
            )
            continue
        q = original.quality
        if q is not None:
            q = apply_quality_component(
                q.base,
                q.quality.boundary,
                q.quality.targets,
                q.activation,
                q.source_control,
                q.accounts,
                q.background_mapping,
                q.quality.bounds,
                q.final_check.arrival if q.final_check is not None else None,
            )
        mapping = original.mapping
        result = compose_requirement(
            original.base,
            final.provenance,
            quality=q,
            mapping=mapping.mapping if mapping else None,
            mapping_evidence=mapping.evidence if mapping else None,
        )
        compositions.append(ClassComposition(key[0], result))
        checks.extend(Check(label + ":" + c.check_id, c.finding, c.reasons) for c in result.checks.checks)
        bound = result.candidate is not None and _core_identity(result.candidate) == _core_identity(final)
        checks.append(
            Check(
                label + ":final_value",
                CheckFinding.PASS if bound else CheckFinding.UNKNOWN if result.candidate is None else CheckFinding.FAIL,
                ("fully assembled member must equal recomputed source and physical composition",),
            )
        )
    return ConstructionAssessment(
        construction, member, recomputed, tuple(compositions), CheckSummary(tuple(checks)), routing
    )
