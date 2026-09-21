"""issue_obligation : Requirement × Deliverability × IssuanceProvenance → IssuedObligation.

Proposed Uzbek arithmetic only. Route/family eligibility and competent authority are
not established here. A Floor is not a Requirement. Existing duties are untouched.
"""

from dataclasses import dataclass

from fishy.duties import Deliverability, Obligation, Requirement
from fishy.evidence import Provenance
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, interval_use
from fishy.quantities import Flow


@dataclass(frozen=True)
class IssuedObligation:
    requirement: Requirement
    deliverability: Deliverability
    obligation: Obligation
    ecological_deficit: Flow


def issue_obligation(
    requirement: Requirement, deliverability: Deliverability, *, version: str, provenance: Provenance
) -> IssuedObligation:
    """Freeze min(requirement, deliverability) without asserting complete regime eligibility.

    Missing/unsupported named operands are refused, not replaced with a floor or zero.
    Caller retains prior returned records when issuing a new identified version.
    """
    if type(requirement) is not Requirement or type(deliverability) is not Deliverability:
        raise TypeError("issuance needs Requirement and Deliverability, never Floor or Delivery")
    if not isinstance(provenance, Provenance):
        raise TypeError("issuance requires versioned Provenance")
    target, capacity = requirement.sample, deliverability.sample
    if target.location != capacity.location or target.interval != capacity.interval:
        raise ValueError("requirement and deliverability must share exact location and interval")
    if target.provenance.scenario != capacity.provenance.scenario or provenance.scenario != target.provenance.scenario:
        raise ValueError("issuance cannot mix scenarios")
    for sample in (target, capacity):
        if (
            sample.presence is not Presence.PRESENT
            or sample.coverage is not Coverage.COMPLETE
            or interval_use(sample) is not IntervalUse.ELIGIBLE
            or sample.value is None
        ):
            raise ValueError("issuance requires complete supported named operands")
    assert target.value is not None and capacity.value is not None
    value = Flow(min(target.value.value, capacity.value.value))
    obligation = Obligation(
        FlowSample(
            target.location, target.interval, value, Presence.PRESENT, provenance, components=(target, capacity)
        ),
        version,
    )
    return IssuedObligation(requirement, deliverability, obligation, Flow(target.value.value - value.value))
