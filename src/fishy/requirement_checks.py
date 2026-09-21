"""assess_requirement : FlowSample × FinalCondition* × QualityComponent? × ControlEquivalent? × DeliveryStep? × HydraulicScope* × (StateAssessment | RateAssessment | ImportedHydraulicFinding)* × StudySelection? × FlowResponseRelation* → RequirementAssessment.

Re-evaluate quality, mapped receptors and supplied hydraulic/study evidence on the
exact final candidate. A previous pass cannot move to a changed requirement.
"""

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from fishy.evidence import Check, CheckFinding, CheckSummary
from fishy.flows import FlowSample
from fishy.hydraulics import (
    HydraulicAssessment,
    HydraulicScope,
    ImportedHydraulicFinding,
    RateAssessment,
    StateAssessment,
    assess_discrete_rate,
    assess_hydraulics,
    assess_state_range,
)
from fishy.mixing import CheckOutcome, MixingRecheck, recheck_mixing
from fishy.quality_activation import ComponentStatus, QualityComponent, apply_quality_component
from fishy.quantities import Flow
from fishy.receptor_delivery import (
    ControlEquivalent,
    DeliveryAssessment,
    DeliveryStep,
    WaterRelationship,
    assess_delivery,
    control_equivalent,
)
from fishy.study_requirements import FlowResponseRelation, StudyAssessment, StudySelection, assess_study


class FinalCondition(StrEnum):
    QUALITY = "quality"
    MAPPING = "mapping"
    RECEPTOR = "receptor"
    HYDRAULICS = "hydraulics"
    STUDY = "study"


def sample_subject(sample: FlowSample) -> str:
    """Bind final specialist evidence to values, units, location, interval and versions."""
    return "requirement:" + sha256(repr(sample).encode()).hexdigest()


@dataclass(frozen=True)
class RequirementAssessment:
    sample: FlowSample
    required: tuple[FinalCondition, ...]
    checks: CheckSummary
    quality: MixingRecheck | None
    original_quality: QualityComponent | None
    mapping: ControlEquivalent | None
    receptor: DeliveryAssessment | None
    hydraulics: HydraulicAssessment | None
    study: StudyAssessment | None


def _identity(sample: FlowSample, provenance) -> None:
    for field in ("scenario", "reference_member", "reference_kind", "configuration_version"):
        if getattr(sample.provenance, field) != getattr(provenance, field):
            raise ValueError("final physical evidence must retain candidate scenario/reference/configuration")


