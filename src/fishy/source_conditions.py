"""source_conditions : StudySelection × FlowResponseRelation* × FlowSample × StudyAssessment? → SourceConditionAssessment.

Original constraints survive quality and receptor uplift. Their supported response
relations supply numerical diagnostics, never a relabelled final acceptance.
"""

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from fishy.evidence import Check, CheckFinding, CheckSummary, EvidenceFindings, EvidenceScope, permitted_use
from fishy.flows import Coverage, FlowSample, Presence
from fishy.hydraulics import RelationDomain
from fishy.quantities import Flow
from fishy.receptor_delivery import ControlEquivalent, WaterRelationship, control_equivalent
from fishy.requirement_checks import sample_subject
from fishy.study_requirements import (
    FlowResponseRelation,
    ResponseAssessment,
    StudyAssessment,
    StudyCondition,
    StudySelection,
    _compare,
    _supported,
    assess_study,
)


class SourcePeriodMapping(StrEnum):
    EXACT = "exact_source_period"
    CONSTANT_THRESHOLD = "separately_supported_constant_threshold_application"


def source_period_scope(
    source: StudySelection | StudyCondition,
    relations: tuple[FlowResponseRelation, ...] = (),
) -> EvidenceScope:
    """Original constraint, relations and full declared period → temporal permission subject."""
    if not isinstance(source, (StudySelection, StudyCondition)):
        raise TypeError("typed source constraint required")
    if not isinstance(relations, tuple) or any(not isinstance(r, FlowResponseRelation) for r in relations):
        raise TypeError("immutable original response relations required")
    digest = sha256(repr((source, relations)).encode()).hexdigest()
    scope = source.scope
    return EvidenceScope(
        "source-period:" + digest,
        scope.location.reach.identifier,
        scope.reference_member,
        scope.period,
        "constant_threshold",
    )


def _period_check(
    source: StudySelection | StudyCondition,
    final: FlowSample,
    mapping: SourcePeriodMapping,
    permission: EvidenceFindings | None,
    relations: tuple[FlowResponseRelation, ...] = (),
) -> Check:
    if not isinstance(mapping, SourcePeriodMapping):
        raise TypeError("explicit SourcePeriodMapping required")
    if permission is not None and not isinstance(permission, EvidenceFindings):
        raise TypeError("typed temporal permission required")
    if mapping is SourcePeriodMapping.EXACT:
        return Check(
            "period_application",
            CheckFinding.PASS if source.scope.period == final.interval else CheckFinding.FAIL,
            ("source period must match; no implicit seasonal-to-daily equivalence",),
        )
    if not (source.scope.period.start <= final.interval.start and final.interval.end <= source.scope.period.end):
        return Check("period_application", CheckFinding.FAIL, ("receiving interval outside supported source period",))
    if final.interval.seconds != 86400:
        return Check(
            "period_application",
            CheckFinding.UNKNOWN,
            (
                "constant-threshold permission supports fixed daily application only; no subdaily or aggregate equivalence",
            ),
        )
    if permission is None:
        return Check(
            "period_application", CheckFinding.UNKNOWN, ("separate constant-threshold temporal permission missing",)
        )
    for field in (
        "scenario",
        "reference_member",
        "reference_kind",
        "configuration_version",
        "data_version",
        "software_version",
    ):
        if getattr(permission.provenance, field) != getattr(source.evidence.provenance, field):
            return Check(
                "period_application", CheckFinding.FAIL, ("temporal permission belongs to another source identity",)
            )
    check = permitted_use(permission, source_period_scope(source, relations))
    return Check("period_application", check.finding, check.reasons)


@dataclass(frozen=True)
class SourceConditionAssessment:
    source: StudySelection
    relations: tuple[FlowResponseRelation, ...]
    final: FlowSample
    mapping: ControlEquivalent | None
    local_flow: Flow | None
    supplied: StudyAssessment | None
    responses: tuple[ResponseAssessment, ...]
    checks: CheckSummary
    period_mapping: SourcePeriodMapping
    period_permission: EvidenceFindings | None


def _condition_policy(condition: StudyCondition):
    return condition.component, condition.variable, condition.units, condition.domain, condition.criterion


def _relation_policy(relation: FlowResponseRelation):
    # A different physical relation needs an explicit equivalence contract; no such
    # contract is inferred from a new candidate's favourable numerical answer.
    return relation.variable, relation.points, relation.interpolation, relation.survey, relation.metadata


