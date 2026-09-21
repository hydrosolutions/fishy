"""recompute_provisional_duration : RequirementMembers × ConstructionAssessments × DurationTests → ProvisionalDurationAssessments.

These source diagnostics never authorize or block final-flow publication.
Final-flow predecessors and uncertainty support are not pre-quality evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from fishy.design_conditions import DesignClass
from fishy.evidence import Check, CheckFinding, CheckSummary
from fishy.flows import FlowSample
from fishy.low_flow_safeguard import AssessmentStage, LowFlowAssessment, assess_low_flow
from fishy.requirement_construction import ConstructionAssessment, StudySource
from fishy.requirement_family import RequirementFamily, RequirementMember
from fishy.study_requirements import NaturalStudyResult

if TYPE_CHECKING:
    from fishy.requirement_finalization import DurationTest


@dataclass(frozen=True)
class ProvisionalDurationAssessment:
    member: str
    identifier: str
    design: DesignClass
    source: tuple[FlowSample, ...]
    result: LowFlowAssessment | None
    checks: CheckSummary


def _actual_source(
    assessment: ConstructionAssessment | None, design: DesignClass
) -> tuple[tuple[FlowSample, ...], tuple[Check, ...]]:
    if assessment is None:
        return (), ()
    native = assessment.recomputed_source
    if not isinstance(native, tuple):
        return (
            tuple(s for c in native.candidate.classes if c.design is design for s in c.samples)
            if native.candidate is not None
            else ()
        ), ()
    source = assessment.construction.source
    if not isinstance(source, StudySource):
        raise TypeError("recomputed study results require a typed StudySource")
    samples = []
    checks = []
    for index, (study, result) in enumerate(zip(source.studies, native, strict=True)):
        if not isinstance(result, NaturalStudyResult):
            raise TypeError("typed recomputed study result required")
        if study.design is not design:
            continue
        matches = []
        if result.checks.finding is CheckFinding.PASS and result.supported_components and study.components:
            first = study.components[0].study
            value = max((flow for _, flow in result.supported_components), key=lambda flow: flow.value)
            if all(c.study.scope == first.scope for c in study.components):
                matches = [
                    c.result.base
                    for c in assessment.compositions
                    if c.design is design
                    and c.result.base.interval == first.scope.period
                    and c.result.base.location == first.scope.location
                    and c.result.base.provenance == first.evidence.provenance
                    and c.result.base.value == value
                ]
        if len(matches) == 1:
            samples.append(matches[0])
        else:
            checks.append(
                Check(
                    f"study_source_binding:{index}",
                    CheckFinding.UNKNOWN,
                    ("actual study-supported pre-quality sample is not uniquely bound",),
                )
            )
    return tuple(sorted(samples, key=lambda sample: sample.interval.start)), tuple(checks)


def _supported_source(source: tuple[FlowSample, ...], support: tuple[FlowSample, ...]) -> tuple[FlowSample, ...]:
    """Attach supplied bounds only after exact native sample binding."""
    native = {sample.interval: sample for sample in source}
    supplied = {}
    for sample in support:
        if sample.interval not in native or sample.interval in supplied:
            raise ValueError("candidate support requires unique actual native source intervals")
        actual = native[sample.interval]
        if replace(sample, uncertainty=actual.uncertainty) != actual:
            raise ValueError("candidate support must equal the native source except for uncertainty")
        supplied[sample.interval] = sample
    return tuple(supplied.get(sample.interval, sample) for sample in source)


def recompute_provisional_duration(
    members: tuple[RequirementMember, ...],
    constructions: tuple[ConstructionAssessment, ...],
    duration_tests: tuple[DurationTest, ...],
    expected_duration_tests: tuple[tuple[str, str], ...],
    *,
    provisional_duration_tests: tuple[DurationTest, ...] = (),
) -> tuple[ProvisionalDurationAssessment, ...]:
    """Retain each configured member/class diagnostic, including missing inputs.

    Construction assessments must be recomputed by the finalizer first. A supplied
    provisional DurationTest supplies a separately accepted local threshold and
    pre-quality context, not a prior result. Its duration rule, return period,
    estimator, profile and purpose must preserve the configured test policy.
    """
    by_member = {m.identifier: m for m in members}
    if len(by_member) != len(members):
        raise ValueError("duplicate retained member")
    if len(set(expected_duration_tests)) != len(expected_duration_tests):
        raise ValueError("duplicate configured duration test")
    if any(m not in by_member or not name.strip() for m, name in expected_duration_tests):
        raise ValueError("duration manifest must identify retained members")
    expected = {(m, name, d) for m, name in expected_duration_tests for d in DesignClass}
    sources = {}
    for assessment in constructions:
        name = assessment.member.identifier
        if name not in by_member or name in sources or assessment.member != by_member[name]:
            raise ValueError("construction must bind an exact unique retained member")
        sources[name] = assessment
    tests = {}
    contexts = {}
    for supplied, destination in ((duration_tests, tests), (provisional_duration_tests, contexts)):
        for test in supplied:
            key = test.member, test.identifier, test.design
            if key not in expected or key in destination:
                raise ValueError("undeclared or duplicate provisional duration test")
            destination[key] = test
    for key, context in contexts.items():
        if key not in tests:
            raise ValueError("pre-quality context requires configured duration test input")
        local = context.threshold
        final = tests[key].threshold
        if (
            local.reference.rule,
            local.return_period,
            local.estimator,
            local.profile_version,
            context.purpose,
        ) != (
            final.reference.rule,
            final.return_period,
            final.estimator,
            final.profile_version,
            tests[key].purpose,
        ):
            raise ValueError("pre-quality context cannot change configured threshold policy or purpose")
    records = []
    for member, identifier, design in sorted(expected, key=lambda k: (k[0], k[1], k[2].value)):
        family = by_member[member].candidate
        if not isinstance(family, RequirementFamily):
            raise TypeError("provisional regime diagnostics require RequirementFamily")
        assessment = sources.get(member)
        source, source_checks = _actual_source(assessment, design)
        test = tests.get((member, identifier, design))
        context = contexts.get((member, identifier, design))
        missing = list(source_checks)
        if not source:
            missing.append(Check("source", CheckFinding.UNKNOWN, ("actual pre-quality source missing",)))
        if test is None:
            missing.append(Check("test", CheckFinding.UNKNOWN, ("configured duration input missing",)))
        result = None
        if source and test is not None:
            # A local reference is a separate scientific product. Never borrow
            # acceptance for the mapped/final location's threshold.
            local_test = context if context is not None else test
            candidate = _supported_source(source, context.candidate_support) if context is not None else source
            relation = context.reference_relation if context is not None else None
            identity_changed = any(
                getattr(source[0].provenance, f) != getattr(local_test.threshold.reference.provenance, f)
                for f in ("scenario", "reference_member", "reference_kind")
            )
            if any(sample.location != local_test.threshold.reference.location for sample in source):
                missing.append(
                    Check(
                        "reference_location",
                        CheckFinding.UNKNOWN,
                        (
                            "pre-quality source location differs from the configured duration reference; "
                            "a provenance relation does not authorize spatial mapping",
                        ),
                    )
                )
            elif context is not None and any(
                getattr(sample.provenance, field) != getattr(local_test.threshold.reference.provenance, field)
                for sample in source
                for field in ("reference_member", "reference_kind")
            ):
                missing.append(
                    Check(
                        "reference_meaning",
                        CheckFinding.UNKNOWN,
                        ("local duration reference must retain the actual pre-quality member and reference meaning",),
                    )
                )
            elif identity_changed and relation is None:
                missing.append(
                    Check(
                        "reference_relation", CheckFinding.UNKNOWN, ("pre-quality source/reference relation missing",)
                    )
                )
            else:
                predecessors = context.predecessors if context is not None else ()
                if any(s.interval.end > family.basis.period.start for s in predecessors):
                    raise ValueError("pre-quality predecessors cannot replace source days")
                result = assess_low_flow(
                    (*predecessors, *candidate),
                    family.basis.period,
                    local_test.threshold,
                    stage=AssessmentStage.PROVISIONAL,
                    candidate_basis=f"pre-quality:{member}:{identifier}:{design.value}",
                    provenance=source[0].provenance,
                    predecessor_basis=context.predecessor_basis if context is not None else None,
                    scientific_assessment=local_test.scientific_assessment,
                    uncertainty_support=context.uncertainty_support if context is not None else None,
                    purpose=test.purpose,
                    reference_relation=relation,
                )
        checks = CheckSummary((*missing, *(result.checks.checks if result is not None else ())))
        records.append(ProvisionalDurationAssessment(member, identifier, design, source, result, checks))
    return tuple(records)
