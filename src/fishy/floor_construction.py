"""assess_floor_construction : RequirementMember × FloorConstruction → FloorConstructionAssessment.

Recompute each route's own floor and daily quality composition. Natural route
classification and structural applicability bind the source; no baseline duration gate is added.
"""

from dataclasses import dataclass

from fishy.duties import SuppliedDuty
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    ProductionMethod,
    ReferenceKind,
    permitted_use,
)
from fishy.graduated_entry import EntryResult, evaluate_graduated_entry
from fishy.natural_routing import NaturalRoute, select_natural_route
from fishy.potential_requirements import (
    PotentialFloorResult,
    PotentialRoute,
    PotentialStudy,
    ServiceZeroDetermination,
    size_potential_floor,
)
from fishy.presumptive_floor import PresumptiveFloor, presumptive_floor
from fishy.quality_activation import apply_quality_component
from fishy.requirement_composition import IntervalComposition, compose_requirement
from fishy.requirement_construction import NaturalRouteInputs
from fishy.requirement_family import FloorSeries, ReconstructionNeed, RequirementMember
from fishy.service_conveyance import ServiceConveyanceRequest
from fishy.source_conditions import source_period_scope
from fishy.spatial import PreparedClassification, Track, assessment_track
from fishy.study_requirements import StudyCondition, StudyNeed, StudyScope


@dataclass(frozen=True)
class EntryFloorSource:
    result: EntryResult
    route: NaturalRouteInputs


@dataclass(frozen=True)
class PresumptiveFloorSource:
    result: PresumptiveFloor
    route: NaturalRouteInputs


@dataclass(frozen=True)
class PotentialFloorSource:
    scope: StudyScope
    classification: PreparedClassification
    habitat: PotentialStudy
    hydraulics: PotentialStudy
    conveyance: ServiceConveyanceRequest | None
    review: StudyNeed
    existing_duties: tuple[SuppliedDuty, ...] = ()
    additional_conditions: tuple[StudyCondition, ...] = ()
    active_quality: tuple[StudyCondition, ...] = ()
    zero: ServiceZeroDetermination | None = None
    constant_thresholds: tuple[EvidenceFindings, ...] = ()


type DirectFloorSource = EntryFloorSource | PresumptiveFloorSource | PotentialFloorSource


@dataclass(frozen=True)
class FloorComponent:
    source: DirectFloorSource
    composition: IntervalComposition

    def __post_init__(self) -> None:
        if not isinstance(self.source, (EntryFloorSource, PresumptiveFloorSource, PotentialFloorSource)):
            raise TypeError("actual typed direct-floor source required")
        if not isinstance(self.composition, IntervalComposition):
            raise TypeError("retained floor composition required")


@dataclass(frozen=True)
class FloorConstruction:
    member: str
    components: tuple[FloorComponent, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.member, str) or not self.member.strip():
            raise ValueError("floor construction member required")
        if not isinstance(self.components, tuple) or any(not isinstance(c, FloorComponent) for c in self.components):
            raise TypeError("immutable floor construction components required")


@dataclass(frozen=True)
class FloorConstructionAssessment:
    member: RequirementMember
    construction: FloorConstruction
    sources: tuple[EntryResult | PresumptiveFloor | PotentialFloorResult, ...]
    compositions: tuple[IntervalComposition, ...]
    checks: CheckSummary


