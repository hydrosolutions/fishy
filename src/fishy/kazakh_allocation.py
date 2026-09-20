"""initial_allocation : NaturalAnnualReference × DesignClass → InitialAllocation (pure).

Order 179-НҚ (2025), paragraphs 15–22 and Appendix 2. Imported statistics
are not reconstructed here. Interpretation choices do not authenticate law.
"""

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from fractions import Fraction

from fishy.basin import DonorRelation, PreparedTopology, River, verify_donor_relation
from fishy.design_conditions import DesignClass
from fishy.evidence import (
    CheckFinding,
    EvidenceFindings,
    EvidenceScope,
    Provenance,
    ReferenceKind,
    permitted_use,
    warmup_restrictions,
)
from fishy.quantities import Volume, finite_number
from fishy.spatial import Location
from fishy.time import Interval


class NaturalExceedance(IntEnum):
    P25 = 25
    P50 = 50
    P75 = 75
    P90 = 90
    P95 = 95
    P97 = 97


def shifted_class(design: DesignClass) -> NaturalExceedance:
    if not isinstance(design, DesignClass):
        raise TypeError("design requires DesignClass")
    return {
        DesignClass.WET: NaturalExceedance.P50,
        DesignClass.MEDIUM: NaturalExceedance.P75,
        DesignClass.MODERATELY_DRY: NaturalExceedance.P90,
        DesignClass.DRY: NaturalExceedance.P97,
    }[design]


class ObservationRoute(StrEnum):
    ADEQUATE = "adequate"
    INSUFFICIENT = "insufficient"
    ABSENT = "absent"


class AllocationRoute(StrEnum):
    PROBABILITY_SHIFT = "probability_shift"
    MEDIAN_NORMALISED = "median_normalised_initial_allocation"
    RECEIVING_PARENT = "receiving_parent_coefficient"


class AllocationStatus(StrEnum):
    SUPPORTED = "supported_initial_allocation"
    UNRESOLVED = "unresolved"
    FURTHER_STUDY = "further_study"


def evidence_reasons(
    evidence: EvidenceFindings,
    location: Location,
    period: Interval,
    provenance: Provenance,
    product: str,
    intended_use: str,
) -> tuple[str, ...]:
    """Check exact requested scope; retain official admissibility separately."""
    scope = EvidenceScope(product, location.reach.identifier, provenance.reference_member, period, intended_use)
    result = permitted_use(evidence, scope)
    reasons = () if result.finding is CheckFinding.PASS else result.reasons
    if evidence.provenance != provenance:
        reasons += ("evidence and product provenance differ",)
    return reasons + warmup_restrictions(provenance, period)


@dataclass(frozen=True)
class AnnualQuantile:
    exceedance: NaturalExceedance
    volume: Volume

    def __post_init__(self) -> None:
        if not isinstance(self.exceedance, NaturalExceedance) or not isinstance(self.volume, Volume):
            raise TypeError("annual quantile requires exceedance and Volume")


@dataclass(frozen=True)
class NaturalAnnualReference:
    location: Location
    period: Interval
    quantiles: tuple[AnnualQuantile, ...]
    observations: ObservationRoute
    provenance: Provenance
    evidence: EvidenceFindings
    reconstruction: EvidenceFindings | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location) or not isinstance(self.period, Interval):
            raise TypeError("reference needs location and observation period")
        if not isinstance(self.observations, ObservationRoute):
            raise TypeError("observation route requires enum")
        if not isinstance(self.provenance, Provenance) or not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("reference requires provenance and evidence")
        if not isinstance(self.quantiles, tuple) or any(not isinstance(q, AnnualQuantile) for q in self.quantiles):
            raise TypeError("quantiles require immutable AnnualQuantile records")
        if len({q.exceedance for q in self.quantiles}) != len(self.quantiles):
            raise ValueError("duplicate annual exceedance")
        ordered = sorted(self.quantiles, key=lambda q: q.exceedance)
        if any(a.volume.value < b.volume.value for a, b in zip(ordered, ordered[1:], strict=False)):
            raise ValueError("annual volume must not increase with exceedance")
        if self.provenance.reference_kind not in (
            ReferenceKind.PRESENT_CLIMATE_NATURAL,
            ReferenceKind.NATURALISED_HISTORICAL,
        ):
            raise ValueError("conditionally-natural reference required")
        if self.reconstruction is not None and not isinstance(self.reconstruction, EvidenceFindings):
            raise TypeError("reconstruction requires evidence findings")

    def volume(self, probability: NaturalExceedance) -> Volume | None:
        return next((q.volume for q in self.quantiles if q.exceedance is probability), None)


