"""Synthetic public-source permit witnesses; exact arithmetic, no legal certification."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from fishy.evidence import (
    CheckFinding,
    Completeness,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ScientificAdequacy,
)
from fishy.quantities import Flow, Volume
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.swiss_permits import (
    AbstractionContext,
    AbstractionInventory,
    AbstractionPurpose,
    AbstractionRate,
    AbstractionSource,
    AbstractionTimeBasis,
    AnnualDrinkingAbstraction,
    Article30Reading,
    Article30ReadingSelection,
    CommonUse,
    ConcessionRoute,
    DecisionStatus,
    DownstreamPermanence,
    EnvironmentalReview,
    GrossHydropower,
    PermitDocument,
    PermitDocumentKind,
    PermitEvidence,
    PermitEvidencePurpose,
    PermitProcess,
    PermitRoute,
    PermitScope,
    SignificantEffect,
    assess_drinking_abstraction,
    assess_limited_abstraction,
    assess_permit_process,
    assess_permit_scope,
    permit_evidence_scope,
)
from fishy.time import Interval


@pytest.fixture
def scope():
    location = Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("intake", "1"), "1")
    return PermitScope(
        location,
        Interval(datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC)),
        "synthetic",
        "member",
        "1",
        "1",
    )


def evidence(scope, purpose=PermitEvidencePurpose.ABSTRACTION_ENVELOPE, subject=None):
    if subject is None:
        subject = AbstractionInventory(
            scope,
            (AbstractionRate("0", Flow(700, "l/s")), AbstractionRate("1", Flow(700, "l/s"))),
            AbstractionTimeBasis.INSTANTANEOUS_ENVELOPE,
            None,
        )
    provenance = Provenance(
        "own synthetic study",
        scope.scenario,
        scope.member,
        "test",
        scope.data_version,
        scope.configuration_version,
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
        scope.reference_kind,
    )
    findings = EvidenceFindings(
        permit_evidence_scope(scope, purpose, subject),
        provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("synthetic only",),
    )
    return PermitEvidence(scope, findings)


def inventory(scope, values=(700, 700), time_basis=AbstractionTimeBasis.INSTANTANEOUS_ENVELOPE):
    subject = AbstractionInventory(
        scope, tuple(AbstractionRate(str(i), Flow(v, "l/s")) for i, v in enumerate(values)), time_basis, None
    )
    return replace(subject, evidence=evidence(scope, PermitEvidencePurpose.ABSTRACTION_ENVELOPE, subject))


def selection(scope, reading):
    subject = Article30ReadingSelection(
        reading, DecisionStatus.HYPOTHETICAL, "Act 2025 Art30(b) / FOEN 2000 pp20,23 named scenario", None
    )
    return replace(subject, evidence=evidence(scope, PermitEvidencePurpose.ARTICLE_30_READING, subject))


def accepted_context(subject):
    return replace(
        subject, applicability_evidence=evidence(subject.scope, PermitEvidencePurpose.APPLICABILITY, subject)
    )


def accepted_permanence(subject):
    return replace(subject, evidence=evidence(subject.scope, PermitEvidencePurpose.DOWNSTREAM_PERMANENCE, subject))


def annual_abstraction(scope, source, purpose, volume):
    subject = AnnualDrinkingAbstraction(scope, source, purpose, volume, None)
    return replace(subject, evidence=evidence(scope, PermitEvidencePurpose.ANNUAL_DRINKING_ABSTRACTION, subject))


def test_two_700_intakes_both_readings_and_no_default(scope):
    inputs = inventory(scope)
    result = assess_limited_abstraction(Flow(7000, "l/s"), inputs, None)
    assert result.combined_abstraction == result.combined_limit == Flow(1400, "l/s")
    assert result.aggregate_reading.finding is CheckFinding.FAIL
    assert result.per_abstraction_reading.finding is CheckFinding.PASS
    assert result.eligibility.finding is CheckFinding.UNKNOWN
    for reading, expected in [
        (Article30Reading.AGGREGATE_1000, CheckFinding.FAIL),
        (Article30Reading.PER_ABSTRACTION_1000, CheckFinding.PASS),
    ]:
        choice = selection(scope, reading)
        selected = assess_limited_abstraction(Flow(7000, "l/s"), inputs, choice)
        assert selected.eligibility.finding is expected
        assert selected.selection == choice
        assert selected.selection is not None
        assert selected.selection.evidence is not None
        assert selected.selection.evidence.findings.official_admissibility is OfficialAdmissibility.PENDING
    with pytest.raises(TypeError):
        assess_limited_abstraction(Flow(7000, "l/s"), inputs)  # ty: ignore[missing-argument]


@pytest.mark.parametrize(
    "q,values,expected",
    [
        (5000, (1000,), CheckFinding.PASS),
        (5000, (1000.001,), CheckFinding.FAIL),
        (4999, (1000,), CheckFinding.FAIL),
        (0, (0,), CheckFinding.FAIL),
    ],
)
def test_article_30_b_exact_thresholds(scope, q, values, expected):
    result = assess_limited_abstraction(
        Flow(q, "l/s"), inventory(scope, values), selection(scope, Article30Reading.AGGREGATE_1000)
    )
    assert result.eligibility.finding is expected


@pytest.mark.parametrize("basis", [AbstractionTimeBasis.INTERVAL_MEAN])
def test_daily_mean_is_not_instantaneous_evidence(scope, basis):
    result = assess_limited_abstraction(
        Flow(10000, "l/s"), inventory(scope, time_basis=basis), selection(scope, Article30Reading.PER_ABSTRACTION_1000)
    )
    assert result.eligibility.finding is CheckFinding.UNKNOWN
    assert result.combined_abstraction == Flow(1400, "l/s")


def test_failure_survives_missing_selection_and_inventory_evidence(scope):
    result = assess_limited_abstraction(Flow(100, "l/s"), replace(inventory(scope), evidence=None), None)
    assert result.eligibility.finding is CheckFinding.FAIL
    assert result.eligibility.completeness is Completeness.INCOMPLETE


def test_interpretation_cannot_transfer_across_section_period_or_scenario(scope):
    for other in [
        replace(scope, scenario="other"),
        replace(scope, member="other"),
        replace(scope, location=replace(scope.location, section=CalculationSection("other", "1"))),
        replace(scope, period=Interval(datetime(2023, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC))),
    ]:
        result = assess_limited_abstraction(
            Flow(7000, "l/s"), inventory(scope), selection(other, Article30Reading.PER_ABSTRACTION_1000)
        )
        assert result.eligibility.finding is CheckFinding.UNKNOWN


def test_empty_and_duplicate_abstraction_inventory(scope):
    result = assess_limited_abstraction(
        Flow(1000, "l/s"), inventory(scope, ()), selection(scope, Article30Reading.PER_ABSTRACTION_1000)
    )
    assert result.eligibility.finding is CheckFinding.UNKNOWN
    with pytest.raises(ValueError):
        replace(inventory(scope), abstractions=(AbstractionRate("same", Flow(0)), AbstractionRate("same", Flow(0))))


@pytest.mark.parametrize(
    "source,rate,expected",
    [
        (AbstractionSource.SPRING, 80, CheckFinding.PASS),
        (AbstractionSource.SPRING, 80.001, CheckFinding.FAIL),
        (AbstractionSource.GROUNDWATER, 100, CheckFinding.PASS),
        (AbstractionSource.GROUNDWATER, 100.001, CheckFinding.FAIL),
        (AbstractionSource.LAKE, 10, CheckFinding.FAIL),
    ],
)
def test_drinking_annual_source_thresholds_and_leap_duration(scope, source, rate, expected):
    volume = Volume(Flow(rate, "l/s").value * scope.period.seconds)
    annual = annual_abstraction(
        scope,
        source,
        AbstractionPurpose.DRINKING_WATER,
        volume,
    )
    result = assess_drinking_abstraction(annual)
    assert result.annual_mean == Flow(rate, "l/s")
    assert result.eligibility.finding is expected
    assert scope.period.seconds == 366 * 86400


def test_annual_means_need_complete_year_and_drinking_purpose(scope):
    annual = annual_abstraction(
        scope,
        AbstractionSource.SPRING,
        AbstractionPurpose.OTHER,
        Volume(0),
    )
    assert assess_drinking_abstraction(annual).eligibility.finding is CheckFinding.FAIL
    short = replace(scope, period=Interval(datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 2, 1, tzinfo=UTC)))
    with pytest.raises(ValueError):
        replace(annual, scope=short)
    with pytest.raises(TypeError):
        replace(annual, annual_volume=Flow(80, "l/s"))


def context(scope):
    downstream = replace(scope, location=replace(scope.location, section=CalculationSection("downstream", "1")))
    item = accepted_permanence(DownstreamPermanence(downstream, Flow(50, "l/s"), None))
    return accepted_context(
        AbstractionContext(
            scope,
            ConcessionRoute.NEW_OR_RENEWED,
            AbstractionSource.WATERCOURSE,
            CommonUse.BEYOND,
            Flow(100, "l/s"),
            SignificantEffect.UNRESOLVED,
            None,
            (item,),
        )
    )


def test_perennial_intake_and_mixed_downstream(scope):
    inputs = context(scope)
    dry = replace(scope, location=replace(scope.location, section=CalculationSection("dry", "1")))
    dry_item = accepted_permanence(DownstreamPermanence(dry, Flow(0), None))
    dry_item = replace(
        dry_item, nature_fisheries_measures=evidence(dry, PermitEvidencePurpose.NATURE_FISHERIES_MEASURES, dry_item)
    )
    inputs = accepted_context(replace(inputs, downstream=inputs.downstream + (dry_item,)))
    result = assess_permit_scope(inputs)
    assert result.route is PermitRoute.ARTICLE_30
    assert result.article_30_sections == (inputs.downstream[0].scope.location,)
    assert result.summary.finding is CheckFinding.PASS
    assert assess_permit_scope(replace(inputs, downstream=())).summary.finding is CheckFinding.UNKNOWN


def test_nonperennial_intake_requires_nature_fisheries_evidence(scope):
    inputs = accepted_context(replace(context(scope), q347_at_intake=Flow(0)))
    result = assess_permit_scope(inputs)
    assert result.route is PermitRoute.NATURE_FISHERIES
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.article_30_sections == ()
    result = assess_permit_scope(
        replace(
            inputs, nature_fisheries_measures=evidence(scope, PermitEvidencePurpose.NATURE_FISHERIES_MEASURES, inputs)
        )
    )
    assert result.summary.finding is CheckFinding.PASS


@pytest.mark.parametrize("source", [AbstractionSource.LAKE, AbstractionSource.GROUNDWATER])
@pytest.mark.parametrize(
    "effect,route",
    [
        (SignificantEffect.SIGNIFICANT, PermitRoute.ANALOGOUS_PROTECTION),
        (SignificantEffect.NOT_SIGNIFICANT, PermitRoute.OUTSIDE_ARTICLE_29),
        (SignificantEffect.UNRESOLVED, PermitRoute.UNRESOLVED),
    ],
)
def test_lake_groundwater_effect_routes(scope, source, effect, route):
    assert (
        assess_permit_scope(accepted_context(replace(context(scope), source=source, significant_effect=effect))).route
        is route
    )


def test_common_use_and_missing_applicability(scope):
    assert (
        assess_permit_scope(accepted_context(replace(context(scope), common_use=CommonUse.WITHIN))).route
        is PermitRoute.OUTSIDE_ARTICLE_29
    )
    assert assess_permit_scope(replace(context(scope), common_use=CommonUse.UNRESOLVED)).route is PermitRoute.UNRESOLVED
    assert assess_permit_scope(replace(context(scope), applicability_evidence=None)).route is PermitRoute.UNRESOLVED


def test_existing_concession_and_supplied_duty_do_not_assign_table(scope):
    result = assess_permit_scope(replace(context(scope), concession=ConcessionRoute.EXISTING))
    assert result.route is PermitRoute.REMEDIATION
    assert result.summary.finding is CheckFinding.UNKNOWN
    result = assess_permit_scope(
        replace(
            context(scope), concession=ConcessionRoute.SUPPLIED_DUTY, q347_at_intake=None, applicability_evidence=None
        )
    )
    assert result.route is PermitRoute.EXISTING_DUTY
    assert result.summary.finding is CheckFinding.PASS
    assert not hasattr(result, "prescribed_flow")


def document(scope, kind, specialists=()):
    subject = PermitDocument(kind, None, "synthetic specialist / authority", "document 1", specialists)
    return replace(subject, evidence=evidence(scope, PermitEvidencePurpose.PROCESS_DOCUMENT, subject))


def process(scope, power=300, review=EnvironmentalReview.NON_EIA):
    documents = (document(scope, PermitDocumentKind.SPECIALIST_CONSULTATION, ("fisheries", "water protection")),)
    return PermitProcess(
        scope,
        AbstractionPurpose.HYDROPOWER,
        GrossHydropower(power),
        review,
        ("fisheries", "water protection"),
        documents,
    )


@pytest.mark.parametrize("power,required", [(299.999, False), (300, False), (300.001, True)])
def test_federal_hearing_threshold_is_strict(scope, power, required):
    result = assess_permit_process(process(scope, power))
    assert (PermitDocumentKind.FEDERAL_HEARING in result.required_documents) is required
    assert result.summary.finding is (CheckFinding.UNKNOWN if required else CheckFinding.PASS)
    assert GrossHydropower("0.3", "MW") == GrossHydropower(300)


@pytest.mark.parametrize("kind", [PermitDocumentKind.FOEN_CANTONAL_OPINION, PermitDocumentKind.FOEN_CANTONAL_DRAFT])
def test_non_eia_federal_route_requires_foen_opinion_or_revised_draft(scope, kind):
    inputs = process(scope, 301)
    inputs = replace(
        inputs,
        documents=inputs.documents + (document(scope, PermitDocumentKind.FEDERAL_HEARING), document(scope, kind)),
    )
    result = assess_permit_process(inputs)
    assert result.summary.finding is CheckFinding.PASS
    assert kind in result.required_documents
    assert PermitDocumentKind.EIA_RESIDUAL_REPORT not in result.required_documents


def test_eia_residual_report_and_federal_hearing_are_separate(scope):
    inputs = process(scope, 301, EnvironmentalReview.EIA)
    inputs = replace(
        inputs,
        documents=inputs.documents
        + (
            document(scope, PermitDocumentKind.FEDERAL_HEARING),
            document(scope, PermitDocumentKind.EIA_RESIDUAL_REPORT),
        ),
    )
    result = assess_permit_process(inputs)
    assert result.summary.finding is CheckFinding.PASS
    assert PermitDocumentKind.FOEN_CANTONAL_DRAFT not in result.required_documents
    no_report = replace(inputs, documents=inputs.documents[:-1])
    assert assess_permit_process(no_report).summary.finding is CheckFinding.UNKNOWN


def test_specialist_names_drive_failure_despite_missing_hearing(scope):
    inputs = process(scope, 301)
    inputs = replace(inputs, documents=(document(scope, PermitDocumentKind.SPECIALIST_CONSULTATION, ("fisheries",)),))
    result = assess_permit_process(inputs)
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert (
        assess_permit_process(replace(process(scope), required_specialists=())).summary.finding is CheckFinding.UNKNOWN
    )


def test_process_evidence_cannot_transfer_or_erase_rejection(scope):
    other = replace(scope, scenario="other")
    inputs = replace(
        process(scope),
        documents=(document(other, PermitDocumentKind.SPECIALIST_CONSULTATION, ("fisheries", "water protection")),),
    )
    assert assess_permit_process(inputs).summary.finding is CheckFinding.UNKNOWN
    doc = document(scope, PermitDocumentKind.SPECIALIST_CONSULTATION, ("fisheries", "water protection"))
    rejected = replace(
        doc.evidence, findings=replace(doc.evidence.findings, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
    )
    inputs = replace(process(scope, 301), documents=(replace(doc, evidence=rejected),))
    result = assess_permit_process(inputs)
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE


@pytest.mark.parametrize("value", [-1, "nan", "inf", True])
def test_invalid_quantities_cannot_create_eligibility(value):
    with pytest.raises((ValueError, TypeError)):
        GrossHydropower(value)
    with pytest.raises((ValueError, TypeError)):
        Flow(value)


def test_runtime_domain_validation_and_immutability(scope):
    inputs = inventory(scope)
    with pytest.raises(FrozenInstanceError):
        inputs.time_basis = AbstractionTimeBasis.INTERVAL_MEAN
    with pytest.raises(TypeError):
        replace(inputs, time_basis="supported_instantaneous_upper_envelope")
    with pytest.raises(TypeError):
        replace(inputs, abstractions=[])
    with pytest.raises(TypeError):
        replace(context(scope), concession="existing")
    with pytest.raises(ValueError):
        PermitEvidence(replace(scope, member="another"), evidence(scope).findings)
    with pytest.raises(ValueError):
        replace(process(scope), documents=process(scope).documents * 2)


def test_evidence_cannot_silently_change_reference_kind(scope):
    from fishy.evidence import ReferenceKind

    original = evidence(scope)
    changed = replace(
        original.findings,
        provenance=replace(original.findings.provenance, reference_kind=ReferenceKind.FUTURE_CLIMATE_STRESS),
    )
    with pytest.raises(ValueError, match="declared permit scope"):
        PermitEvidence(scope, changed)


def test_both_1000_readings_fail_even_without_selection(scope):
    result = assess_limited_abstraction(Flow(10000, "l/s"), inventory(scope, (1100,)), None)
    assert result.aggregate_reading.finding is CheckFinding.FAIL
    assert result.per_abstraction_reading.finding is CheckFinding.FAIL
    assert result.eligibility.finding is CheckFinding.FAIL
    assert result.eligibility.completeness is Completeness.INCOMPLETE


def test_valid_foen_draft_is_not_discarded_for_rejected_opinion(scope):
    inputs = process(scope, 301)
    opinion = document(scope, PermitDocumentKind.FOEN_CANTONAL_OPINION)
    opinion = replace(
        opinion,
        evidence=replace(
            opinion.evidence,
            findings=replace(opinion.evidence.findings, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED),
        ),
    )
    inputs = replace(
        inputs,
        documents=inputs.documents
        + (
            opinion,
            document(scope, PermitDocumentKind.FOEN_CANTONAL_DRAFT),
            document(scope, PermitDocumentKind.FEDERAL_HEARING),
        ),
    )
    assert assess_permit_process(inputs).summary.finding is CheckFinding.PASS


def test_unrelated_accepted_use_cannot_establish_limited_abstraction(scope):
    inputs = inventory(scope)
    unrelated = replace(
        inputs.evidence,
        findings=replace(
            inputs.evidence.findings,
            scope=replace(inputs.evidence.findings.scope, intended_use="unrelated annual diagnostic"),
        ),
    )
    result = assess_limited_abstraction(
        Flow(7000, "l/s"), replace(inputs, evidence=unrelated), selection(scope, Article30Reading.PER_ABSTRACTION_1000)
    )
    assert result.eligibility.finding is CheckFinding.UNKNOWN


def test_evidence_cannot_be_rebound_to_another_section_in_same_reach(scope):
    other = replace(scope, location=replace(scope.location, section=CalculationSection("other", "2")))
    with pytest.raises(ValueError, match="declared permit scope"):
        PermitEvidence(other, evidence(scope).findings)


def test_evidence_cannot_change_configuration_version(scope):
    item = evidence(scope)
    changed = replace(item.findings, provenance=replace(item.findings.provenance, configuration_version="unrelated"))
    with pytest.raises(ValueError, match="declared permit scope"):
        PermitEvidence(scope, changed)


def test_nonperennial_intake_does_not_create_art30_from_perennial_downstream(scope):
    inputs = accepted_context(replace(context(scope), q347_at_intake=Flow(0)))
    inputs = replace(
        inputs, nature_fisheries_measures=evidence(scope, PermitEvidencePurpose.NATURE_FISHERIES_MEASURES, inputs)
    )
    result = assess_permit_scope(inputs)
    assert result.route is PermitRoute.NATURE_FISHERIES
    assert result.article_30_sections == ()
    assert result.summary.finding is CheckFinding.PASS


def test_scoped_evidence_fields_refuse_untyped_placeholders(scope):
    with pytest.raises(TypeError):
        replace(inventory(scope), evidence="unknown")
    with pytest.raises(TypeError):
        replace(context(scope), applicability_evidence="unknown")
    annual = annual_abstraction(
        scope,
        AbstractionSource.SPRING,
        AbstractionPurpose.DRINKING_WATER,
        Volume(0),
    )
    with pytest.raises(TypeError):
        replace(annual, evidence="unknown")


def test_spring_is_groundwater_for_significant_effect_applicability(scope):
    inputs = replace(
        context(scope),
        source=AbstractionSource.SPRING,
        q347_at_intake=None,
        significant_effect=SignificantEffect.SIGNIFICANT,
    )
    assert assess_permit_scope(accepted_context(inputs)).route is PermitRoute.ANALOGOUS_PROTECTION


def test_nonperennial_downstream_section_keeps_nature_fisheries_protection(scope):
    inputs = context(scope)
    dry = accepted_permanence(replace(inputs.downstream[0], q347=Flow(0)))
    result = assess_permit_scope(accepted_context(replace(inputs, downstream=(dry,))))
    assert result.summary.finding is CheckFinding.UNKNOWN


def test_process_and_reading_evidence_require_their_own_accepted_use(scope):
    wrong = evidence(scope, PermitEvidencePurpose.ANNUAL_DRINKING_ABSTRACTION)
    choice = replace(selection(scope, Article30Reading.PER_ABSTRACTION_1000), evidence=wrong)
    result = assess_limited_abstraction(Flow(7000, "l/s"), inventory(scope), choice)
    assert result.eligibility.finding is CheckFinding.UNKNOWN
    inputs = process(scope)
    document_with_wrong_use = replace(inputs.documents[0], evidence=wrong)
    assert (
        assess_permit_process(replace(inputs, documents=(document_with_wrong_use,))).summary.finding
        is CheckFinding.UNKNOWN
    )


def test_complete_physical_and_data_identity_binds_findings(scope):
    location = scope.location
    other_locations = (
        replace(location, mapping_version="2"),
        replace(location, section=replace(location.section, version="2")),
        replace(location, reach=replace(location.reach, version="2")),
        replace(location, reach=replace(location.reach, water_body=replace(location.reach.water_body, version="2"))),
    )
    alternatives = tuple(replace(scope, location=item) for item in other_locations) + (
        replace(scope, data_version="2"),
        replace(scope, configuration_version="2"),
    )
    for other in alternatives:
        with pytest.raises(ValueError, match="declared permit scope"):
            PermitEvidence(other, evidence(scope).findings)


@pytest.mark.parametrize("mutation", ["kind", "issuer", "reference", "specialists"])
def test_reviewed_document_content_cannot_be_replaced(scope, mutation):
    inputs = process(scope, 301)
    opinion = document(scope, PermitDocumentKind.FOEN_CANTONAL_OPINION)
    hearing = document(scope, PermitDocumentKind.FEDERAL_HEARING)
    if mutation == "kind":
        hearing = replace(opinion, kind=PermitDocumentKind.FEDERAL_HEARING)
    elif mutation == "issuer":
        hearing = replace(hearing, issuer="another issuer")
    elif mutation == "reference":
        hearing = replace(hearing, reference="another document")
    else:
        inputs = replace(
            inputs,
            documents=(
                replace(
                    inputs.documents[0], consulted_specialists=inputs.required_specialists + ("invented specialist",)
                ),
            ),
        )
    result = assess_permit_process(replace(inputs, documents=inputs.documents + (opinion, hearing)))
    assert result.summary.finding is CheckFinding.UNKNOWN


def test_reviewed_reading_and_status_cannot_be_replaced(scope):
    choice = selection(scope, Article30Reading.AGGREGATE_1000)
    altered = replace(choice, reading=Article30Reading.PER_ABSTRACTION_1000)
    assert (
        assess_limited_abstraction(Flow(7000, "l/s"), inventory(scope), altered).eligibility.finding
        is CheckFinding.UNKNOWN
    )
    altered = replace(selection(scope, Article30Reading.PER_ABSTRACTION_1000), status=DecisionStatus.SUPPLIED_AUTHORITY)
    assert (
        assess_limited_abstraction(Flow(7000, "l/s"), inventory(scope), altered).eligibility.finding
        is CheckFinding.UNKNOWN
    )


def test_reviewed_inventory_rates_cannot_be_replaced(scope):
    original = inventory(scope)
    altered = replace(original, abstractions=(AbstractionRate("invented", Flow(1, "l/s")),))
    result = assess_limited_abstraction(
        Flow(7000, "l/s"), altered, selection(scope, Article30Reading.PER_ABSTRACTION_1000)
    )
    assert result.eligibility.finding is CheckFinding.UNKNOWN


def test_reviewed_annual_volume_cannot_be_replaced(scope):
    annual = annual_abstraction(
        scope,
        AbstractionSource.SPRING,
        AbstractionPurpose.DRINKING_WATER,
        Volume(100000),
    )
    assert assess_drinking_abstraction(annual).eligibility.finding is CheckFinding.PASS
    altered = replace(annual, annual_volume=Volume(0))
    assert assess_drinking_abstraction(altered).eligibility.finding is CheckFinding.UNKNOWN


def test_reviewed_applicability_and_permanence_cannot_be_replaced(scope):
    inputs = context(scope)
    assert assess_permit_scope(replace(inputs, common_use=CommonUse.WITHIN)).summary.finding is CheckFinding.UNKNOWN
    altered = replace(inputs.downstream[0], q347=Flow(70, "l/s"))
    reviewed_parent = accepted_context(replace(inputs, downstream=(altered,)))
    assert assess_permit_scope(reviewed_parent).summary.finding is CheckFinding.UNKNOWN