def _local_flow(
    source: StudySelection | StudyCondition,
    final: FlowSample,
    mapping: ControlEquivalent | None,
    period_mapping: SourcePeriodMapping = SourcePeriodMapping.EXACT,
    period_permission: EvidenceFindings | None = None,
    relations: tuple[FlowResponseRelation, ...] = (),
):
    if mapping is not None and not isinstance(mapping, ControlEquivalent):
        raise TypeError("typed supported control mapping required")
    checks = [_period_check(source, final, period_mapping, period_permission, relations)]
    if final.provenance.scenario != source.scope.scenario:
        return None, [*checks, Check("source_domain", CheckFinding.FAIL, ("source and final scenarios differ",))]
    if checks[0].finding is not CheckFinding.PASS:
        return None, checks
    if final.presence is not Presence.PRESENT or final.coverage is not Coverage.COMPLETE or final.value is None:
        return None, [Check("final_coverage", CheckFinding.UNKNOWN, ("complete final flow unavailable",))]
    if final.location == source.scope.location:
        return final.value, checks
    if mapping is None:
        return None, [
            Check("source_mapping", CheckFinding.UNKNOWN, ("source section needs supported final control mapping",))
        ]
    m = mapping.mapping
    if (m.control, m.continuing_location, m.context.period, m.context.candidate) != (
        final.location,
        source.scope.location,
        final.interval,
        sample_subject(final),
    ):
        return None, [
            Check("source_mapping", CheckFinding.FAIL, ("mapping does not bind the exact final and source section",))
        ]
    for field in ("scenario", "reference_member", "reference_kind", "configuration_version"):
        if getattr(m.context.provenance, field) != getattr(final.provenance, field):
            return None, [
                Check("source_mapping_identity", CheckFinding.FAIL, ("mapping belongs to different final inputs",))
            ]
    assessed = control_equivalent(m, mapping.evidence)
    if assessed.upstream is None:
        return None, [Check("source_mapping", CheckFinding.UNKNOWN, assessed.reasons)]
    if assessed.upstream != final.value:
        return None, [Check("source_mapping", CheckFinding.FAIL, ("mapped flow differs from final candidate",))]
    # SAME_WATER's continuing operand is only a lower bound, not the actual shared
    # through-flow. LATERAL instead removes the separately mapped diversion.
    return (final.value if m.relationship is WaterRelationship.SAME_WATER else m.continuing), checks


