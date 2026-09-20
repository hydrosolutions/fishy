"""ReportingIdentity × Provenance × Interval → PreparedTopology (synthetic supplied context).

Prepared tributary contributions are not inferred from repeated reach requirements.
"""

from fractions import Fraction

from fishy.basin import (
    ContextEvidence,
    ContextKind,
    PreparedTopology,
    River,
    RiverConnection,
    RiverType,
    SectionContext,
    TributaryAccount,
    tributary_sum,
)
from fishy.design_conditions import DesignClass
from fishy.evidence import (
    Computability,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    Provenance,
    ScientificAdequacy,
)
from fishy.quantities import Volume
from fishy.seasonal_allocation import ReportingIdentity
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def basin_evidence(location: Location, period: Interval, provenance: Provenance, product: str) -> EvidenceFindings:
    return EvidenceFindings(
        EvidenceScope(product, location.reach.identifier, provenance.reference_member, period, "basin assessment"),
        provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("Synthetic prepared context, not a calibrated basin",),
    )


def prepared_basin(identity: ReportingIdentity, period: Interval, provenance: Provenance) -> PreparedTopology:
    left, right = River("left-tributary", "v1", 1), River("right-tributary", "v1", 1)

    def section_location(name: str) -> Location:
        return Location(
            Reach(name, "v1", WaterBody(name, "v1")), CalculationSection(name, "v1"), identity.location.mapping_version
        )

    upstream = section_location("main-upstream")
    locations = (identity.location, upstream, section_location("left"), section_location("right"))
    rivers = (identity.river, identity.river, left, right)
    sections = tuple(
        SectionContext(
            river,
            location,
            downstream,
            river_type,
            tuple(
                ContextEvidence(kind, basin_evidence(location, period, provenance, kind.value)) for kind in ContextKind
            ),
        )
        for river, location, downstream, river_type in zip(
            rivers,
            locations,
            (None, identity.location, upstream, upstream),
            (RiverType.PLAIN, RiverType.MOUNTAIN, RiverType.MOUNTAIN, RiverType.PLAIN),
            strict=True,
        )
    )
    return PreparedTopology(
        identity.basin,
        "topology-v1",
        (identity.river, left, right),
        (RiverConnection(left, identity.river), RiverConnection(right, identity.river)),
        sections,
    )


def supplied_tributary_account(
    topology: PreparedTopology,
    identity: ReportingIdentity,
    period: Interval,
    provenance: Provenance,
    total: Volume,
    design: DesignClass,
):
    # External illustrative study supplies disjoint parcels and shares. This is NOT
    # an algorithm for splitting a main-river requirement into obligations.
    product = f"design{design.value}/corrected-tributary-volume"
    contributions = tuple(
        TributaryAccount(
            section.river,
            section.location,
            Volume(total.value * share),
            (section.river.identifier + "-water-parcel",),
            basin_evidence(section.location, period, provenance, product),
        )
        for section, share in zip(topology.sections[2:], (Fraction(3, 5), Fraction(2, 5)), strict=True)
    )
    evidence = basin_evidence(identity.location, period, provenance, product)
    return tributary_sum(topology, identity.river, identity.location, evidence.scope, contributions, evidence)
