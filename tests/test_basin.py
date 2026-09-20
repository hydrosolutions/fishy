"""Prepared basin connectivity and attributed non-consumptive accounting."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from fishy.basin import (
    Basin,
    ContextEvidence,
    ContextKind,
    DonorRelation,
    PreparedTopology,
    River,
    RiverConnection,
    RiverType,
    SectionContext,
    TributaryAccount,
    mouth_to_source,
    receiving_parent,
    tributary_sum,
    verify_donor_relation,
)
from fishy.evidence import (
    CheckFinding,
    Completeness,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ScientificAdequacy,
    UseRestriction,
)
from fishy.quantities import Volume
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def location(name):
    return Location(Reach(name, "r1", WaterBody("body-" + name, "w1")), CalculationSection(name, "s1"), "map1")


def evidence(loc, product="design25/tributary-accounting"):
    period = Interval(datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC))
    return EvidenceFindings(
        EvidenceScope(product, loc.reach.identifier, "natural-A", period, "scenario calculation"),
        Provenance(
            "prepared study",
            "scenario-A",
            "natural-A",
            "v1",
            "data1",
            "config1",
            ProductionMethod.ILLUSTRATIVE,
            CorrectionState.ORIGINAL,
        ),
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        (),
    )


@pytest.fixture
def basin():
    main, left, right, nested = (
        River("main", "v1", 0),
        River("left", "v1", 1),
        River("right", "v1", 1),
        River("nested", "v1", 2),
    )
    mouth, upstream, a, a_up, b, c = map(location, ("mouth", "upstream", "left", "left-up", "right", "nested"))
    sections = (
        SectionContext(nested, c, a),
        SectionContext(left, a_up, a, RiverType.MOUNTAIN),
        SectionContext(right, b, mouth),
        SectionContext(main, upstream, mouth, RiverType.MOUNTAIN),
        SectionContext(left, a, upstream, RiverType.PLAIN),
        SectionContext(main, mouth, None, RiverType.PLAIN),
    )
    return PreparedTopology(
        Basin("basin", "b1"),
        "topology1",
        (main, left, right, nested),
        (RiverConnection(left, main), RiverConnection(right, main), RiverConnection(nested, left)),
        sections,
    )


def accounts(basin):
    left = next(s for s in basin.sections if s.location.section.identifier == "left")
    right = next(s for s in basin.sections if s.location.section.identifier == "right")
    return (
        TributaryAccount(left.river, left.location, Volume(30), ("left-catchment",), evidence(left.location)),
        TributaryAccount(right.river, right.location, Volume(20), ("right-catchment",), evidence(right.location)),
    )


def calculate(basin, items, findings=None):
    mouth = next(s for s in basin.sections if s.downstream is None)
    support = evidence(mouth.location)
    return tributary_sum(
        basin, mouth.river, mouth.location, support.scope, items, support if findings is None else findings
    )


def test_mouth_to_source_sections_and_receiving_rivers_before_tributaries(basin):
    ordered = mouth_to_source(basin)
    assert [s.location.section.identifier for s in ordered] == [
        "mouth",
        "upstream",
        "right",
        "left",
        "left-up",
        "nested",
    ]
    assert ordered[0].river_type is RiverType.PLAIN
    assert ordered[1].river_type is RiverType.MOUNTAIN
    assert ordered[0].location.reach.water_body != ordered[0].river
    assert basin.basin == Basin("basin", "b1")


def test_receiving_parent_not_higher_order_child_or_unconnected_gauge(basin):
    main, left, right, nested = basin.rivers
    assert receiving_parent(basin, left) == main
    assert receiving_parent(basin, nested) == left
    assert receiving_parent(basin, main) is None
    loc = next(s.location for s in basin.sections if s.river == left)
    finding = evidence(loc, "donor transfer")
    good = DonorRelation(left, main, finding)
    assert verify_donor_relation(basin, left, good, finding.scope).finding is CheckFinding.PASS
    for wrong in (nested, right):
        assert (
            verify_donor_relation(basin, left, replace(good, donor=wrong), finding.scope).finding is CheckFinding.FAIL
        )
    assert good.evidence.official_admissibility is OfficialAdmissibility.PENDING


@pytest.mark.parametrize("missing", ["relation", "topology", "scope", "acceptance", "restriction"])
def test_donor_missing_or_unsupported_evidence_remains_further_study(basin, missing):
    main, left, _, _ = basin.rivers
    loc = next(s.location for s in basin.sections if s.river == left)
    findings = evidence(loc, "donor transfer")
    scope = findings.scope
    if missing == "scope":
        scope = replace(scope, product="other operation")
    if missing == "acceptance":
        findings = replace(findings, scientific_adequacy=ScientificAdequacy.UNKNOWN)
    if missing == "restriction":
        findings = replace(findings, restrictions=(UseRestriction("unsuitable", (scope.intended_use,)),))
    result = verify_donor_relation(
        None if missing == "topology" else basin,
        left,
        None if missing == "relation" else DonorRelation(left, main, findings),
        scope,
    )
    assert result.finding is (CheckFinding.FAIL if missing == "restriction" else CheckFinding.UNKNOWN)


def test_source_order_labels_do_not_create_or_override_connectivity(basin):
    # A prepared anomalous source label cannot become a different donor choice.
    main, left, right, nested = basin.rivers
    changed = replace(left, order=7)
    topology = replace(
        basin,
        rivers=(main, changed, right, nested),
        connections=tuple(
            RiverConnection(
                changed if e.tributary == left else e.tributary, changed if e.receiving == left else e.receiving
            )
            for e in basin.connections
        ),
        sections=tuple(replace(s, river=changed) if s.river == left else s for s in basin.sections),
    )
    assert receiving_parent(topology, changed) == main
    assert receiving_parent(topology, nested) == changed


def test_supported_paragraph5_sum_preserves_source_and_exact_attribution(basin):
    items = accounts(basin)
    result = calculate(basin, items)
    assert result.volume == Volume(50)
    assert result.accounts == items
    assert result.checks.finding is CheckFinding.PASS
    assert result.checks.completeness is Completeness.COMPLETE
    assert result.source == "Order 179-НҚ (2025), methodology paragraph 5"
    assert result.topology == basin
    assert result.evidence.official_admissibility is OfficialAdmissibility.PENDING
    # Repeated main-river reaches did not enter the sum; no routing or duty exists.
    assert len([s for s in basin.sections if s.river.order == 0]) == 2


def test_zero_is_supported_not_missing(basin):
    result = calculate(basin, tuple(replace(a, volume=Volume(0)) for a in accounts(basin)))
    assert result.volume == Volume(0)
    assert result.checks.finding is CheckFinding.PASS


@pytest.mark.parametrize("missing", ["topology", "accounting", "tributary", "volume", "evidence", "parcels"])
def test_missing_accounting_evidence_never_becomes_a_sum_or_maximum(basin, missing):
    mouth = next(s for s in basin.sections if s.downstream is None)
    support = evidence(mouth.location)
    items = accounts(basin)
    if missing == "tributary":
        items = items[:1]
    if missing == "volume":
        items = (replace(items[0], volume=None), items[1])
    if missing == "evidence":
        items = (replace(items[0], evidence=None), items[1])
    if missing == "parcels":
        items = (replace(items[0], water_accounts=()), items[1])
    result = tributary_sum(
        None if missing == "topology" else basin,
        mouth.river,
        mouth.location,
        support.scope,
        items,
        None if missing == "accounting" else support,
    )
    assert result.volume is None
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.checks.completeness is Completeness.INCOMPLETE


def test_known_failure_survives_other_missing_account(basin):
    items = accounts(basin)
    unsupported = replace(items[0].evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
    result = calculate(basin, (replace(items[0], evidence=unsupported), replace(items[1], volume=None)))
    assert result.volume is None
    assert result.checks.finding is CheckFinding.FAIL
    assert result.checks.completeness is Completeness.INCOMPLETE


@pytest.mark.parametrize(
    "bad", ["duplicate-river", "nested", "shared-parcel", "wrong-location", "scenario", "period", "product"]
)
def test_double_counting_and_mixed_support_cannot_produce_result(basin, bad):
    items = accounts(basin)
    if bad == "duplicate-river":
        second = next(s for s in basin.sections if s.location.section.identifier == "left-up")
        items = (*items, replace(items[0], location=second.location, water_accounts=("different-label",)))
    if bad == "nested":
        nested = next(s for s in basin.sections if s.river.identifier == "nested")
        items = (
            *items,
            TributaryAccount(nested.river, nested.location, Volume(10), ("nested",), evidence(nested.location)),
        )
    if bad == "shared-parcel":
        items = (items[0], replace(items[1], water_accounts=items[0].water_accounts))
    if bad == "wrong-location":
        items = (replace(items[0], location=items[1].location), items[1])
    if bad == "scenario":
        assert items[0].evidence is not None
        altered = replace(items[0].evidence, provenance=replace(items[0].evidence.provenance, scenario="other"))
        items = (replace(items[0], evidence=altered), items[1])
    if bad in ("period", "product"):
        assert items[0].evidence is not None
        scope = items[0].evidence.scope
        scope = (
            replace(scope, period=Interval(datetime(2023, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)))
            if bad == "period"
            else replace(scope, product="design95/tributary-accounting")
        )
        result = calculate(basin, (replace(items[0], evidence=replace(items[0].evidence, scope=scope)), items[1]))
        assert result.volume is None
        assert result.checks.finding is CheckFinding.UNKNOWN
    else:
        with pytest.raises(ValueError):
            calculate(basin, items)


@pytest.mark.parametrize(
    "bad",
    [
        "cycle",
        "duplicate-section",
        "mixed-revision",
        "missing-edge",
        "missing-section",
        "two-outlets",
        "wrong-downstream",
    ],
)
def test_topology_invariants(basin, bad):
    with pytest.raises(ValueError):
        if bad == "cycle":
            replace(basin, connections=(*basin.connections, RiverConnection(basin.rivers[0], basin.rivers[1])))
        elif bad == "duplicate-section":
            replace(basin, sections=(*basin.sections, basin.sections[0]))
        elif bad == "mixed-revision":
            replace(basin, rivers=(*basin.rivers, replace(basin.rivers[0], version="new")))
        elif bad == "missing-edge":
            replace(basin, connections=basin.connections[:-1])
        elif bad == "missing-section":
            replace(basin, sections=basin.sections[1:])
        elif bad == "two-outlets":
            replace(basin, sections=(replace(basin.sections[0], downstream=None), *basin.sections[1:]))
        else:
            replace(basin, sections=(replace(basin.sections[0], downstream=location("unknown")), *basin.sections[1:]))


def test_context_evidence_preserves_every_supplied_kind_and_scope(basin):
    section = basin.sections[0]
    supplied = tuple(ContextEvidence(kind, evidence(section.location, kind.value)) for kind in ContextKind)
    revised = replace(section, evidence=supplied)
    assert revised.evidence == supplied
    assert not section.evidence
    assert revised.location == section.location
    with pytest.raises(ValueError, match="different reach"):
        replace(section, evidence=(ContextEvidence(ContextKind.CLIMATE, evidence(location("elsewhere"))),))


def test_revision_identity_cannot_select_old_donor_or_rewrite_result(basin):
    result = calculate(basin, accounts(basin))
    with pytest.raises(ValueError, match="absent"):
        receiving_parent(basin, replace(basin.rivers[1], version="next"))
    next_basin = replace(basin, basin=replace(basin.basin, version="b2"), version="topology2")
    assert result.topology.version == "topology1"
    assert next_basin.basin.version == "b2"


@pytest.mark.parametrize("order", [-1, 1.5, True])
def test_invalid_river_order(order):
    with pytest.raises(ValueError):
        River("river", "v1", order)


def test_excluded_warmup_cannot_support_accounting(basin):
    items = accounts(basin)
    finding = items[0].evidence
    finding = replace(finding, provenance=replace(finding.provenance, excluded_warmup=(finding.scope.period,)))
    result = calculate(basin, (replace(items[0], evidence=finding), items[1]))
    assert result.volume is None
    assert result.checks.finding is CheckFinding.FAIL


def test_excluded_warmup_cannot_accept_a_donor(basin):
    main, left, _, _ = basin.rivers
    loc = next(s.location for s in basin.sections if s.river == left)
    finding = evidence(loc, "donor transfer")
    finding = replace(finding, provenance=replace(finding.provenance, excluded_warmup=(finding.scope.period,)))
    assert (
        verify_donor_relation(basin, left, DonorRelation(left, main, finding), finding.scope).finding
        is CheckFinding.FAIL
    )


def test_provenance_member_must_match_accounting_scope(basin):
    mouth = next(s for s in basin.sections if s.downstream is None)
    finding = evidence(mouth.location)
    finding = replace(finding, provenance=replace(finding.provenance, reference_member="other-member"))
    # Keep all provenances mutually equal: the scope/provenance mismatch must itself fail.
    items = tuple(replace(a, evidence=replace(a.evidence, provenance=finding.provenance)) for a in accounts(basin))
    result = calculate(basin, items, finding)
    assert result.volume is None
    assert result.checks.finding is CheckFinding.FAIL


def test_disconnected_river_cycle_is_rejected(basin):
    main, left, right, nested = basin.rivers
    with pytest.raises(ValueError, match="Cyclic river"):
        replace(
            basin,
            connections=(RiverConnection(left, nested), RiverConnection(nested, left), RiverConnection(right, main)),
        )


def test_same_river_section_cycle_is_rejected(basin):
    mouth = next(s for s in basin.sections if s.downstream is None)
    upstream = next(s for s in basin.sections if s.location.section.identifier == "upstream")
    extra_location = location("extra-upstream")
    cycle = replace(upstream, downstream=extra_location)
    extra = SectionContext(upstream.river, extra_location, upstream.location)
    with pytest.raises(ValueError, match="Cyclic section"):
        replace(basin, sections=tuple(cycle if s == upstream else s for s in basin.sections) + (extra,))
    assert mouth.downstream is None


def test_empty_tributary_set_cannot_manufacture_zero_pass():
    main = River("main", "v1", 0)
    loc = location("mouth")
    topology = PreparedTopology(Basin("basin", "v1"), "v1", (main,), (), (SectionContext(main, loc, None),))
    finding = evidence(loc)
    result = tributary_sum(topology, main, loc, finding.scope, (), finding)
    assert result.volume is None
    assert result.checks.finding is CheckFinding.UNKNOWN


def test_mapping_revision_and_undeclared_river_fail_loud(basin):
    with pytest.raises(ValueError, match="mapping versions"):
        replace(
            basin,
            sections=(
                replace(basin.sections[0], location=replace(basin.sections[0].location, mapping_version="new")),
                *basin.sections[1:],
            ),
        )
    with pytest.raises(ValueError, match="undeclared river revision"):
        replace(basin, connections=(*basin.connections, RiverConnection(River("unknown", "v1", 4), basin.rivers[0])))