def assess_source_conditions(
    source: StudySelection,
    relations: tuple[FlowResponseRelation, ...],
    final: FlowSample,
    *,
    mapping: ControlEquivalent | None = None,
    supplied: StudyAssessment | None = None,
    period_mapping: SourcePeriodMapping = SourcePeriodMapping.EXACT,
    period_permission: EvidenceFindings | None = None,
) -> SourceConditionAssessment:
    """Derive compulsory source tests independently of the caller's final manifest.

    Re-evaluate the original supported relation at the actual source-section flow.
    An original supported violation remains FAIL when fresh final evidence is
    omitted. Original scope/provenance are retained unchanged. A numerical pass
    is not final permission: matching newly scoped scientific/process support is
    required, including each temporal and holistic criterion. A different relation
    is refused unless a future explicit equivalence contract supports it.
    """
    if not isinstance(source, StudySelection) or not isinstance(final, FlowSample):
        raise TypeError("typed original study and final sample required")
    if not isinstance(relations, tuple) or any(not isinstance(r, FlowResponseRelation) for r in relations):
        raise TypeError("immutable original response relations required")
    if supplied is not None and not isinstance(supplied, StudyAssessment):
        raise TypeError("supplied final study requires StudyAssessment")
    original = assess_study(source, relations)
    checks = [Check("source:" + c.check_id, c.finding, c.reasons) for c in original.checks.checks]
    flow, location_checks = _local_flow(source, final, mapping, period_mapping, period_permission, relations)
    checks.extend(location_checks)
    by_variable = {r.variable: r for r in relations}
    responses = []
    for criterion in source.criteria:
        relation = by_variable.get(criterion.variable)
        value = relation.evaluate(flow) if relation is not None and flow is not None else None
        numerical = _compare(value, criterion) if value is not None else None
        supported = (
            relation is not None
            and _supported(relation.evidence)
            and _supported(source.evidence)
            and relation.metadata.domain_state is RelationDomain.SUPPORTED
        )
        finding = numerical if supported and numerical is not None else CheckFinding.UNKNOWN
        check = Check(
            "original_response:" + criterion.identifier,
            finding,
            ("original accepted relation evaluated at actual final source-section flow; not new candidate acceptance",),
        )
        responses.append(ResponseAssessment(criterion, relation, value, check, numerical))
        checks.append(check)
    evaluated = None
    if supplied is None:
        checks.append(
            Check(
                "final_study",
                CheckFinding.UNKNOWN,
                ("original source permission cannot substitute for final candidate support",),
            )
        )
        for name in source.required_conditions:
            checks.append(
                Check(
                    "final_condition:" + name,
                    CheckFinding.UNKNOWN,
                    ("source-required final process/temporal evidence missing",),
                )
            )
        if source.holistic_assessment is not None:
            checks.append(
                Check("final_holistic", CheckFinding.UNKNOWN, ("source-required final holistic evidence missing",))
            )
    else:
        chosen = supplied.selection
        expected = (
            sample_subject(final),
            source.scope.location,
            final.interval,
            final.provenance.scenario,
            final.provenance.reference_member,
            source.scope.purpose,
            source.scope.season,
        )
        actual = (
            chosen.scope.candidate,
            chosen.scope.location,
            chosen.scope.period,
            chosen.scope.scenario,
            chosen.scope.reference_member,
            chosen.scope.purpose,
            chosen.scope.season,
        )
        scope_matches = actual == expected and all(
            getattr(chosen.evidence.provenance, f) == getattr(final.provenance, f)
            for f in ("scenario", "reference_member", "reference_kind", "configuration_version")
        )
        identity = scope_matches and flow is not None and chosen.selected_flow == flow
        identity_finding = (
            CheckFinding.FAIL
            if not scope_matches or flow is not None and chosen.selected_flow != flow
            else CheckFinding.UNKNOWN
            if flow is None
            else CheckFinding.PASS
        )
        checks.append(
            Check(
                "final_study_identity",
                identity_finding,
                ("final study must bind exact final subject, source-section flow, period, purpose and season",),
            )
        )
        final_relations = tuple(r.relation for r in supplied.responses if r.relation is not None)
        evaluated = assess_study(chosen, final_relations)
        if identity:
            checks.extend(Check("final:" + c.check_id, c.finding, c.reasons) for c in evaluated.checks.checks)
        final_criteria = {c.identifier: c for c in chosen.criteria}
        final_relation = {r.variable: r for r in final_relations}
        for criterion in source.criteria:
            actual_criterion = final_criteria.get(criterion.identifier)
            checks.append(
                Check(
                    "criterion_policy:" + criterion.identifier,
                    CheckFinding.UNKNOWN
                    if actual_criterion is None
                    else CheckFinding.PASS
                    if actual_criterion == criterion
                    else CheckFinding.FAIL,
                    ("original criterion, bounds, units and strictness cannot be omitted or changed",),
                )
            )
            original_relation = by_variable.get(criterion.variable)
            actual_relation = final_relation.get(criterion.variable)
            match = (
                original_relation is not None
                and actual_relation is not None
                and _relation_policy(original_relation) == _relation_policy(actual_relation)
            )
            checks.append(
                Check(
                    "relation_policy:" + criterion.identifier,
                    CheckFinding.PASS
                    if match
                    else CheckFinding.UNKNOWN
                    if actual_relation is None
                    else CheckFinding.FAIL,
                    ("original physical response, geometry, validity and interpolation must be preserved",),
                )
            )
        old_conditions = {c.component: c for c in source.conditions}
        new_conditions = {c.component: c for c in chosen.conditions}
        for name in source.required_conditions:
            old, new = old_conditions.get(name), new_conditions.get(name)
            match = (
                old is not None
                and new is not None
                and name in chosen.required_conditions
                and _condition_policy(old) == _condition_policy(new)
            )
            checks.append(
                Check(
                    "condition_policy:" + name,
                    CheckFinding.PASS if match else CheckFinding.UNKNOWN if new is None else CheckFinding.FAIL,
                    (
                        "source temporal/process criterion must remain required with unchanged variable, units and limits",
                    ),
                )
            )
        if source.holistic_assessment is not None:
            new = chosen.holistic_assessment
            match = new is not None and _condition_policy(source.holistic_assessment) == _condition_policy(new)
            checks.append(
                Check(
                    "holistic_policy",
                    CheckFinding.PASS if match else CheckFinding.UNKNOWN if new is None else CheckFinding.FAIL,
                    ("source holistic objective cannot disappear or change at final selection",),
                )
            )
    return SourceConditionAssessment(
        source,
        relations,
        final,
        mapping,
        flow,
        evaluated,
        tuple(responses),
        CheckSummary(tuple(checks)),
        period_mapping,
        period_permission,
    )