def assess_floor_source(source: DirectFloorSource):
    checks = []
    if isinstance(source, EntryFloorSource):
        original = source.result
        result = evaluate_graduated_entry(original.statistic, original.curve, original.screen)
        checks.extend(result.checks)
        route = select_natural_route(source.route.classification, source.route.tiers, source.route.failures)
        expected = NaturalRoute.ENTRY
        location = original.statistic.product.location
        if source.route.location != location:
            raise ValueError("entry classification belongs to another physical location")
        entry = next((tier for tier in source.route.tiers if tier.route is NaturalRoute.ENTRY), None)
        bound = entry is not None and any(
            s.product == original.statistic.product and s.assessment == original.statistic.assessment
            for s in entry.statistics
        )
        checks.append(
            Check(
                "entry_route_source",
                CheckFinding.PASS if bound else CheckFinding.FAIL,
                ("entry tier must use the actual statistic and its accepted assessment",),
            )
        )
        if result != original:
            checks.append(
                Check(
                    "entry_source_result", CheckFinding.FAIL, ("retained entry result differs from its actual inputs",)
                )
            )
    elif isinstance(source, PresumptiveFloorSource):
        original = source.result
        result = presumptive_floor(original.reference, original.profile)
        checks.extend(result.checks.checks)
        route = select_natural_route(
            source.route.classification, source.route.tiers, source.route.failures, presumptive=result
        )
        expected = NaturalRoute.PRESUMPTIVE
        if result.reference is not None and source.route.location != result.reference.location:
            raise ValueError("presumptive classification belongs to another natural reference location")
        if result != original:
            checks.append(
                Check(
                    "presumptive_source_result",
                    CheckFinding.FAIL,
                    ("retained floor differs from its reference/profile",),
                )
            )
    else:
        track = assessment_track(source.classification)
        if track.track is not Track.POTENTIAL:
            return None, CheckSummary(
                (
                    Check(
                        "potential_classification",
                        CheckFinding.UNKNOWN if track.track is Track.UNDETERMINED else CheckFinding.FAIL,
                        (track.reason,),
                    ),
                )
            )
        result = size_potential_floor(
            source.scope,
            source.classification,
            source.habitat,
            source.hydraulics,
            source.conveyance,
            source.review,
            existing_duties=source.existing_duties,
            additional_conditions=source.additional_conditions,
            active_quality=source.active_quality,
            zero=source.zero,
        )
        chosen = next((r for r in result.routes if r.route is result.selected_route), None)
        if chosen is None:
            for i, r in enumerate(result.routes):
                checks.extend(Check(f"route:{i}:{c.check_id}", c.finding, c.reasons) for c in r.checks.checks)
            checks.append(Check("potential_floor", CheckFinding.UNKNOWN, ("no supported potential floor route",)))
        else:
            checks.extend(chosen.checks.checks)
        for condition in (*result.additional_conditions, *result.active_quality):
            # These supplied restrictions retain their own actual scope/evidence.
            from fishy.evidence import permitted_use

            permission = permitted_use(condition.evidence, condition.evidence.scope)
            checks.append(
                Check(
                    "condition:" + condition.component,
                    condition.finding if permission.finding is CheckFinding.PASS else permission.finding,
                    (condition.criterion, *permission.reasons),
                )
            )
        return result, CheckSummary(tuple(checks))
    finding = (
        CheckFinding.PASS
        if route.selected is expected
        else CheckFinding.UNKNOWN
        if route.selected is NaturalRoute.PENDING
        else CheckFinding.FAIL
    )
    checks.append(Check("natural_floor_route", finding, route.reasons))
    for tier in route.tiers:
        if tier.evidence.route is expected:
            for name, summary in (("data", tier.data), ("eligibility", tier.eligibility)):
                checks.extend(Check(f"route:{name}:{c.check_id}", c.finding, c.reasons) for c in summary.checks)
    return result, CheckSummary(tuple(checks))


