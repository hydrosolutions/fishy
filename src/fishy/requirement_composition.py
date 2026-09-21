"""compose_requirement : FlowSample × Provenance × QualityComponent? × ControlMapping? × EvidenceFindings? → IntervalComposition.

Shared lower bounds use their maximum. Lateral water uses the supported carrier
mapping, never a sum of arbitrary requirements. Original components remain visible.
"""

from dataclasses import dataclass, replace

from fishy.evidence import Check, CheckFinding, CheckSummary, EvidenceFindings, Provenance
from fishy.flows import Coverage, FlowSample, Presence
from fishy.quality_activation import ComponentStatus, QualityComponent
from fishy.receptor_delivery import ControlEquivalent, ControlMapping, control_equivalent


@dataclass(frozen=True)
class IntervalComposition:
    base: FlowSample
    quality: QualityComponent | None
    mapping: ControlEquivalent | None
    candidate: FlowSample | None
    checks: CheckSummary


def compose_requirement(
    base: FlowSample,
    provenance: Provenance,
    *,
    quality: QualityComponent | None = None,
    mapping: ControlMapping | None = None,
    mapping_evidence: EvidenceFindings | None = None,
) -> IntervalComposition:
    """Compose one supported interval; this operation neither issues nor derives a floor.

    A missing mapping is represented by a supplied mapping with missing evidence.
    No mapping means the caller declares there is no spatial addition in this step.
    Final checks on any later uplift or external selection remain separate.
    """
    if not isinstance(base, FlowSample) or not isinstance(provenance, Provenance):
        raise TypeError("composition requires FlowSample and Provenance")
    for field in ("scenario", "reference_member", "reference_kind", "configuration_version"):
        if getattr(base.provenance, field) != getattr(provenance, field):
            raise ValueError("composition cannot change scenario/reference/configuration identity")
    if mapping_evidence is not None and mapping is None:
        raise ValueError("mapping evidence supplied without a mapping")
    checks = []
    value = base.value
    available = base.presence is Presence.PRESENT and base.coverage is Coverage.COMPLETE and value is not None
    checks.append(
        Check(
            "ecological_base",
            CheckFinding.PASS if available else CheckFinding.UNKNOWN,
            base.reasons if not available else (),
        )
    )
    if quality is not None:
        boundary = quality.quality.boundary
        if (boundary.location, boundary.interval) != (base.location, base.interval) or quality.base != base.value:
            raise ValueError("quality component must use the exact ecological operand, location and interval")
        for field in ("scenario", "reference_member", "reference_kind", "configuration_version"):
            if getattr(boundary.provenance, field) != getattr(base.provenance, field):
                raise ValueError("quality component identity differs from ecological base")
        finding = (
            CheckFinding.FAIL
            if quality.status is ComponentStatus.INFEASIBLE
            else CheckFinding.UNKNOWN
            if quality.status is ComponentStatus.UNSIZED
            else CheckFinding.PASS
        )
        checks.append(Check("quality_component", finding, quality.reasons))
        value = quality.combined
    equivalent = None
    location = base.location
    if mapping is not None:
        if (mapping.continuing_location, mapping.context.period, mapping.continuing) != (
            base.location,
            base.interval,
            value,
        ):
            raise ValueError("control mapping must carry the exact quality-adjusted continuing flow")
        for field in ("scenario", "reference_member", "reference_kind", "configuration_version"):
            if getattr(mapping.context.provenance, field) != getattr(base.provenance, field):
                raise ValueError("control mapping identity differs from continuing flow")
        equivalent = control_equivalent(mapping, mapping_evidence)
        checks.append(
            Check(
                "control_equivalence",
                CheckFinding.PASS if equivalent.upstream is not None else CheckFinding.UNKNOWN,
                equivalent.reasons,
            )
        )
        value = equivalent.upstream
        location = mapping.control
    candidate = None
    if value is not None and available:
        candidate = replace(
            base,
            location=location,
            value=value,
            provenance=provenance,
            uncertainty=None,
            components=(base,),
            reasons=(*base.reasons, "uncapped composition; final checks required; derived uncertainty not supplied"),
        )
    return IntervalComposition(base, quality, equivalent, candidate, CheckSummary(tuple(checks)))