@dataclass(frozen=True)
class ProcessConditionAssessment:
    sources: tuple[StudyCondition, ...]
    final: FlowSample
    mapping: ControlEquivalent | None
    supplied: StudyAssessment | None
    period_mapping: SourcePeriodMapping
    period_permissions: tuple[EvidenceFindings, ...]
    checks: CheckSummary


def assess_process_conditions(
    conditions: tuple[StudyCondition, ...],
    final: FlowSample,
    *,
    mapping: ControlEquivalent | None = None,
    supplied: StudyAssessment | None = None,
    period_mapping: SourcePeriodMapping = SourcePeriodMapping.EXACT,
    period_permissions: tuple[EvidenceFindings, ...] = (),
) -> ProcessConditionAssessment:
    """Bind supplemental process requirements without inventing a source study or evidence.

    Each original condition requires a freshly scoped counterpart with the same
    variable, units, domain and criterion, explicitly required by the final study.
    One full-source permission per condition may support daily application; the
    original process result itself is never relabelled to the changed candidate.
    """
    if not isinstance(conditions, tuple) or any(not isinstance(c, StudyCondition) for c in conditions):
        raise TypeError("immutable actual source process conditions required")
    if not isinstance(final, FlowSample) or supplied is not None and not isinstance(supplied, StudyAssessment):
        raise TypeError("typed final flow and optional final study required")
    if not isinstance(period_permissions, tuple) or any(
        not isinstance(e, EvidenceFindings) for e in period_permissions
    ):
        raise TypeError("immutable temporal permission findings required")
    if len({e.scope for e in period_permissions}) != len(period_permissions):
        raise ValueError("duplicate process temporal permission")
    checks = []
    for index, condition in enumerate(conditions):
        label = f"process:{index}:{condition.component}"
        checks.append(
            Check(
                label + ":source_support",
                CheckFinding.PASS if _supported(condition.evidence) else CheckFinding.UNKNOWN,
                ("source condition needs supported declared applicability",),
            )
        )
        permission = next((e for e in period_permissions if e.scope == source_period_scope(condition)), None)
        flow, domain_checks = _local_flow(condition, final, mapping, period_mapping, permission)
        checks.extend(Check(label + ":" + c.check_id, c.finding, c.reasons) for c in domain_checks)
        if supplied is None:
            checks.append(
                Check(label + ":final", CheckFinding.UNKNOWN, ("source-required fresh final process evidence missing",))
            )
            continue
        chosen = supplied.selection
        scope = chosen.scope
        identity = (
            scope.candidate,
            scope.location,
            scope.period,
            scope.scenario,
            scope.reference_member,
            scope.purpose,
            scope.season,
        ) == (
            sample_subject(final),
            condition.scope.location,
            final.interval,
            final.provenance.scenario,
            final.provenance.reference_member,
            condition.scope.purpose,
            condition.scope.season,
        )
        identity = identity and all(
            getattr(chosen.evidence.provenance, f) == getattr(final.provenance, f)
            for f in ("scenario", "reference_member", "reference_kind", "configuration_version")
        )
        if not identity or flow is not None and chosen.selected_flow != flow:
            checks.append(
                Check(
                    label + ":identity",
                    CheckFinding.FAIL,
                    ("process evidence identifies another final candidate/domain",),
                )
            )
            continue
        if flow is None:
            checks.append(Check(label + ":identity", CheckFinding.UNKNOWN, ("final local flow unavailable",)))
        counterpart = next((c for c in chosen.conditions if c.component == condition.component), None)
        required = condition.component in chosen.required_conditions
        if condition.component == "holistic_objective":
            counterpart = chosen.holistic_assessment
            required = counterpart is not None
        if counterpart is None or not required:
            checks.append(
                Check(
                    label + ":final", CheckFinding.UNKNOWN, ("original condition omitted from required final coverage",)
                )
            )
            continue
        if _condition_policy(counterpart) != _condition_policy(condition):
            checks.append(
                Check(label + ":policy", CheckFinding.FAIL, ("original process criterion changed or relaxed",))
            )
            continue
        supported = flow is not None and _supported(chosen.evidence) and _supported(counterpart.evidence)
        checks.append(
            Check(
                label + ":final",
                counterpart.finding if supported else CheckFinding.UNKNOWN,
                ("fresh supported final process finding under unchanged original criterion",),
            )
        )
    return ProcessConditionAssessment(
        conditions, final, mapping, supplied, period_mapping, period_permissions, CheckSummary(tuple(checks))
    )
