"""assess_study : StudySelection × FlowResponseRelation → StudyAssessment (pure).

Selected curve points are supplied ecological decisions, never inferred minima.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    ReferenceKind,
    permitted_use,
    warmup_restrictions,
)
from fishy.hydraulics import Comparison, HydraulicRelationEvidence, RelationDomain, StateBounds
from fishy.quantities import Flow
from fishy.spatial import Location, PreparedClassification, Track, assessment_track
from fishy.time import Interval


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("study identity, reference and source must be nonempty")


class StudyVariable(StrEnum):
    HABITAT = "habitat"
    DEPTH = "depth"
    VELOCITY = "velocity"
    DISCHARGE = "discharge"


@dataclass(frozen=True)
class ResponseVariable:
    variable: StudyVariable
    units: str
    reference: str
    domain: str

    def __post_init__(self) -> None:
        for value in (self.units, self.reference, self.domain):
            _text(value)
        if not isinstance(self.variable, StudyVariable):
            raise TypeError("StudyVariable required")
        units = {StudyVariable.DEPTH: "m", StudyVariable.VELOCITY: "m/s", StudyVariable.DISCHARGE: "m3/s"}
        if self.variable in units and self.units != units[self.variable]:
            raise ValueError("incompatible response units")


@dataclass(frozen=True)
class StudyScope:
    candidate: str
    location: Location
    period: Interval
    scenario: str
    reference_member: str | None
    purpose: str
    season: str

    def __post_init__(self) -> None:
        for value in (self.candidate, self.scenario, self.purpose, self.season):
            _text(value)
        if not isinstance(self.location, Location) or not isinstance(self.period, Interval):
            raise TypeError("typed location and interval required")
        if self.reference_member is not None:
            _text(self.reference_member)


def _evidence(scope: StudyScope, evidence: EvidenceFindings) -> None:
    if not isinstance(evidence, EvidenceFindings):
        raise TypeError("EvidenceFindings required")
    if (
        evidence.scope.product != scope.candidate
        or evidence.scope.reach != scope.location.reach.identifier
        or evidence.scope.period != scope.period
        or evidence.scope.member != scope.reference_member
        or evidence.scope.intended_use != scope.purpose
        or evidence.provenance.scenario != scope.scenario
        or evidence.provenance.reference_member != scope.reference_member
    ):
        raise ValueError("study evidence has incompatible candidate, reach, member, period, purpose or scenario")


def _supported(evidence: EvidenceFindings) -> bool:
    return permitted_use(evidence, evidence.scope).finding is CheckFinding.PASS and not warmup_restrictions(
        evidence.provenance, evidence.scope.period
    )


class Interpolation(StrEnum):
    EXACT = "exact_points_only"
    LINEAR = "supported_piecewise_linear"


@dataclass(frozen=True)
class ResponsePoint:
    flow: Flow
    response: StateBounds

    def __post_init__(self) -> None:
        if not isinstance(self.flow, Flow) or not isinstance(self.response, StateBounds):
            raise TypeError("Flow and StateBounds required")


@dataclass(frozen=True)
class FlowResponseRelation:
    scope: StudyScope
    variable: ResponseVariable
    points: tuple[ResponsePoint, ...]
    interpolation: Interpolation
    survey: str
    metadata: HydraulicRelationEvidence
    evidence: EvidenceFindings

    def __post_init__(self) -> None:
        _evidence(self.scope, self.evidence)
        _text(self.survey)
        if not isinstance(self.variable, ResponseVariable) or not isinstance(self.metadata, HydraulicRelationEvidence):
            raise TypeError("response variable and relation metadata required")
        if not isinstance(self.interpolation, Interpolation):
            raise TypeError("declared interpolation required")
        if (
            not isinstance(self.points, tuple)
            or not self.points
            or any(not isinstance(p, ResponsePoint) for p in self.points)
        ):
            raise ValueError("nonempty immutable relation points required")
        if any(a.flow.value >= b.flow.value for a, b in zip(self.points, self.points[1:], strict=False)):
            raise ValueError("relation flows must be strictly increasing; contradictory duplicates refused")
        if self.variable.variable in (StudyVariable.HABITAT, StudyVariable.DEPTH, StudyVariable.DISCHARGE) and any(
            p.response.lower < 0 for p in self.points
        ):
            raise ValueError("nonnegative response domain violated")

    def evaluate(self, flow: Flow) -> StateBounds | None:
        """Evaluate the declared relation only; neither extrapolate nor invert it."""
        for point in self.points:
            if point.flow == flow:
                return point.response
        if self.interpolation is Interpolation.LINEAR:
            for left, right in zip(self.points, self.points[1:], strict=False):
                if left.flow.value < flow.value < right.flow.value:
                    weight = (flow.value - left.flow.value) / (right.flow.value - left.flow.value)
                    return StateBounds(
                        left.response.lower + weight * (right.response.lower - left.response.lower),
                        left.response.upper + weight * (right.response.upper - left.response.upper),
                    )
        return None


@dataclass(frozen=True)
class StudyCriterion:
    identifier: str
    variable: ResponseVariable
    acceptable: StateBounds
    lower_comparison: Comparison
    upper_comparison: Comparison
    source: str

    def __post_init__(self) -> None:
        _text(self.identifier)
        _text(self.source)
        if not isinstance(self.variable, ResponseVariable) or not isinstance(self.acceptable, StateBounds):
            raise TypeError("typed criterion variable and bounds required")
        if not isinstance(self.lower_comparison, Comparison) or not isinstance(self.upper_comparison, Comparison):
            raise TypeError("explicit endpoint comparisons required")


def _compare(value: StateBounds, criterion: StudyCriterion) -> CheckFinding:
    low, high = criterion.acceptable.lower, criterion.acceptable.upper
    above = value.lower >= low if criterion.lower_comparison is Comparison.INCLUSIVE else value.lower > low
    below = value.upper <= high if criterion.upper_comparison is Comparison.INCLUSIVE else value.upper < high
    outside_low = value.upper < low if criterion.lower_comparison is Comparison.INCLUSIVE else value.upper <= low
    outside_high = value.lower > high if criterion.upper_comparison is Comparison.INCLUSIVE else value.lower >= high
    return (
        CheckFinding.PASS
        if above and below
        else CheckFinding.FAIL
        if outside_low or outside_high
        else CheckFinding.UNKNOWN
    )


@dataclass(frozen=True)
class StudyCondition:
    """Attributed specialist assessment for a named component, never a bare pass flag."""

    scope: StudyScope
    component: str
    variable: str
    units: str
    domain: str
    criterion: str
    assessed_value: str
    finding: CheckFinding
    evidence: EvidenceFindings

    def __post_init__(self) -> None:
        _evidence(self.scope, self.evidence)
        for value in (self.component, self.variable, self.units, self.domain, self.criterion, self.assessed_value):
            _text(value)
        if not isinstance(self.finding, CheckFinding):
            raise TypeError("CheckFinding required")


@dataclass(frozen=True)
class StudySelection:
    scope: StudyScope
    selected_flow: Flow
    selection_source: str
    objective: str
    evidence: EvidenceFindings
    criteria: tuple[StudyCriterion, ...]
    required_conditions: tuple[str, ...]
    conditions: tuple[StudyCondition, ...] = ()
    holistic_assessment: StudyCondition | None = None

    def __post_init__(self) -> None:
        _evidence(self.scope, self.evidence)
        _text(self.selection_source)
        _text(self.objective)
        if not isinstance(self.selected_flow, Flow):
            raise TypeError("Flow required")
        for items in (self.criteria, self.required_conditions, self.conditions):
            if not isinstance(items, tuple):
                raise TypeError("immutable criteria and conditions required")
        ids = tuple(c.identifier for c in self.criteria) + self.required_conditions
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate required study components")
        for name in self.required_conditions:
            _text(name)
        supplied = tuple(c.component for c in self.conditions)
        if len(set(supplied)) != len(supplied) or set(supplied) - set(self.required_conditions):
            raise ValueError("duplicate or undeclared supplied condition")
        if any(c.scope != self.scope for c in self.conditions):
            raise ValueError("condition must assess the same candidate, season and domain")
        if self.holistic_assessment is not None:
            if (
                self.holistic_assessment.scope != self.scope
                or self.holistic_assessment.component != "holistic_objective"
            ):
                raise ValueError("holistic objective must assess the exact candidate scope")
            if "holistic_objective" in ids:
                raise ValueError("duplicate holistic objective")


@dataclass(frozen=True)
class ResponseAssessment:
    criterion: StudyCriterion
    relation: FlowResponseRelation | None
    value: StateBounds | None
    check: Check


@dataclass(frozen=True)
class StudyAssessment:
    selection: StudySelection
    responses: tuple[ResponseAssessment, ...]
    checks: CheckSummary

    @property
    def supported_flow(self) -> Flow | None:
        return self.selection.selected_flow if self.checks.finding is CheckFinding.PASS else None


def assess_study(selection: StudySelection, relations: tuple[FlowResponseRelation, ...]) -> StudyAssessment:
    """Assess every condition on the explicitly selected flow in the exact study scope."""
    if any(r.scope != selection.scope for r in relations):
        raise ValueError("relation must assess the same candidate, location, time and scenario")
    if len({r.variable for r in relations}) != len(relations):
        raise ValueError("duplicate response relations")
    by_variable = {r.variable: r for r in relations}
    checks = [
        Check(
            "selection_support",
            CheckFinding.PASS if _supported(selection.evidence) else CheckFinding.UNKNOWN,
            (selection.selection_source,),
        )
    ]
    responses = []
    if selection.holistic_assessment is not None:
        holistic = selection.holistic_assessment
        checks.append(
            Check(
                "holistic_objective",
                holistic.finding if _supported(holistic.evidence) else CheckFinding.UNKNOWN,
                (holistic.criterion, holistic.assessed_value),
            )
        )
    elif not selection.criteria:
        checks.append(Check("ecological_criterion", CheckFinding.UNKNOWN, ("missing selected ecological criterion",)))
    for criterion in selection.criteria:
        relation = by_variable.get(criterion.variable)
        value = relation.evaluate(selection.selected_flow) if relation else None
        finding = CheckFinding.UNKNOWN
        reasons = ("required accepted relation or supported operating domain missing",)
        if (
            relation
            and value is not None
            and _supported(relation.evidence)
            and relation.metadata.domain_state is RelationDomain.SUPPORTED
        ):
            finding = _compare(value, criterion)
            reasons = (criterion.source, "configured criterion only; not ecological certification")
        check = Check(criterion.identifier, finding, reasons)
        checks.append(check)
        responses.append(ResponseAssessment(criterion, relation, value, check))
    by_component = {c.component: c for c in selection.conditions}
    for component in selection.required_conditions:
        supplied = by_component.get(component)
        checks.append(
            Check(
                component,
                supplied.finding if supplied and _supported(supplied.evidence) else CheckFinding.UNKNOWN,
                (supplied.criterion,) if supplied else ("required study condition missing",),
            )
        )
    return StudyAssessment(selection, tuple(responses), CheckSummary(tuple(checks)))


@dataclass(frozen=True)
class StudyNeed:
    reason: str
    owner: str | None
    deadline: date | None

    def __post_init__(self) -> None:
        _text(self.reason)
        if self.owner is not None:
            _text(self.owner)
        if self.deadline is not None and not isinstance(self.deadline, date):
            raise TypeError("dated study milestone required")


class TopTierEligibility(StrEnum):
    PRIORITY = "specified_resourced_priority"
    TRIGGERED = "specified_resourced_triggered"
    UNRESOURCED = "not_resourced"
    NOT_SELECTED = "not_priority_or_triggered"


class HighFlowTrigger(StrEnum):
    SEDIMENT_TRAPPING = "below_sediment_trapping_reservoir"
    OTHER_SUPPORTED = "other_supplied_trigger"
    NONE = "none_identified"


@dataclass(frozen=True)
class NaturalStudyComponent:
    name: str
    study: StudySelection
    relations: tuple[FlowResponseRelation, ...]
    kind: str

    def __post_init__(self) -> None:
        _text(self.name)
        if self.kind not in ("seasonal", "pulse"):
            raise ValueError("component kind must be seasonal or pulse")


@dataclass(frozen=True)
class NaturalStudyResult:
    classification: PreparedClassification
    components: tuple[StudyAssessment, ...]
    supported_components: tuple[tuple[str, Flow], ...]
    checks: CheckSummary
    trigger: HighFlowTrigger
    study_need: StudyNeed
    next_route: str | None
    baseline_median_cap: Flow | None
    release_permission: str = "not_granted_by_calculation"


def assess_natural_study(
    classification: PreparedClassification,
    eligibility: TopTierEligibility,
    required_components: tuple[str, ...],
    components: tuple[NaturalStudyComponent, ...],
    trigger: HighFlowTrigger,
    study_need: StudyNeed,
    descent_route: str,
    *,
    baseline_median_cap: Flow | None = None,
) -> NaturalStudyResult:
    """Produce uncapped study components; baseline cap is diagnostic, never a pulse cap."""
    _text(descent_route)
    if assessment_track(classification).track is not Track.NATURAL:
        raise ValueError("new natural calculations require an eligible natural track")
    if not isinstance(eligibility, TopTierEligibility) or not isinstance(trigger, HighFlowTrigger):
        raise TypeError("typed eligibility and trigger required")
    if len(set(required_components)) != len(required_components) or len({c.name for c in components}) != len(
        components
    ):
        raise ValueError("duplicate natural components")
    if {c.name for c in components} - set(required_components):
        raise ValueError("undeclared natural component")
    if components:
        first = components[0].study.scope
        if first.reference_member is None:
            raise ValueError("natural study requires a named natural reference member")
        for component in components:
            scope = component.study.scope
            if (scope.location, scope.scenario, scope.reference_member) != (
                first.location,
                first.scenario,
                first.reference_member,
            ):
                raise ValueError("natural components require one location, scenario and reference member")
    checks = [
        Check(
            "eligibility",
            CheckFinding.PASS
            if eligibility in (TopTierEligibility.PRIORITY, TopTierEligibility.TRIGGERED)
            else CheckFinding.UNKNOWN,
            (eligibility.value,),
        )
    ]
    if not required_components:
        checks.append(Check("study_components", CheckFinding.UNKNOWN, ("no required components declared",)))
    if trigger is not HighFlowTrigger.NONE:
        assigned = study_need.owner is not None and study_need.deadline is not None
        checks.append(
            Check(
                "trigger_assignment",
                CheckFinding.PASS if assigned else CheckFinding.UNKNOWN,
                (study_need.reason, "accountable owner and deadline required for escalation"),
            )
        )
    if trigger is HighFlowTrigger.SEDIMENT_TRAPPING and not any(c.kind == "pulse" for c in components):
        checks.append(Check("high_flow_assessment", CheckFinding.UNKNOWN, ("mandatory high-flow study missing",)))
    assessed = []
    supported = []
    by_name = {c.name: c for c in components}
    for name in required_components:
        component = by_name.get(name)
        if component is None:
            checks.append(Check(name, CheckFinding.UNKNOWN, ("required study component missing",)))
            continue
        result = assess_study(component.study, component.relations)
        assessed.append(result)
        checks.extend(Check(f"{name}:{c.check_id}", c.finding, c.reasons) for c in result.checks.checks)
        if component.kind == "pulse":
            required = {"sediment", "hydraulic", "flood_safety", "ramping"}
            absent = required - set(component.study.required_conditions)
            for condition in sorted(absent):
                checks.append(
                    Check(
                        f"{name}:pulse_{condition}",
                        CheckFinding.UNKNOWN,
                        ("pulse requires joint sediment, hydraulic, flood-safety and ramping evidence",),
                    )
                )
        else:
            absent = set()
        references = (
            component.study.evidence,
            *(r.evidence for r in component.relations),
            *(c.evidence for c in component.study.conditions),
        )
        if component.study.holistic_assessment is not None:
            references += (component.study.holistic_assessment.evidence,)
        natural_reference = all(
            e.provenance.reference_kind is ReferenceKind.PRESENT_CLIMATE_NATURAL for e in references
        )
        if not natural_reference:
            checks.append(
                Check(
                    f"{name}:natural_reference",
                    CheckFinding.UNKNOWN,
                    ("present-climate natural reference required; other arithmetic remains exploratory",),
                )
            )
        eligible = eligibility in (TopTierEligibility.PRIORITY, TopTierEligibility.TRIGGERED)
        escalation_ready = trigger is HighFlowTrigger.NONE or (
            study_need.owner is not None and study_need.deadline is not None
        )
        if result.supported_flow is not None and not absent and natural_reference and eligible and escalation_ready:
            supported.append((name, result.supported_flow))
    summary = CheckSummary(tuple(checks))
    return NaturalStudyResult(
        classification,
        tuple(assessed),
        tuple(supported),
        summary,
        trigger,
        study_need,
        None if summary.finding is CheckFinding.PASS else descent_route,
        baseline_median_cap,
    )
