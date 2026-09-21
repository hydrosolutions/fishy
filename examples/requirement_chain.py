"""requirement_chain : AcceptedSyntheticReferences × ScenarioProfile → IssuedScenario.

U9 uses full 2001/2002 reference years and 365-day 2003 design families.
All acceptance, physical relations and thresholds are explicit synthetic assumptions.
This is neither adopted Uzbek policy nor ecological or basin validation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from typing import TYPE_CHECKING

from fishy.annual_statistics import (
    AnnualReference,
    ExceedanceProbability,
    TrendTreatment,
    annual_mean,
    fitted_estimate,
)
from fishy.daily_patterns import (
    AlignmentChoice,
    AlignmentSettings,
    AnalogueReference,
    DailyReferenceYear,
    DonorEligibility,
    MembershipEstimator,
    PatternProfile,
    annual_magnitude_product,
    construct_pattern,
    pattern_product,
)
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    ScientificAdequacy,
)
from fishy.flows import FlowSample, Presence
from fishy.hydraulics import (
    BoundState,
    CriterionStatus,
    HydraulicRelationEvidence,
    HydraulicScope,
    HydraulicState,
    HydraulicVariable,
    RelationDomain,
    StateBounds,
    StateCriterion,
    StateLimit,
    TemporalSupport,
    assess_state_range,
)
from fishy.hydraulics import Comparison as HydraulicComparison
from fishy.load_accounts import (
    AccountTransfer,
    ControlState,
    Inventory,
    LoadAccount,
    Mass,
    ResidualSourceKind,
    SourceControlEvidence,
    assess_load_accounts,
)
from fishy.mixing import BoundarySupport, FixedBoundary, LoadRate, MixingConstituent
from fishy.pattern_calendar import AccountingYear
from fishy.quality import ChemicalBehavior, ChemicalIdentity, QualityTarget, QualityValue
from fishy.quality import Comparison as QualityComparison
from fishy.quality_activation import (
    ActivationCondition,
    ActivationConditions,
    ActivationMode,
    BackgroundAccountMapping,
    EvidenceState,
    QualityActivation,
    QualityRoute,
    apply_quality_component,
)
from fishy.quantities import Flow, Volume
from fishy.receptor_delivery import (
    BoundInclusion,
    ControlMapping,
    DeliveryContext,
    DeliveryStep,
    ExchangeDirection,
    Pathway,
    PathwayRelease,
    ProcessTest,
    StorageBalance,
    SupportedProcessTest,
    WaterExchange,
    WaterRelationship,
    control_equivalent,
    delivery_scope,
)
from fishy.scientific_acceptance import (
    AcceptanceRecord,
    Aggregation,
    ClimateTreatment,
    CriterionRole,
    DailyDerivation,
    DiagnosticObservation,
    ErrorMeasure,
    EvidenceItem,
    EvidenceRequirement,
    HydrologicalProductKind,
    RatingSupport,
    ScientificCriterion,
    ScientificEvidence,
    UsePurpose,
    ValidationEvidence,
    ValidationMethod,
    assess_scientific_use,
    minimum_evidence,
)
from fishy.scientific_acceptance import Comparison as ScientificComparison
from fishy.spatial import (
    CalculationSection,
    Location,
    Reach,
    WaterBody,
)
from fishy.study_requirements import (
    FlowResponseRelation,
    Interpolation,
    ResponsePoint,
    ResponseVariable,
    StudyCriterion,
    StudyScope,
    StudySelection,
    StudyVariable,
    assess_study,
)
from fishy.time import Interval

if TYPE_CHECKING:
    from fishy.daily_patterns import DailyPattern
    from fishy.delivery_assessment import DeliveryComparison
    from fishy.duration_minima import DurationThreshold
    from fishy.low_flow_safeguard import LowFlowAssessment
    from fishy.natural_baseline import BaselineResult
    from fishy.potential_requirements import PotentialFloorResult
    from fishy.requirement_checks import RequirementAssessment
    from fishy.requirement_composition import IntervalComposition
    from fishy.requirement_family import FamilySelection, RequirementFamily
    from fishy.requirement_finalization import FinalFloors, FinalRegime
    from fishy.uzbek_issuance import IssuedObligation


def synthetic_acceptance(subject):
    """Hypothetical external study; declared 1-unit maxima pass at equality.

    The frozen record precedes the supplied withheld diagnostics. This exercises
    permission plumbing, not scientific certification of these synthetic rivers.
    """
    contracts = ((EvidenceRequirement.DISTRIBUTION, "m3/s", "annual-mean-error"),)
    if subject.kind is HydrologicalProductKind.DAILY_PATTERN:
        contracts = (
            (EvidenceRequirement.SEASONAL_SHARES, "percent", "season-volume/annual-volume*100"),
            (EvidenceRequirement.TIMING, "days", "first-half-volume-time-nonwrapping"),
            (EvidenceRequirement.MINIMA, "m3/s", "minimum-complete-seven-day-mean"),
            (EvidenceRequirement.SPELLS, "days", "longest-strict-below-fixed-threshold"),
        )
    cases = ("heldout-climate-2010", "heldout-climate-2011")
    criteria = tuple(
        ScientificCriterion(
            requirement.value,
            CriterionRole.MANDATORY,
            formula,
            "synthetic withheld year",
            units,
            ErrorMeasure.ABSOLUTE,
            Aggregation.EACH_CASE,
            ScientificComparison.AT_MOST,
            1.0,
            cases,
            "hypothetical test distinction of one unit, not a policy threshold",
            requirement,
        )
        for requirement, units, formula in contracts
    )
    record = AcceptanceRecord(
        subject,
        "synthetic-acceptance-v1",
        "preparer",
        "independent-reviewer",
        datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 9, 4, tzinfo=UTC),
        criteria,
        "synthetic sampling and rating uncertainty with declared coverage",
        ("structural alternatives",),
        "stipulated synthetic sizing only; no official or site-validation permission",
        (subject.scope.intended_use,),
        (),
        "new independent evidence required",
    )
    observations = tuple(
        DiagnosticObservation(
            c.criterion_id,
            case,
            1.0,
            0.0,
            c.units,
            c.formula,
            c.domain,
            "hypothetical withheld independent diagnostics",
        )
        for c in record.criteria
        for case in cases
    )
    validation = ValidationEvidence(
        ValidationMethod.WITHHELD,
        ("training-climate-2000",),
        cases,
        (),
        (),
        ("training-case",),
        cases,
        ("training-climate-2000",),
        cases,
        ("heldout-donor",),
        ("shared-rating-error",),
        datetime(2026, 9, 3, tzinfo=UTC),
        "caller-owned whole climate-year holdouts",
    )
    items = tuple(
        EvidenceItem(
            requirement,
            CheckFinding.PASS,
            "synthetic external study",
            "explicit hypothetical supported finding; not empirical site certification",
        )
        for requirement in minimum_evidence(subject, DailyDerivation.NATIVE)
    )
    evidence = ScientificEvidence(
        subject,
        record.profile_version,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        OfficialAdmissibility.PENDING,
        items,
        observations,
        validation,
        RatingSupport.WITHIN_RANGE,
        ClimateTreatment.COMMON_BASIS,
        DailyDerivation.NATIVE,
        frozen_record=record,
    )
    assessment = assess_scientific_use(record, evidence)
    assert assessment.findings.scientific_adequacy is ScientificAdequacy.ACCEPTED
    assert assessment.acceptance_for(subject).finding is CheckFinding.PASS
    assert all(c.actual == c.criterion.limit == 1.0 for c in assessment.comparisons)
    return assessment


SCENARIO = "U9-supported-synthetic-v1"
TARGET = AccountingYear(2003, 1, 0)


def location(section):
    return Location(
        Reach("U9-reach", "v1", WaterBody("synthetic-river", "v1")), CalculationSection(section, "v1"), "v1"
    )


def provenance(member):
    return Provenance(
        "U9 stipulated synthetic reference",
        SCENARIO,
        member,
        "fishy-0.1.2/requirement-composition-v1",
        "v1",
        "v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
        limitations=(
            "Two structurally distinct references assumed, not empirically validated",
            "Rare-year shape acceptance stipulated only for this synthetic case",
            "21/21 dry-case seven-day overestimation remains a method limitation; no correction applied",
        ),
    )


def samples(calendar, value, member, section="R"):
    return tuple(
        FlowSample(
            location(section),
            Interval(calendar.interval.start + timedelta(days=i), calendar.interval.start + timedelta(days=i + 1)),
            Flow(value),
            Presence.PRESENT,
            provenance(member),
        )
        for i in range(calendar.days)
    )


def reference_patterns(member, wet, dry):
    """Two complete daily reference years → five probability-specific accepted patterns."""
    years = tuple(
        DailyReferenceYear(
            AccountingYear(year, 1, 0),
            samples(AccountingYear(year, 1, 0), flow, member),
            str(year),
            CheckSummary(
                (
                    Check(
                        "synthetic-reference",
                        CheckFinding.PASS,
                        ("Explicit stipulated complete constant reference; not field validation",),
                    ),
                )
            ),
        )
        for year, flow in ((2001, wet), (2002, dry))
    )
    reference = AnnualReference(
        tuple(
            annual_mean(y.samples, accounting_start_month=1, utc_offset_minutes=0, provenance=provenance(member))
            for y in years
        ),
        Interval(years[0].calendar.interval.start, years[-1].calendar.interval.end),
        "stipulated-present-climate",
        1,
        0,
        (),
        TrendTreatment.COMMON_CLIMATE,
        "explicit U9 common-climate assumption",
    )
    pool = AnalogueReference(reference, years)
    patterns = {}
    for percent in (50, 75, 90, 97, 99):
        target = ExceedanceProbability(Fraction(percent, 100))
        annual = fitted_estimate(reference, target, provenance=provenance(member), profile_version="U9-lognormal-v1")
        settings = PatternProfile(
            "U9-h1-no-melt-v1",
            target,
            Fraction(1),
            member,
            SCENARIO,
            reference.climate_basis,
            MembershipEstimator.FITTED,
            (
                DonorEligibility(
                    location("R"), ("same member full reference",), years[0].quality_checks, provenance(member)
                ),
            ),
            2,
            2,
            AlignmentSettings(AlignmentChoice.CALENDAR, 0, 365, Fraction(0)),
            "synthetic-acceptance-v1",
            reference.reference_period,
        )
        magnitude_acceptance = synthetic_acceptance(
            annual_magnitude_product(annual, intended_use="U9-scenario", purpose=UsePurpose.SIZING)
        )
        preliminary = construct_pattern(
            annual,
            TARGET,
            (pool,),
            settings,
            intended_use="U9-scenario",
            purpose=UsePurpose.SIZING,
            magnitude_assessment=magnitude_acceptance,
        )
        shape_acceptance = synthetic_acceptance(
            pattern_product(preliminary, intended_use="U9-scenario", purpose=UsePurpose.SIZING)
        )
        patterns[percent] = construct_pattern(
            annual,
            TARGET,
            (pool,),
            settings,
            intended_use="U9-scenario",
            purpose=UsePurpose.SIZING,
            magnitude_assessment=magnitude_acceptance,
            shape_assessment=shape_acceptance,
        )
    return reference, years, patterns


def accepted_evidence(scope, source):
    """Exact synthetic subject → explicitly assumed supported-use evidence, never official."""
    return EvidenceFindings(
        scope,
        source,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("Stipulated synthetic support only; no site or ecological validation",),
    )


def quality(
    base,
    interval,
    member,
    *,
    route=QualityRoute.REGIME,
    source_concentration=Fraction(0),
    background_concentration=Fraction(9, 1000),
    activation_mode=ActivationMode.HYPOTHETICAL,
    source_provenance=None,
):
    """Same-section total flow × fixed conservative account → active quality candidate."""
    source = provenance(member) if source_provenance is None else source_provenance
    chemical = ChemicalIdentity(
        "synthetic salt", "conservative solute", "salt mass", "dissolved", ChemicalBehavior.CONSERVATIVE
    )
    boundary = FixedBoundary(
        location("R"),
        interval,
        Flow(1),
        (MixingConstituent(chemical, LoadRate(background_concentration), QualityValue(source_concentration, "kg/m3")),),
        BoundarySupport(
            f"fixed complete mixing; background1 at{background_concentration}kg/m3; zero storage and no other loads"
        ),
        source,
    )
    target = QualityTarget(
        "U9-upper-1mg/l",
        chemical,
        QualityComparison.LE,
        QualityValue(Fraction(1, 1000), "kg/m3"),
        "daily interval",
        "hypothetical U9 target",
    )
    missing = ActivationCondition(EvidenceState.MISSING, "national approvals not claimed")
    activation = QualityActivation(
        SCENARIO,
        route,
        activation_mode,
        ActivationConditions(missing, missing, missing, missing, missing),
        "explicit U9 hypothetical activation",
    )
    controls = SourceControlEvidence(
        SCENARIO,
        "R",
        interval,
        ControlState.EXHAUSTED,
        (("background", ResidualSourceKind.UNCONTROLLABLE_DIFFUSE),),
        "stipulated uncontrollable background; no controllable source omitted",
    )
    empty = Inventory(Volume(0), Mass(0))
    inventory = Inventory(Volume(interval.seconds), Mass(background_concentration * interval.seconds))
    account = LoadAccount("R", chemical, interval, SCENARIO, empty, empty, source)
    ledger = assess_load_accounts(
        (account,),
        (AccountTransfer("background", None, "R", inventory), AccountTransfer("outflow", "R", None, inventory)),
    )
    return apply_quality_component(
        base,
        boundary,
        (target,),
        activation,
        controls,
        (ledger,),
        BackgroundAccountMapping(("background",), "all background and only background", location("R")),
    )


def lateral(continuing, interval, member, candidate):
    """Continuing flow × supported lateral1 → upstream equivalent under signed balance."""
    ctx = DeliveryContext(location("wetland"), interval, candidate, "wetland lateral daily arrival", provenance(member))
    mapping = ControlMapping(
        ctx,
        location("U"),
        location("R"),
        continuing,
        Flow(1),
        WaterRelationship.LATERAL,
        "U9 no-loss/no-delay/no-storage carrier balance U=R+wetland; dedicated lateral pathway",
    )
    return control_equivalent(mapping, accepted_evidence(delivery_scope(ctx, mapping), ctx.provenance))


def final_physics(upstream, interval, member, candidate):
    """Selected U flow → recomputed R quality, lateral balance, depth and habitat findings.

    Synthetic supported relations: depth=Q_U/10 m, habitat=10 Q_U m2,
    valid on [0,30]m3/s. Limits are hypothetical depth[1,3], habitat[100,300].
    Relations evaluate the supplied final candidate, not a disconnected PASS.
    """
    continuing = Flow(upstream.value - 1)
    q = quality(continuing, interval, member)
    receptor = lateral(continuing, interval, member, candidate)
    metadata = HydraulicRelationEvidence(
        "U9-relations-v1",
        "synthetic geometry",
        "fixed zero backwater",
        "0<=Q_U<=30 m3/s",
        "linear synthetic relation",
        "exact synthetic singleton support",
        "U9 scenario only",
        RelationDomain.SUPPORTED,
    )
    scope = StudyScope(candidate, location("U"), interval, SCENARIO, member, "U9-study", "all-year")
    ev = accepted_evidence(EvidenceScope(candidate, "U9-reach", member, interval, "U9-study"), provenance(member))
    habitat = ResponseVariable(StudyVariable.HABITAT, "m2", "synthetic survey datum", "wetted area")
    relation = FlowResponseRelation(
        scope,
        habitat,
        (
            ResponsePoint(Flow(0), StateBounds(Fraction(0), Fraction(0))),
            ResponsePoint(Flow(30), StateBounds(Fraction(300), Fraction(300))),
        ),
        Interpolation.LINEAR,
        "U9 synthetic relation, not field survey",
        metadata,
        ev,
    )
    criterion = StudyCriterion(
        "habitat",
        habitat,
        StateBounds(Fraction(100), Fraction(300)),
        HydraulicComparison.INCLUSIVE,
        HydraulicComparison.INCLUSIVE,
        "U9 explicit hypothetical habitat limits",
    )
    study = assess_study(
        StudySelection(
            scope, upstream, "external U9 structural selection", "synthetic habitat", ev, (criterion,), (), ()
        ),
        (relation,),
    )
    hydraulic_scope = HydraulicScope(
        "depth",
        location("U"),
        "synthetic section mean depth",
        candidate,
        SCENARIO,
        HydraulicVariable.DEPTH,
        interval,
        "synthetic bed datum",
        TemporalSupport.DAILY_MEANS,
    )
    hydraulic_evidence = accepted_evidence(
        EvidenceScope(candidate, "U9-reach", member, interval, "depth"), provenance(member)
    )
    depth = upstream.value / 10
    hydraulics = assess_state_range(
        StateCriterion(
            hydraulic_scope,
            "U9 synthetic depth limits",
            CriterionStatus.HYPOTHETICAL,
            StateLimit(BoundState.SUPPLIED, Fraction(1)),
            StateLimit(BoundState.SUPPLIED, Fraction(3)),
        ),
        HydraulicState(hydraulic_scope, StateBounds(depth, depth), hydraulic_evidence, relation=metadata),
    )
    return q, receptor, study, hydraulics


def wetland_step(interval, member, candidate):
    """Selected lateral1 schedule → candidate-bound quantity and salinity assessment inputs."""
    ctx = DeliveryContext(location("wetland"), interval, candidate, "synthetic well-mixed wetland", provenance(member))
    outflow = WaterExchange(
        "wetland-drain", ctx, ExchangeDirection.OUTFLOW, Volume(interval.seconds), location("drain")
    )
    balance = StorageBalance(
        ctx,
        Volume(86400),
        Volume(86400),
        (outflow,),
        "U9 steady wetland stock: lateral1 in, drain1 out; no evaporation",
        "explicit exact synthetic support",
    )
    predecessor = Interval(interval.start - timedelta(days=1), interval.start)
    path = Pathway(
        "lateral",
        ctx,
        location("U"),
        interval,
        timedelta(0),
        Volume(0),
        Volume(0),
        (),
        Flow(0),
        Flow(2),
        Flow(1),
        predecessor,
        Fraction(0),
        Fraction(0),
        "U9 zero loss storage delay mapping",
        "explicit constant lateral1 predecessor; not implicit observed wrap",
        "exact hypothetical singleton flows",
    )
    salt = ProcessTest(
        "salt",
        ctx,
        "resident salinity",
        "kg/m3",
        "whole synthetic mixed wetland; daily mean",
        Fraction(0),
        None,
        Fraction(1, 1000),
        BoundInclusion.INCLUSIVE,
        "stipulated salt-free initial stock and lateral source, conservative mixing, drain carries salt",
    )
    step = DeliveryStep(
        balance,
        accepted_evidence(delivery_scope(ctx, balance), ctx.provenance),
        (PathwayRelease(path, Volume(interval.seconds), accepted_evidence(delivery_scope(ctx, path), ctx.provenance)),),
        ("lateral",),
        ("salt",),
        (SupportedProcessTest(salt, accepted_evidence(delivery_scope(ctx, salt), ctx.provenance)),),
        None,
    )
    return replace(
        step,
        checking_evidence=accepted_evidence(
            delivery_scope(ctx, step.checking_subject),
            replace(ctx.provenance, source="independent synthetic audit of exact selected wetland inputs"),
        ),
    )


def final_assessment(sample):
    """Final upstream FlowSample → all applicable recomputed physical checks."""
    from fishy.requirement_checks import FinalCondition, assess_requirement, sample_subject

    candidate = sample_subject(sample)
    q, mapping, study, hydraulic = final_physics(
        sample.value, sample.interval, sample.provenance.reference_member, candidate
    )
    receptor = wetland_step(sample.interval, sample.provenance.reference_member, candidate)
    return assess_requirement(
        sample,
        tuple(FinalCondition),
        quality=q,
        mapping=mapping,
        receptor=receptor,
        hydraulic_required=(hydraulic.criterion.scope,),
        hydraulic_components=(hydraulic,),
        study_selection=study.selection,
        study_relations=tuple(response.relation for response in study.responses),
    )


def independent_duty():
    """Existing sanitary schedule × supplied delivery → independent uncapped shortfalls."""
    from fishy.duties import Delivery, DutyApplicability, Obligation, SuppliedDuty, assess_duty

    prescribed = samples(TARGET, 2, "independent-duty", "U")[:2]
    prescribed = (prescribed[0], replace(prescribed[1], value=Flow(3)))
    duty = SuppliedDuty(
        "independent sanitary duty",
        "v1",
        "supplied hypothetical sanitary schedule, no sizing needed",
        DutyApplicability.HYPOTHETICAL,
        tuple(Obligation(s, "v1") for s in prescribed),
        "synthetic inventory",
    )
    delivery = tuple(
        Delivery(replace(s, value=Flow(q)), "v1")
        for s, q in zip(prescribed, (Fraction(3, 2), Fraction(7, 2)), strict=True)
    )
    return assess_duty(duty, delivery)


def singleton(flow):
    """Stipulated exact synthetic Flow → enclosing singleton support, not measurement precision."""
    from fishy.quantities import FlowBounds

    return FlowBounds(
        flow,
        flow,
        "explicit fixed synthetic value",
        "U9 stipulated support",
        "joint singleton support; no independent marginal confidence assumption",
    )


def duration_threshold(member, years, *, section="U"):
    """Complete U reference chronology and six wet precursor days → fitted annual7/T100 threshold."""
    from fishy.duration_minima import DurationEstimator, construct_duration_reference, estimate_duration_threshold
    from fishy.duration_windows import DurationWindowRule, WindowDomain, WindowUncertaintySupport
    from fishy.low_flow_frequency import LowFlowReturnPeriod

    reference_samples = tuple(
        replace(s, location=location(section), uncertainty=singleton(s.value)) for y in years for s in y.samples
    )
    first = reference_samples[0]
    predecessor = tuple(
        replace(
            first,
            interval=Interval(first.interval.start - timedelta(days=i), first.interval.start - timedelta(days=i - 1)),
        )
        for i in range(6, 0, -1)
    )
    rule = DurationWindowRule(
        7, WindowDomain.ANNUAL, 1, 0, None, "U9 hypothetical annual7/T100, not an ecological default"
    )
    support = WindowUncertaintySupport(
        "exact synthetic joint singleton support", "U9", "fixed values; no independence inference"
    )
    reference = construct_duration_reference(
        predecessor + reference_samples,
        Interval(years[0].calendar.interval.start, years[-1].calendar.interval.end),
        rule,
        location=location(section),
        provenance=provenance(member),
        predecessor_basis=f"six explicit wet-reference days before2001; stipulated {section} reference",
        climate_basis="stipulated-present-climate",
        trend=TrendTreatment.COMMON_CLIMATE,
        climate_evidence="U9 stipulated accepted synthetic reference at U, not transferred basin evidence",
        dependence="two hypothetical years only; structural independence is an assumption",
        uncertainty_support=support,
    )
    threshold = estimate_duration_threshold(
        reference, LowFlowReturnPeriod(100), estimator=DurationEstimator.ZERO_MIXTURE, profile_version="U9-duration-v1"
    )
    return replace(threshold, uncertainty=singleton(threshold.value))


def safeguard(series, threshold, *, stage, predecessor="explicit_constant_synthetic"):
    """Complete class plus separately declared precursor support → every eligible seven-day test."""
    from fishy.duration_windows import WindowUncertaintySupport
    from fishy.low_flow_safeguard import CandidateReferenceRelation, assess_low_flow

    values = tuple(replace(s, uncertainty=singleton(s.value)) for s in series)
    first = values[0]
    prefix = (
        ()
        if predecessor is None
        else tuple(
            replace(
                first,
                interval=Interval(
                    first.interval.start - timedelta(days=i), first.interval.start - timedelta(days=i - 1)
                ),
            )
            for i in range(6, 0, -1)
        )
    )
    assessment = synthetic_acceptance(threshold.product(UsePurpose.SIZING))
    return assess_low_flow(
        prefix + values,
        TARGET.interval,
        threshold,
        stage=stage,
        candidate_basis="U9 exact class candidate",
        provenance=first.provenance,
        predecessor_basis=predecessor,
        scientific_assessment=assessment,
        uncertainty_support=WindowUncertaintySupport(
            "exact synthetic joint singleton support", "U9", "fixed values, not measured certainty"
        ),
        purpose=UsePurpose.SIZING,
        reference_relation=CandidateReferenceRelation(
            first.provenance,
            threshold.reference.identity,
            "selected U requirement rechecked against this retained member U reference; neither is a mosaic natural reconstruction",
        ),
    )


def assembled_member(member, reference, years, patterns):
    """Accepted member hydrology → pre-quality baseline and complete uncapped upstream family."""
    from fishy.natural_baseline import RecordedMinimum, baseline_family, recorded_minimum_product
    from fishy.requirement_composition import compose_requirement
    from fishy.requirement_family import ClassRequirement, FamilyBasis, RequirementFamily

    record = RecordedMinimum(
        reference,
        years,
        "complete synthetic daily record; no infill",
        "supported fixed synthetic values; not field uncertainty",
    )
    record = replace(
        record,
        assessment=synthetic_acceptance(
            recorded_minimum_product(record, intended_use="U9-scenario", purpose=UsePurpose.SIZING)
        ),
    )
    baseline = baseline_family(
        tuple(patterns.values()), record, provenance=provenance(member), profile_version="U9-baseline-v1"
    )
    assert baseline.candidate is not None
    components = []
    classes = []
    for regime in baseline.candidate.classes:
        composed = []
        for sample in regime.samples:
            q = quality(sample.value, sample.interval, member)
            mapping = lateral(q.combined, sample.interval, member, "U9-member-composition")
            component = compose_requirement(
                sample, provenance(member), quality=q, mapping=mapping.mapping, mapping_evidence=mapping.evidence
            )
            assert component.candidate is not None and component.candidate.value is not None
            component = replace(
                component, candidate=replace(component.candidate, uncertainty=singleton(component.candidate.value))
            )
            components.append(component)
            assert component.candidate is not None
            composed.append(component.candidate)
        classes.append(ClassRequirement(regime.design, tuple(composed)))
    basis = FamilyBasis(
        location("U"),
        TARGET.interval,
        SCENARIO,
        "uzbek_baseline",
        "v1",
        "U9-hypothetical-quality-v1",
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
    )
    return baseline, tuple(components), RequirementFamily(basis, tuple(classes))


def natural_tier(baseline):
    """Exact accepted baseline products → explicit natural classification and evidence-aware tier."""
    from fishy.natural_routing import (
        Availability,
        NaturalRoute,
        ScientificRequirement,
        ScopedRequirement,
        TierEvidence,
        reconstruction_disclosure_scope,
    )
    from fishy.spatial import DesignationState, Eligibility, Origin, PreparedClassification, UseCategory

    record = baseline.inputs.recorded
    assert record is not None
    patterns = baseline.inputs.patterns
    classification = PreparedClassification(
        Origin.NATURAL,
        DesignationState.NONE,
        Eligibility.NOT_APPLICABLE,
        UseCategory.AGRICULTURE_IRRIGATION,
        ("hypothetical irrigation river",),
        "explicit U9 natural-origin assumption; use category does not choose track",
        "v1",
    )
    statistics = []
    for pattern in patterns:
        target = pattern.magnitude.target.value
        statistics.append(
            ScientificRequirement(
                f"annual:{target}",
                annual_magnitude_product(
                    pattern.magnitude, intended_use=pattern.requested_use, purpose=UsePurpose.SIZING
                ),
                pattern.magnitude_assessment,
            )
        )
        statistics.append(
            ScientificRequirement(
                f"shape:{target}",
                pattern_product(pattern, intended_use=pattern.requested_use, purpose=UsePurpose.SIZING),
                pattern.shape_assessment,
            )
        )
    scope = reconstruction_disclosure_scope(record.reference)
    disclosure = ScopedRequirement(
        "reconstruction_disclosure", scope, accepted_evidence(scope, record.reference.provenance)
    )
    tier = TierEvidence(
        NaturalRoute.BASELINE,
        record.reference.location,
        "U9-tier-v1",
        Availability.AVAILABLE,
        Availability.AVAILABLE,
        Check("top_priority", CheckFinding.UNKNOWN, ("no separate top-tier priority commissioned in U9",)),
        (*tuple(s.identifier for s in statistics), "reconstruction_disclosure"),
        tuple(statistics),
        (disclosure,),
        (),
        "explicit U9 supported and resourced baseline; other tiers not commissioned",
        patterns,
        record,
    )
    return classification, tier


def external_selection(families: tuple[tuple[str, RequirementFamily], ...]) -> FamilySelection:
    """Fixed complete member families → externally chosen uncapped family, verified by Fishy."""
    from fishy.requirement_family import (
        ClassRequirement,
        ReconstructionNeed,
        RequirementFamily,
        RequirementMember,
        SelectionSpecification,
        assess_selected_family,
        candidate_scope,
    )

    members = tuple(
        RequirementMember(
            name,
            "stipulated structurally distinct reconstruction " + name,
            family,
            accepted_evidence(candidate_scope(family), family.classes[0].samples[0].provenance),
            "same two climate years; structural distinction assumed, not empirically proved",
        )
        for name, family in families
    )
    selected_classes = []
    # Caller owns comparison; provisional theta=.20 is explicit scenario configuration.
    rows = []
    for _, family in families:
        row = []
        for cls in family.classes:
            for sample in cls.samples:
                assert sample.value is not None
                row.append(sample.value.value)
        rows.append(tuple(row))
    values = tuple(rows)
    medians = tuple(sum(pair) / 2 for pair in zip(*values, strict=True))
    spread = max(
        (max(pair) - min(pair)) / median for pair, median in zip(zip(*values, strict=True), medians, strict=True)
    )
    offset = 0
    for cls in families[0][1].classes:
        chosen = []
        for sample in cls.samples:
            pair = tuple(value[offset] for value in values)
            value = medians[offset] if spread <= Fraction(1, 5) else max(pair)
            chosen.append(
                replace(
                    sample,
                    value=Flow(value),
                    uncertainty=singleton(Flow(value)),
                    provenance=provenance("selected"),
                    components=(),
                    reasons=("externally selected uncapped requirement; not a mosaic natural reconstruction",),
                )
            )
            offset += 1
        selected_classes.append(ClassRequirement(cls.design, tuple(chosen)))
    selected = RequirementFamily(members[0].candidate.basis, tuple(selected_classes))
    specification = SelectionSpecification(
        tuple(m.identifier for m in members),
        (),
        Fraction(1, 5),
        ReconstructionNeed.REQUIRED,
        "U9 caller-owned whole-family rule; theta.20 hypothetical, not an adopted uncertainty limit",
    )
    return assess_selected_family(members, selected, specification)


def issue_and_assess(sample):
    """Accepted uncapped requirement × deliverability6 × actual5 → immutable issued comparison."""
    from fishy.comparison_evidence import Attribution, AttributionFinding, ComparisonEvidence
    from fishy.delivery_assessment import assess_issued_delivery
    from fishy.duties import Deliverability, Delivery, Requirement
    from fishy.uzbek_issuance import issue_obligation

    capacity = replace(
        sample, value=Flow(6), components=(), uncertainty=None, reasons=("separately stipulated deliverability6",)
    )
    issue = issue_obligation(
        Requirement(sample, "U9-requirement-v1"),
        Deliverability(capacity, "U9-capacity-v1"),
        version="U9-issued-v1",
        provenance=sample.provenance,
    )
    actual = Delivery(
        replace(
            sample,
            value=Flow(5),
            components=(),
            uncertainty=singleton(Flow(5)),
            reasons=("stipulated actual scenario5; not observed compliance",),
        ),
        "U9-delivery-v1",
    )
    evidence = ComparisonEvidence(
        issue.obligation,
        actual,
        None,
        tuple(
            Check(name, CheckFinding.PASS, (reason,))
            for name, reason in (
                ("coverage", "exact full daily synthetic interval"),
                ("infill", "no missing values or infill in stipulated scenario"),
                ("authentication", "explicit fixture assumption; not authenticated observation"),
                ("reconciliation", "stipulated independent technical support for scenario5"),
                ("uncertainty", "supported singleton enclosing synthetic5; no measurement-certainty claim"),
            )
        ),
        None,
        OfficialAdmissibility.PENDING,
        Attribution(
            AttributionFinding.UNASSESSED,
            "causality not supplied",
            Check("operator_control", CheckFinding.UNKNOWN, ("scenario does not establish operator control",)),
        ),
        "U9 exact versioned hypothetical operands",
    )
    return issue, assess_issued_delivery(issue.obligation, actual, evidence=evidence)


@dataclass(frozen=True)
class ChainResult:
    """Attributable U9 intermediate products and immutable final issued records."""

    prepared: dict[str, tuple[AnnualReference, tuple[DailyReferenceYear, ...], dict[int, DailyPattern]]]
    baselines: dict[str, BaselineResult]
    compositions: dict[str, tuple[IntervalComposition, ...]]
    families: dict[str, RequirementFamily]
    thresholds: dict[str, DurationThreshold]
    provisional: dict[str, tuple[LowFlowAssessment, ...]]
    member_duration: dict[str, tuple[LowFlowAssessment, ...]]
    member_physical: dict[str, tuple[RequirementAssessment, ...]]
    selection: FamilySelection
    final: FinalRegime
    issued: tuple[tuple[IssuedObligation, DeliveryComparison], ...]


def run_chain(prepared=None):
    """Complete supplied U9 scenario → all member, selected, final-floor and issued records."""
    from fishy.design_conditions import DesignClass
    from fishy.duration_windows import WindowUncertaintySupport
    from fishy.low_flow_safeguard import AssessmentStage, CandidateReferenceRelation
    from fishy.natural_baseline import EcologicalRegimeMethod
    from fishy.requirement_checks import FinalCondition
    from fishy.requirement_construction import BaselineSource, ClassComposition, MemberConstruction, NaturalRouteInputs
    from fishy.requirement_family import RequirementFamily
    from fishy.requirement_finalization import ClassAssessment, DurationTest, MemberPhysical, finalize_regime

    if prepared is None:
        prepared = {
            "A": reference_patterns("A", "13.498588075760033", "7.4081822068171785"),
            "B": reference_patterns("B", "20.24788211364005", "11.112273310225769"),
        }
    baselines, compositions, families, thresholds = {}, {}, {}, {}
    provisional, member_duration, member_physical = {}, {}, {}
    for member, (reference, years, patterns) in prepared.items():
        baselines[member], compositions[member], families[member] = assembled_member(member, reference, years, patterns)
        thresholds[member] = duration_threshold(member, years)
        local_threshold = duration_threshold(member, years, section="R")
        provisional[member] = tuple(
            safeguard(c.samples, local_threshold, stage=AssessmentStage.PROVISIONAL)
            for c in baselines[member].candidate.classes
        )
        member_duration[member] = tuple(
            safeguard(c.samples, thresholds[member], stage=AssessmentStage.FINAL) for c in families[member].classes
        )
        member_physical[member] = tuple(final_assessment(s) for c in families[member].classes for s in c.samples)
        assert all(result.checks.finding is CheckFinding.PASS for result in member_duration[member])
        assert all(result.checks.finding is CheckFinding.PASS for result in member_physical[member])
    selection = external_selection(tuple(families.items()))
    selected = selection.accepted
    assert isinstance(selected, RequirementFamily)
    physical = tuple(ClassAssessment(c.design, final_assessment(s)) for c in selected.classes for s in c.samples)
    tests = []
    for member, threshold in thresholds.items():
        acceptance = synthetic_acceptance(threshold.product(UsePurpose.SIZING))
        for cls in selected.classes:
            first = cls.samples[0]
            prefix = tuple(
                replace(
                    first,
                    interval=Interval(
                        first.interval.start - timedelta(days=i), first.interval.start - timedelta(days=i - 1)
                    ),
                )
                for i in range(6, 0, -1)
            )
            tests.append(
                DurationTest(
                    "annual7-T100",
                    member,
                    cls.design,
                    threshold,
                    prefix,
                    "six explicit constant synthetic class precursor values; not wrapping an observed record",
                    acceptance,
                    WindowUncertaintySupport(
                        "exact synthetic enclosing singletons", "U9", "fixed values; no independence assumption"
                    ),
                    CandidateReferenceRelation(
                        first.provenance,
                        threshold.reference.identity,
                        "exact selected U requirement checked against retained member U synthetic reference",
                    ),
                    UsePurpose.SIZING,
                )
            )
    route_inputs = {member: natural_tier(baselines[member]) for member in families}
    constructions = tuple(
        MemberConstruction(
            member,
            BaselineSource(baselines[member], provenance(member), "U9-baseline-v1"),
            tuple(
                ClassComposition(design, composition)
                for design, composition in zip(
                    (c.design for c in families[member].classes for _ in c.samples), compositions[member], strict=True
                )
            ),
            route=NaturalRouteInputs(location("R"), route_inputs[member][0], (route_inputs[member][1],)),
        )
        for member in families
    )
    member_physical_inputs = tuple(
        MemberPhysical(member, ClassAssessment(design, result))
        for member, family in families.items()
        for design, result in zip(
            (c.design for c in family.classes for _ in c.samples), member_physical[member], strict=True
        )
    )
    member_tests = tuple(
        DurationTest(
            "annual7-T100",
            member,
            cls.design,
            result.threshold,
            tuple(s for s in result.windows.windows[0].contributors if s.interval.end <= TARGET.interval.start),
            result.windows.predecessor_basis,
            result.scientific_assessment,
            result.windows.uncertainty_support,
            result.reference_relation,
            UsePurpose.SIZING,
        )
        for member, family in families.items()
        for cls, result in zip(family.classes, member_duration[member], strict=True)
    )
    final = finalize_regime(
        selection,
        EcologicalRegimeMethod.BASELINE,
        tuple(FinalCondition),
        physical,
        duration_tests=tuple(tests),
        expected_duration_tests=tuple((member, "annual7-T100") for member in thresholds),
        version="U9-final-v1",
        constructions=constructions,
        member_physical=member_physical_inputs,
        member_duration_tests=member_tests,
        provenance=provenance("selected"),
        provisional=tuple(result for results in provisional.values() for result in results),
    )
    assert final.requirement is not None and final.floor is not None
    issued = tuple(issue_and_assess(sample) for sample in final.requirement.samples(DesignClass.DRY))
    return ChainResult(
        prepared,
        baselines,
        compositions,
        families,
        thresholds,
        provisional,
        member_duration,
        member_physical,
        selection,
        final,
        issued,
    )


@dataclass(frozen=True)
class PotentialFloorExample:
    """Potential sizing results and complete quality-adjusted direct floors."""

    sources: tuple[PotentialFloorResult, ...]
    final: FinalFloors


def potential_study(flow, interval, source, candidate):
    """Selected constant potential flow → evaluated depth, velocity and daily-change conditions."""
    from fishy.hydraulics import (
        CriterionApplicability,
        HydraulicTransition,
        RateBound,
        RateCriterion,
        TransitionCoverage,
        assess_discrete_rate,
    )
    from fishy.study_requirements import StudyCondition

    scope = StudyScope(
        candidate, location("R"), interval, SCENARIO, source.reference_member, "potential-sizing", "all-year"
    )
    evidence = accepted_evidence(
        EvidenceScope(candidate, "U9-reach", source.reference_member, interval, "potential-sizing"), source
    )
    metadata = HydraulicRelationEvidence(
        "potential-depth-velocity-v1",
        "stipulated artificial channel geometry",
        "fixed supported boundary",
        "0<=Q<=12m3/s",
        "linear synthetic relation",
        "fixed singleton response",
        "hypothetical potential sizing only",
        RelationDomain.SUPPORTED,
    )
    criteria, relations, states = [], [], []
    for variable, units, divisor, lower, upper, hydraulic_variable in (
        (StudyVariable.DEPTH, "m", 3, Fraction(1), Fraction(4), HydraulicVariable.DEPTH),
        (StudyVariable.VELOCITY, "m/s", 6, Fraction(1, 2), Fraction(2), HydraulicVariable.SECTION_MEAN_VELOCITY),
    ):
        response = ResponseVariable(variable, units, "synthetic bed/direction datum", "section mean")
        criteria.append(
            StudyCriterion(
                variable.value,
                response,
                StateBounds(lower, upper),
                HydraulicComparison.INCLUSIVE,
                HydraulicComparison.INCLUSIVE,
                "explicit hypothetical potential criterion",
            )
        )
        relations.append(
            FlowResponseRelation(
                scope,
                response,
                (
                    ResponsePoint(Flow(0), StateBounds(Fraction(0), Fraction(0))),
                    ResponsePoint(Flow(12), StateBounds(Fraction(12, divisor), Fraction(12, divisor))),
                ),
                Interpolation.LINEAR,
                "stipulated geometry",
                metadata,
                evidence,
            )
        )
        hs = HydraulicScope(
            variable.value,
            location("R"),
            "artificial channel section mean",
            candidate,
            SCENARIO,
            hydraulic_variable,
            interval,
            "synthetic bed/direction datum",
            TemporalSupport.DAILY_MEANS,
        )
        ev = accepted_evidence(
            EvidenceScope(candidate, "U9-reach", source.reference_member, interval, variable.value), source
        )
        value = flow.value / divisor
        states.append(
            assess_state_range(
                StateCriterion(
                    hs,
                    "synthetic potential criterion",
                    CriterionStatus.HYPOTHETICAL,
                    StateLimit(BoundState.SUPPLIED, lower),
                    StateLimit(BoundState.SUPPLIED, upper),
                ),
                HydraulicState(hs, StateBounds(value, value), ev, relation=metadata),
            )
        )
    hs = HydraulicScope(
        "ramping",
        location("R"),
        "daily mean discharge transition",
        candidate,
        SCENARIO,
        HydraulicVariable.RELEASE_DISCHARGE,
        interval,
        "constant candidate plus explicitly supplied identical precursor",
        TemporalSupport.DAILY_MEANS,
    )
    ev = accepted_evidence(EvidenceScope(candidate, "U9-reach", source.reference_member, interval, "ramping"), source)
    zero = RateBound(BoundState.SUPPLIED, Fraction(0))
    ramp = assess_discrete_rate(
        RateCriterion(
            hs,
            "hypothetical no-change criterion",
            CriterionStatus.HYPOTHETICAL,
            zero,
            zero,
            CriterionApplicability.APPLICABLE,
        ),
        HydraulicTransition(
            hs,
            StateBounds(flow.value, flow.value),
            StateBounds(flow.value, flow.value),
            TransitionCoverage.ADJACENT,
            ev,
        ),
    )
    condition = StudyCondition(
        scope,
        "ramping",
        "daily mean flow change",
        "m3/s/hour",
        "complete constant candidate year",
        "hypothetical daily change0",
        "computed identical adjacent means; explicit constant precursor",
        ramp.check.finding,
        evidence,
    )
    selected = StudySelection(
        scope,
        flow,
        "supplied constant synthetic schedule",
        "joint potential depth and velocity",
        evidence,
        tuple(criteria),
        ("ramping",),
        (condition,),
    )
    return selected, tuple(relations), tuple(states), ramp


def floor_only_example(calendar=TARGET):
    """Actual potential sizing × daily active quality → complete365-day final direct floor only."""
    from datetime import date

    from fishy.floor_construction import FloorComponent, FloorConstruction, PotentialFloorSource
    from fishy.potential_requirements import Applicability, PotentialStudy, size_potential_floor
    from fishy.requirement_checks import FinalCondition, assess_requirement, sample_subject
    from fishy.requirement_composition import compose_requirement
    from fishy.requirement_family import (
        FamilyBasis,
        FloorSeries,
        ReconstructionNeed,
        RequirementMember,
        SelectionSpecification,
        assess_selected_family,
        candidate_scope,
    )
    from fishy.requirement_finalization import FloorMemberAssessment, finalize_floors
    from fishy.spatial import DesignationState, Eligibility, Origin, PreparedClassification, UseCategory
    from fishy.study_requirements import StudyNeed

    source = replace(provenance("potential"), reference_kind=ReferenceKind.MANAGED)
    classification = PreparedClassification(
        Origin.ARTIFICIAL,
        DesignationState.NONE,
        Eligibility.NOT_APPLICABLE,
        UseCategory.AGRICULTURE_IRRIGATION,
        ("synthetic canal",),
        "explicit constructed-origin scenario",
        "v1",
    )
    missing = PotentialStudy(Applicability.UNRESOLVED, "habitat study retained as pending", None, ())
    review = StudyNeed("remaining habitat study and official decisions", "hypothetical review owner", date(2027, 1, 1))
    sources, flows, checks, components = [], [], [], []
    required = (FinalCondition.QUALITY, FinalCondition.HYDRAULICS, FinalCondition.STUDY)
    for base in samples(calendar, 3, "potential", "R"):
        selected, relations, _, _ = potential_study(
            base.value, base.interval, source, "potential-base3:" + base.interval.start.isoformat()
        )
        hydraulic_study = PotentialStudy(
            Applicability.APPLICABLE, "stipulated accepted joint depth/velocity route", selected, relations
        )
        potential_source = PotentialFloorSource(selected.scope, classification, missing, hydraulic_study, None, review)
        potential = size_potential_floor(selected.scope, classification, missing, hydraulic_study, None, review)
        assert potential.floor is not None
        sources.append(potential)
        q = quality(
            potential.floor, base.interval, "potential", route=QualityRoute.FLOOR_ONLY, source_provenance=source
        )
        composition = compose_requirement(replace(base, provenance=source), source, quality=q)
        components.append(FloorComponent(potential_source, composition))
        sample = composition.candidate
        assert sample is not None
        flows.append(sample)
        selected, relations, states, ramp = potential_study(
            sample.value, sample.interval, source, sample_subject(sample)
        )
        checks.append(
            assess_requirement(
                sample,
                required,
                quality=q,
                hydraulic_required=(*(state.criterion.scope for state in states), ramp.criterion.scope),
                hydraulic_components=(*states, ramp),
                study_selection=selected,
                study_relations=relations,
            )
        )
    basis = FamilyBasis(
        location("R"),
        calendar.interval,
        SCENARIO,
        "potential-floor",
        "v1",
        "U9-hypothetical-quality-v1",
        source.reference_kind,
    )
    series = FloorSeries(basis, tuple(flows))
    member = RequirementMember(
        "potential",
        "supported hypothetical joint depth/velocity sizing",
        series,
        accepted_evidence(candidate_scope(series), source),
        "artificial route needs no natural reconstruction",
    )
    selection = assess_selected_family(
        (member,),
        series,
        SelectionSpecification(
            ("potential",),
            (),
            Fraction(1, 5),
            ReconstructionNeed.NOT_REQUIRED,
            "actual potential sizing plus active quality; no baseline gate",
        ),
    )
    return PotentialFloorExample(
        tuple(sources),
        finalize_floors(
            selection,
            required,
            tuple(checks),
            version="U9-potential-v1",
            constructions=(FloorConstruction("potential", tuple(components)),),
            member_physical=tuple(FloorMemberAssessment("potential", assessment) for assessment in checks),
        ),
    )


def main():
    """Run one supported scenario, then show floor-only, missing-evidence and independent-duty paths."""
    result = run_chain()
    final = result.final
    print(
        "Synthetic selected U classes m3/s:",
        {c.design.value: float(c.samples[0].value.value) for c in final.requirement.classes},
    )
    print("Selected natural routes:", {c.member.identifier: c.route.selected.value for c in final.constructions})
    print("Whole-family spread:", float(result.selection.maximum_spread))
    print("Final floor m3/s:", float(final.floor.sample.value.value))
    issue, delivery = result.issued[0]
    print(
        "Obligation / ecological deficit / raw shortfall m3/s:",
        float(issue.obligation.sample.value.value),
        float(issue.ecological_deficit.value),
        float(delivery.raw_shortfall.value),
    )
    print("Final checks:", final.checks.finding.value, "; all365 windows/class/member assessed")
    floor = floor_only_example()
    print(
        "Floor-only fallback m3/s:",
        float(floor.final.floors[0].sample.value.value),
        "; no regime or new delivery obligation",
    )
    from fishy.requirement_checks import FinalCondition, assess_requirement

    missing = assess_requirement(final.requirement.classes[0].samples[0], tuple(FinalCondition))
    print("Missing physical evidence:", missing.checks.finding.value)
    print("Independent sanitary duty shortfall m3:", float(independent_duty().known_shortfall_volume.value))
    print(
        "All acceptance and physical support are stipulated synthetic assumptions; not adopted policy or basin validation."
    )
    return result


if __name__ == "__main__":
    main()