def reference_reasons(reference: NaturalAnnualReference) -> tuple[str, ...]:
    reasons = evidence_reasons(
        reference.evidence,
        reference.location,
        reference.period,
        reference.provenance,
        "natural_annual_reference",
        "initial_allocation",
    )
    if reference.observations is ObservationRoute.INSUFFICIENT:
        if reference.reconstruction is None:
            reasons += ("annual/monthly reconstruction and naturalisation evidence missing",)
        else:
            reasons += evidence_reasons(
                reference.reconstruction,
                reference.location,
                reference.period,
                reference.provenance,
                "annual_monthly_reconstruction",
                "initial_allocation",
            )
    return reasons


@dataclass(frozen=True)
class InitialAllocation:
    design: DesignClass
    volume: Volume | None
    coefficient: Fraction | None
    route: AllocationRoute | None
    status: AllocationStatus
    reference: NaturalAnnualReference
    reasons: tuple[str, ...]
    supporting_evidence: tuple[EvidenceFindings, ...] = ()
    source: str = "Order 179-НҚ, 23 July 2025, paragraphs 18–22; Appendix 2"

    def __post_init__(self) -> None:
        if not isinstance(self.design, DesignClass) or not isinstance(self.reference, NaturalAnnualReference):
            raise TypeError("initial allocation requires typed design and reference")
        if not isinstance(self.status, AllocationStatus) or (
            self.route is not None and not isinstance(self.route, AllocationRoute)
        ):
            raise TypeError("initial allocation requires typed status and route")
        if self.status is AllocationStatus.SUPPORTED:
            if not isinstance(self.volume, Volume) or self.route is None or self.reasons:
                raise ValueError("supported initial allocation requires volume, route and no unresolved reasons")
        elif self.volume is not None or not self.reasons:
            raise ValueError("unresolved allocation requires reasons and no numerical volume")
        if self.coefficient is not None:
            value = finite_number(self.coefficient)
            if value < 0 or self.route is AllocationRoute.PROBABILITY_SHIFT:
                raise ValueError("invalid initial coefficient")
            object.__setattr__(self, "coefficient", value)
        if not isinstance(self.supporting_evidence, tuple) or any(
            not isinstance(e, EvidenceFindings) for e in self.supporting_evidence
        ):
            raise TypeError("supporting evidence must be immutable findings")


def initial_allocation(
    reference: NaturalAnnualReference, design: DesignClass, route: AllocationRoute | None
) -> InitialAllocation:
    """Shift or reproduce that same initial volume; never reduce it twice."""
    probability = shifted_class(design)
    reasons = reference_reasons(reference)
    if route is not None and not isinstance(route, AllocationRoute):
        raise TypeError("allocation interpretation requires AllocationRoute")
    if reference.observations is ObservationRoute.ABSENT:
        return InitialAllocation(
            design,
            None,
            None,
            route,
            AllocationStatus.FURTHER_STUDY,
            reference,
            (*reasons, "accepted receiving-parent donor and coefficients required"),
        )
    if route is AllocationRoute.RECEIVING_PARENT:
        raise ValueError("receiving-parent coefficients require transfer_allocation")
    if route is None:
        reasons += ("annual allocation route not selected",)
    target = reference.volume(probability)
    if target is None:
        reasons += (f"natural P{probability.value} annual volume missing",)
    coefficient = None
    if route is AllocationRoute.MEDIAN_NORMALISED:
        median = reference.volume(NaturalExceedance.P50)
        if median is None or median.value <= 0:
            reasons += ("median-normalised denominator requires natural W50 > 0; 0/0 unidentified",)
        elif target is not None:
            coefficient = target.value / median.value
            target = Volume(coefficient * median.value)
    return InitialAllocation(
        design,
        None if reasons else target,
        coefficient if not reasons else None,
        route,
        AllocationStatus.UNRESOLVED if reasons else AllocationStatus.SUPPORTED,
        reference,
        reasons,
    )