def assess_requirement(
    sample: FlowSample,
    required: tuple[FinalCondition, ...],
    *,
    quality: QualityComponent | None = None,
    mapping: ControlEquivalent | None = None,
    receptor: DeliveryStep | None = None,
    hydraulic_required: tuple[HydraulicScope, ...] = (),
    hydraulic_components: tuple[StateAssessment | RateAssessment | ImportedHydraulicFinding, ...] = (),
    study_selection: StudySelection | None = None,
    study_relations: tuple[FlowResponseRelation, ...] = (),
) -> RequirementAssessment:
    """Test the supplied final interval, without correcting it or inventing physical states.

    The required set comes from the declared applicable conditions. Empty sets do
    not manufacture a complete pass. Advisory quality is retained but not binding.
    Supported specialised imports remain allowed, with exact candidate identity.
    """
    if not isinstance(required, tuple) or any(not isinstance(c, FinalCondition) for c in required):
        raise TypeError("required conditions must be an immutable tuple of FinalCondition")
    if len(set(required)) != len(required):
        raise ValueError("duplicate final condition")
    supplied_conditions = (
        (FinalCondition.QUALITY, quality is not None),
        (FinalCondition.MAPPING, mapping is not None),
        (FinalCondition.RECEPTOR, receptor is not None),
        (FinalCondition.HYDRAULICS, bool(hydraulic_required or hydraulic_components)),
        (FinalCondition.STUDY, study_selection is not None or bool(study_relations)),
    )
    if any(present and condition not in required for condition, present in supplied_conditions):
        raise ValueError("supplied assessment must belong to the declared final conditions")
    checks = []
    local_flow = sample.value
    local_location = sample.location
    mapped = None
    if mapping is not None:
        m = mapping.mapping
        _identity(sample, m.context.provenance)
        if (m.control, m.context.period, m.context.candidate) != (
            sample.location,
            sample.interval,
            sample_subject(sample),
        ):
            raise ValueError("mapping must refer to the exact final candidate, control and interval")
        mapped = control_equivalent(m, mapping.evidence)
        compatible = mapped.upstream == sample.value and mapped.upstream is not None
        checks.append(
            Check(
                "mapping",
                CheckFinding.UNKNOWN
                if mapped.upstream is None
                else CheckFinding.PASS
                if compatible
                else CheckFinding.FAIL,
                mapped.reasons or ("mapped requirement must equal uncapped final control flow",),
            )
        )
        local_flow = mapped.upstream if m.relationship is WaterRelationship.SAME_WATER else m.continuing
        local_location = m.continuing_location
    elif FinalCondition.MAPPING in required:
        checks.append(Check("mapping", CheckFinding.UNKNOWN, ("required physical mapping missing",)))
    mixing = None
    if quality is not None:
        quality = apply_quality_component(
            quality.base,
            quality.quality.boundary,
            quality.quality.targets,
            quality.activation,
            quality.source_control,
            quality.accounts,
            quality.background_mapping,
            quality.quality.bounds,
            quality.final_check.arrival if quality.final_check is not None else None,
        )
        boundary = quality.quality.boundary
        _identity(sample, boundary.provenance)
        if boundary.interval != sample.interval or boundary.location != local_location:
            raise ValueError("quality boundary must match the final continuing-flow section/time")
        if quality.status is ComponentStatus.ADVISORY:
            checks.append(
                Check(
                    "quality",
                    CheckFinding.PASS,
                    ("quality remains advisory; no binding uplift or quality adequacy asserted",),
                )
            )
        elif local_flow is None or local_flow.value < boundary.background.value:
            checks.append(
                Check(
                    "quality",
                    CheckFinding.FAIL if local_flow else CheckFinding.UNKNOWN,
                    ("final flow cannot supply the fixed quality background",),
                )
            )
        else:
            mixing = recheck_mixing(
                boundary,
                quality.quality.targets,
                Flow(local_flow.value - boundary.background.value),
                quality.quality.bounds,
            )
            finding = {
                CheckOutcome.PASS: CheckFinding.PASS,
                CheckOutcome.FAIL: CheckFinding.FAIL,
                CheckOutcome.INDETERMINATE: CheckFinding.UNKNOWN,
            }[mixing.outcome]
            checks.append(Check("quality", finding, ("original quality constraints rechecked after final uplift",)))
            if quality.status in (ComponentStatus.INFEASIBLE, ComponentStatus.UNSIZED):
                checks.append(
                    Check(
                        "quality_activation",
                        CheckFinding.FAIL if quality.status is ComponentStatus.INFEASIBLE else CheckFinding.UNKNOWN,
                        quality.reasons,
                    )
                )
    elif FinalCondition.QUALITY in required:
        checks.append(Check("quality", CheckFinding.UNKNOWN, ("required local quality input missing",)))
    delivered = None
    if receptor is not None:
        context = receptor.balance.context
        _identity(sample, context.provenance)
        if context.candidate != sample_subject(sample) or context.period != sample.interval:
            raise ValueError("receptor trajectory must assess the exact final candidate and interval")
        if mapping is None:
            raise ValueError("receptor integration needs an explicit physical control mapping")
        m = mapping.mapping
        paths = tuple(
            p
            for p in receptor.pathways
            if p.pathway.control == sample.location and p.pathway.release_period == sample.interval
        )
        release = sum(p.release.value / p.pathway.release_period.seconds for p in paths)
        expected = (
            m.receptor.value
            if m.relationship is WaterRelationship.LATERAL
            else sample.value.value
            if sample.value is not None
            else None
        )
        if release != expected:
            raise ValueError("selected receptor pathway release differs from the mapped receptor flow")
        if context.receptor != m.context.receptor:
            raise ValueError("mapping and selected trajectory identify different receptors")
        delivered = assess_delivery((receptor,), period=sample.interval)
        checks.extend(Check(f"receptor:{c.check_id}", c.finding, c.reasons) for c in delivered.checks.checks)
    elif FinalCondition.RECEPTOR in required:
        checks.append(
            Check("receptor", CheckFinding.UNKNOWN, ("required receptor schedule/physical evidence missing",))
        )
    hydraulic = None
    if hydraulic_required or hydraulic_components:
        for scope in hydraulic_required:
            if (scope.candidate, scope.location, scope.period, scope.scenario) != (
                sample_subject(sample),
                scope.location,
                sample.interval,
                sample.provenance.scenario,
            ) or scope.location not in (sample.location, local_location):
                raise ValueError(
                    "hydraulic condition must identify the exact final candidate and a mapped physical location"
                )
        recalculated = []
        for component in hydraulic_components:
            if isinstance(component, StateAssessment):
                _identity(sample, component.state.evidence.provenance)
                recalculated.append(assess_state_range(component.criterion, component.state))
            elif isinstance(component, RateAssessment):
                _identity(sample, component.transition.evidence.provenance)
                recalculated.append(assess_discrete_rate(component.criterion, component.transition))
            else:
                _identity(sample, component.evidence.provenance)
                recalculated.append(component)
        hydraulic = assess_hydraulics(hydraulic_required, tuple(recalculated))
        checks.extend(Check(f"hydraulics:{c.check_id}", c.finding, c.reasons) for c in hydraulic.checks.checks)
    elif FinalCondition.HYDRAULICS in required:
        checks.append(Check("hydraulics", CheckFinding.UNKNOWN, ("required final hydraulic evidence missing",)))
    study = None
    if study_selection is not None:
        scope = study_selection.scope
        if (scope.candidate, scope.location, scope.period, scope.scenario, scope.reference_member) != (
            sample_subject(sample),
            scope.location,
            sample.interval,
            sample.provenance.scenario,
            sample.provenance.reference_member,
        ) or scope.location not in (sample.location, local_location):
            raise ValueError("study must identify the exact final candidate and a mapped physical location")
        study_flow = sample.value if scope.location == sample.location else local_flow
        if study_selection.selected_flow != study_flow:
            raise ValueError("study selected discharge differs from actual final flow at its physical location")
        _identity(sample, study_selection.evidence.provenance)
        study = assess_study(study_selection, study_relations)
        checks.extend(Check(f"study:{c.check_id}", c.finding, c.reasons) for c in study.checks.checks)
    elif FinalCondition.STUDY in required:
        checks.append(Check("study", CheckFinding.UNKNOWN, ("required final study evidence missing",)))
    return RequirementAssessment(
        sample, required, CheckSummary(tuple(checks)), mixing, quality, mapped, delivered, hydraulic, study
    )


def recheck_requirement(result: RequirementAssessment) -> RequirementAssessment:
    """Recompute retained inputs instead of trusting a replaced summary finding."""
    receptor = None
    if result.receptor is not None:
        if len(result.receptor.steps) != 1:
            raise ValueError("one matched interval receptor result required")
        receptor = result.receptor.steps[0].step
    return assess_requirement(
        result.sample,
        result.required,
        quality=result.original_quality,
        mapping=result.mapping,
        receptor=receptor,
        hydraulic_required=result.hydraulics.required if result.hydraulics else (),
        hydraulic_components=result.hydraulics.components if result.hydraulics else (),
        study_selection=result.study.selection if result.study else None,
        study_relations=tuple(r.relation for r in result.study.responses if r.relation is not None)
        if result.study
        else (),
    )