def assess_floor_construction(
    member: RequirementMember, construction: FloorConstruction
) -> FloorConstructionAssessment:
    if not isinstance(member.candidate, FloorSeries) or member.identifier != construction.member:
        raise ValueError("direct-floor construction must identify the retained floor member")
    expected = {s.interval: s for s in member.candidate.samples}
    components = {}
    for component in construction.components:
        period = component.composition.base.interval
        if period not in expected or period in components:
            raise ValueError("duplicate or undeclared direct-floor interval")
        components[period] = component
    cache = {}
    results = []
    compositions = []
    checks = []
    for period, final in expected.items():
        label = period.start.isoformat()
        if period not in components:
            checks.append(Check(label, CheckFinding.UNKNOWN, ("original direct-floor source/composition missing",)))
            continue
        component = components[period]
        source = component.source
        if id(source) not in cache:
            cache[id(source)] = assess_floor_source(source)
            if cache[id(source)][0] is not None:
                results.append(cache[id(source)][0])
        result, source_checks = cache[id(source)]
        checks.extend(Check(label + ":" + c.check_id, c.finding, c.reasons) for c in source_checks.checks)
        base = component.composition.base
        bound = False
        available = False
        temporal = Check("constant_threshold", CheckFinding.PASS)
        if isinstance(result, EntryResult):
            available = result.floor is not None
            product = result.statistic.product
            bound = (
                result.floor is not None
                and base.value == result.floor
                and base.location == product.location
                and base.provenance == product.provenance
            )
        elif isinstance(result, PresumptiveFloor):
            available = any(s.interval == base.interval and s.value is not None for s in result.samples)
            bound = any(
                (s.location, s.interval, s.value, s.provenance)
                == (base.location, base.interval, base.value, base.provenance)
                for s in result.samples
            )
        elif isinstance(result, PotentialFloorResult):
            available = result.floor is not None
            temporal = Check("constant_threshold", CheckFinding.PASS)
            if base.interval != result.scope.period:
                temporal = Check(
                    "constant_threshold",
                    CheckFinding.UNKNOWN,
                    ("separate constant-threshold support required; interval means cannot be disaggregated",),
                )
                if isinstance(source, PotentialFloorSource):
                    study = (
                        source.habitat
                        if result.selected_route is PotentialRoute.HABITAT
                        else source.hydraulics
                        if result.selected_route is PotentialRoute.HYDRAULIC
                        else None
                    )
                    if study is not None and study.selection is not None:
                        subject = source_period_scope(study.selection, study.relations)
                        permission = next((e for e in source.constant_thresholds if e.scope == subject), None)
                        if permission is not None:
                            temporal = permitted_use(permission, subject)
                if not (
                    result.scope.period.start <= base.interval.start and base.interval.end <= result.scope.period.end
                ):
                    temporal = Check(
                        "constant_threshold", CheckFinding.FAIL, ("daily floor outside supported source period",)
                    )
                checks.append(Check(label + ":constant_threshold", temporal.finding, temporal.reasons))
            bound = (
                result.floor is not None
                and base.value == result.floor
                and base.location == result.scope.location
                and temporal.finding is CheckFinding.PASS
                and base.provenance.scenario == result.scope.scenario
                and base.provenance.reference_member == result.scope.reference_member
            )
        checks.append(
            Check(
                label + ":source_binding",
                CheckFinding.PASS
                if bound
                else CheckFinding.UNKNOWN
                if isinstance(result, PotentialFloorResult) and temporal.finding is CheckFinding.UNKNOWN
                else CheckFinding.FAIL
                if available
                else CheckFinding.UNKNOWN,
                ("daily base floor must match its actual route-specific source",),
            )
        )
        q = component.composition.quality
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
                q.final_check.arrival if q.final_check else None,
            )
        mapping = component.composition.mapping
        recomputed = compose_requirement(
            base,
            final.provenance,
            quality=q,
            mapping=mapping.mapping if mapping else None,
            mapping_evidence=mapping.evidence if mapping else None,
        )
        compositions.append(recomputed)
        checks.extend(
            Check(label + ":composition:" + c.check_id, c.finding, c.reasons) for c in recomputed.checks.checks
        )
        candidate = recomputed.candidate
        bound = candidate is not None and (
            candidate.location,
            candidate.interval,
            candidate.value,
            candidate.provenance,
        ) == (final.location, final.interval, final.value, final.provenance)
        checks.append(
            Check(
                label + ":final_binding",
                CheckFinding.PASS if bound else CheckFinding.UNKNOWN if candidate is None else CheckFinding.FAIL,
                ("final direct floor must equal its actual quality-adjusted composition",),
            )
        )
    return FloorConstructionAssessment(
        member, construction, tuple(results), tuple(compositions), CheckSummary(tuple(checks))
    )


def floor_reconstruction_need(source: DirectFloorSource) -> ReconstructionNeed:
    """Derive structural applicability from the accepted source, not selection flags."""
    if isinstance(source, PotentialFloorSource):
        return ReconstructionNeed.NOT_REQUIRED
    if isinstance(source, EntryFloorSource):
        product = source.result.statistic.product
        direct = (
            product.provenance.reference_kind is ReferenceKind.OBSERVED
            and source.result.statistic.assessment.acceptance_for(product).finding is CheckFinding.PASS
        )
        return ReconstructionNeed.NOT_REQUIRED if direct else ReconstructionNeed.REQUIRED
    reference = source.result.reference
    if reference is None or reference.use_checks.finding is not CheckFinding.PASS:
        return ReconstructionNeed.REQUIRED
    # An imported/illustrative hydrograph alone cannot establish direct observations.
    # Require the exact accepted daily values to retain actual observation leaves.
    annual = reference.magnitude.reference
    from fishy.annual_statistics import AnnualReference

    if not isinstance(annual, AnnualReference):
        return ReconstructionNeed.REQUIRED

    def observations(sample):
        if sample.components:
            return tuple(leaf for component in sample.components for leaf in observations(component))
        return (sample,) if sample.provenance.production_method is ProductionMethod.OBSERVED else ()

    original = tuple(leaf for sample in annual.observations for leaf in observations(sample))
    return (
        ReconstructionNeed.REQUIRED
        if not reference.samples or any(sample not in original for sample in reference.samples)
        else ReconstructionNeed.NOT_REQUIRED
    )