@dataclass(frozen=True)
class InitialCoefficient:
    design: DesignClass
    value: Fraction
    donor: Location
    evidence: EvidenceFindings

    def __post_init__(self) -> None:
        if not isinstance(self.design, DesignClass) or not isinstance(self.donor, Location):
            raise TypeError("coefficient requires design and donor Location")
        value = finite_number(self.value)
        if value < 0:
            raise ValueError("initial coefficient must be nonnegative")
        object.__setattr__(self, "value", value)
        if not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("coefficient needs supported initial-stage derivation evidence")


class DonorChoice(StrEnum):
    RECEIVING_PARENT = "receiving_parent"


def transfer_allocation(
    reference: NaturalAnnualReference,
    design: DesignClass,
    topology: PreparedTopology | None,
    recipient: River,
    relation: DonorRelation | None,
    coefficient: InitialCoefficient | None,
    choice: DonorChoice | None,
) -> InitialAllocation:
    """Apply a supported initial-stage donor coefficient to the recipient median.

    The relation is scoped to the recipient historical reference and the coefficient
    to the donor's initial allocation. No estimator, nearest gauge or order heuristic.
    """
    shifted_class(design)
    if reference.observations is not ObservationRoute.ABSENT:
        raise ValueError("transfer route belongs to absent observations")
    if choice is not None and not isinstance(choice, DonorChoice):
        raise TypeError("donor interpretation requires DonorChoice")
    reasons = reference_reasons(reference)
    if choice is None:
        reasons += ("receiving-parent interpretation not selected",)
    scope = EvidenceScope(
        "receiving_parent_transfer",
        reference.location.reach.identifier,
        reference.provenance.reference_member,
        reference.period,
        "initial_allocation",
    )
    relation_check = verify_donor_relation(topology, recipient, relation, scope)
    if relation_check.finding is not CheckFinding.PASS:
        reasons += relation_check.reasons
    if topology is not None and not any(
        s.river == recipient and s.location == reference.location for s in topology.sections
    ):
        raise ValueError("recipient reference location absent from topology")
    if relation is not None and relation.evidence.provenance != reference.provenance:
        reasons += ("transfer relation and receiving reference provenance differ",)
    if coefficient is None:
        reasons += ("initial donor coefficient evidence missing; further studies required",)
    else:
        if coefficient.design is not design:
            raise ValueError("donor coefficient design mismatch")
        if (
            topology is not None
            and relation is not None
            and not any(s.river == relation.donor and s.location == coefficient.donor for s in topology.sections)
        ):
            raise ValueError("coefficient donor location differs from receiving parent")
        donor_scope = EvidenceScope(
            f"initial_coefficient_P{design.value}",
            coefficient.donor.reach.identifier,
            coefficient.evidence.provenance.reference_member,
            coefficient.evidence.scope.period,
            "initial_allocation_transfer",
        )
        check = permitted_use(coefficient.evidence, donor_scope)
        if check.finding is not CheckFinding.PASS:
            reasons += check.reasons
        reasons += warmup_restrictions(coefficient.evidence.provenance, donor_scope.period)
    median = reference.volume(NaturalExceedance.P50)
    if median is None:
        reasons += ("recipient natural annual median missing",)
    supporting = tuple(
        e
        for e in (relation.evidence if relation else None, coefficient.evidence if coefficient else None)
        if e is not None
    )
    volume = (
        Volume(median.value * coefficient.value)
        if not reasons and median is not None and coefficient is not None
        else None
    )
    return InitialAllocation(
        design,
        volume,
        coefficient.value if volume is not None and coefficient is not None else None,
        AllocationRoute.RECEIVING_PARENT,
        AllocationStatus.FURTHER_STUDY if reasons else AllocationStatus.SUPPORTED,
        reference,
        reasons,
        supporting,
    )
