"""alternative_requirements : AcceptedDirectReferences × LocalPhysics → FinalRegime | FinalFloors.

Complete synthetic calendars exercise top study, qualified transfer and direct floors.
Imported natural hydrographs are stipulated direct reference products, not altered
observations needing reconstruction. No national policy or basin validation is claimed.
"""

from dataclasses import dataclass, replace
from datetime import date
from fractions import Fraction

from examples.requirement_chain import accepted_evidence
from examples.study_requirements import NATURAL
from fishy.design_conditions import DesignClass
from fishy.evidence import Check, CheckFinding, EvidenceScope
from fishy.hydraulics import Comparison, HydraulicRelationEvidence, RelationDomain, StateBounds
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
from fishy.natural_baseline import EcologicalRegimeMethod, baseline_family
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
from fishy.requirement_checks import FinalCondition, assess_requirement, sample_subject
from fishy.requirement_composition import compose_requirement
from fishy.requirement_construction import (
    BaselineSource,
    ClassComposition,
    ClassStudy,
    MemberConstruction,
    NaturalRouteInputs,
    StudySource,
)
from fishy.requirement_family import (
    ClassRequirement,
    FamilyBasis,
    FamilySelection,
    FloorSeries,
    ReconstructionNeed,
    RequirementFamily,
    RequirementMember,
    SelectionSpecification,
    assess_selected_family,
    candidate_scope,
)
from fishy.requirement_finalization import (
    ClassAssessment,
    FloorMemberAssessment,
    MemberPhysical,
    finalize_floors,
    finalize_regime,
)
from fishy.study_requirements import (
    FlowResponseRelation,
    HighFlowTrigger,
    Interpolation,
    NaturalStudyComponent,
    ResponsePoint,
    ResponseVariable,
    StudyCondition,
    StudyCriterion,
    StudyNeed,
    StudyScope,
    StudySelection,
    StudyVariable,
    TopTierEligibility,
)


def local_quality(sample, *, route=QualityRoute.REGIME, background_mg_l=6):
    """Exact local daily base × uncontrollable conservative load → supported active quality."""
    p, loc, interval = sample.provenance, sample.location, sample.interval
    chemical = ChemicalIdentity(
        "synthetic salt", "conservative solute", "salt mass", "dissolved", ChemicalBehavior.CONSERVATIVE
    )
    concentration = Fraction(background_mg_l, 1000)
    boundary = FixedBoundary(
        loc,
        interval,
        Flow(1),
        (MixingConstituent(chemical, LoadRate(concentration), QualityValue(Fraction(0), "kg/m3")),),
        BoundarySupport("fixed complete conservative mixing; zero storage; no omitted loads"),
        p,
    )
    targets = (
        QualityTarget(
            "local-salt",
            chemical,
            QualityComparison.LE,
            QualityValue(Fraction(1, 1000), "kg/m3"),
            "daily interval",
            "hypothetical local limit",
        ),
    )
    missing = ActivationCondition(EvidenceState.MISSING, "national approvals not claimed")
    activation = QualityActivation(
        p.scenario,
        route,
        ActivationMode.HYPOTHETICAL,
        ActivationConditions(missing, missing, missing, missing, missing),
        "explicit synthetic activation",
    )
    section = loc.section.identifier
    controls = SourceControlEvidence(
        p.scenario,
        section,
        interval,
        ControlState.EXHAUSTED,
        (("background", ResidualSourceKind.UNCONTROLLABLE_DIFFUSE),),
        "no omitted controllable loads",
    )
    empty = Inventory(Volume(0), Mass(0))
    water = Inventory(Volume(interval.seconds), Mass(concentration * interval.seconds))
    ledger = assess_load_accounts(
        (LoadAccount(section, chemical, interval, p.scenario, empty, empty, p),),
        (AccountTransfer("background", None, section, water), AccountTransfer("outflow", section, None, water)),
    )
    return apply_quality_component(
        sample.value,
        boundary,
        targets,
        activation,
        controls,
        (ledger,),
        BackgroundAccountMapping(("background",), "all and only background", loc),
    )


def study_component(sample, *, pulse=False):
    """Selected daily flow → evaluated habitat/depth curves and attributable specialist conditions."""
    p = sample.provenance
    scope = StudyScope(
        sample_subject(sample),
        sample.location,
        sample.interval,
        p.scenario,
        p.reference_member,
        "sizing",
        "June pulse" if pulse else "annual habitat",
    )
    evidence = accepted_evidence(
        EvidenceScope(
            scope.candidate, sample.location.reach.identifier, p.reference_member, sample.interval, scope.purpose
        ),
        p,
    )
    metadata = HydraulicRelationEvidence(
        "direct-top-v1",
        "synthetic surveyed section",
        "fixed downstream level",
        "0<=Q<=30 m3/s",
        "linear synthetic relation",
        "explicit exact singleton support",
        "hypothetical only",
        RelationDomain.SUPPORTED,
    )
    habitat = ResponseVariable(StudyVariable.HABITAT, "m2", "synthetic bed", "wetted habitat")
    depth = ResponseVariable(StudyVariable.DEPTH, "m", "synthetic bed", "section mean depth")
    relations = tuple(
        FlowResponseRelation(
            scope,
            variable,
            (
                ResponsePoint(Flow(0), StateBounds(Fraction(0), Fraction(0))),
                ResponsePoint(Flow(30), StateBounds(Fraction(high), Fraction(high))),
            ),
            Interpolation.LINEAR,
            "synthetic direct study",
            metadata,
            evidence,
        )
        for variable, high in ((habitat, 300), (depth, 3))
    )
    criteria = tuple(
        StudyCriterion(
            variable.variable.value,
            variable,
            StateBounds(Fraction(low), Fraction(high)),
            Comparison.INCLUSIVE,
            Comparison.INCLUSIVE,
            "explicit specialist selection",
        )
        for variable, low, high in ((habitat, 200 if pulse else 120, 300), (depth, 2 if pulse else Fraction(6, 5), 3))
    )
    names = ("sediment", "hydraulic", "flood_safety", "ramping") if pulse else ()
    conditions = tuple(
        StudyCondition(
            scope,
            name,
            "supplied synthetic specialist assessment",
            "m3/s",
            "named daily pulse and transitions",
            "explicit accepted pulse20 with previous/next12",
            "20 within accepted[20,25]; changes8 within accepted10 m3/s/day",
            CheckFinding.PASS,
            evidence,
        )
        for name in names
    )
    selection = StudySelection(
        scope,
        sample.value,
        "explicit ecologist selected point",
        "pulse timing or annual habitat",
        evidence,
        criteria,
        names,
        conditions,
    )
    return NaturalStudyComponent(
        "pulse" if pulse else "habitat", selection, relations, "pulse" if pulse else "seasonal"
    )


def single_selection(candidate):
    """Direct accepted input → fixed one-member selection; no reconstruction was performed."""
    first = candidate.samples[0] if isinstance(candidate, FloorSeries) else candidate.classes[0].samples[0]
    member = RequirementMember(
        first.provenance.reference_member,
        "direct imported natural reference; no altered-record reconstruction",
        candidate,
        accepted_evidence(candidate_scope(candidate), first.provenance),
        "one supplied direct reference; no independence or structural bracket claimed",
    )
    spec = SelectionSpecification(
        (member.identifier,),
        (),
        Fraction(1, 5),
        ReconstructionNeed.NOT_REQUIRED,
        "Direct accepted present-climate reference imports, not reconstructed altered observations",
    )
    return assess_selected_family((member,), candidate, spec)


def family_basis(sample, period, method):
    p = sample.provenance
    return FamilyBasis(
        sample.location,
        period,
        p.scenario,
        method,
        p.configuration_version,
        "fixed-hypothetical-local-quality-v1",
        p.reference_kind,
    )


@dataclass(frozen=True)
class RegimeInputs:
    selection: FamilySelection
    method: EcologicalRegimeMethod
    required: tuple[FinalCondition, ...]
    physical: tuple[ClassAssessment, ...]
    construction: MemberConstruction
    member_physical: tuple[MemberPhysical, ...]

    def finalize(self):
        assert isinstance(self.selection.supplied, RequirementFamily)
        first = self.selection.supplied.classes[0].samples[0]
        return finalize_regime(
            self.selection,
            self.method,
            self.required,
            self.physical,
            duration_tests=(),
            expected_duration_tests=(),
            version="alternative-final-v1",
            provenance=first.provenance,
            constructions=(self.construction,),
            member_physical=self.member_physical,
        )


def natural_route(source):
    """Exact source hydrology/studies × prepared natural classification → route inputs."""
    from fishy.natural_routing import (
        Availability,
        NaturalRoute,
        ScopedRequirement,
        TierEvidence,
        reconstruction_disclosure_scope,
    )

    if not isinstance(source, StudySource):
        return NaturalRouteInputs(source.recipient_natural[0].location, NATURAL, ())
    inputs = source.hydrology.result.inputs
    reference = inputs.patterns[0].magnitude.reference
    scope = reconstruction_disclosure_scope(reference)
    disclosure = ScopedRequirement("reconstruction_disclosure", scope, accepted_evidence(scope, reference.provenance))
    study = source.studies[0]
    tier = TierEvidence(
        NaturalRoute.TOP,
        inputs.patterns[0].location,
        "top-direct-route-v1",
        Availability.AVAILABLE,
        Availability.AVAILABLE,
        Check("priority", CheckFinding.PASS, ("explicit specified/resourced hypothetical priority reach",)),
        ("reconstruction_disclosure",),
        (),
        (disclosure,),
        study.components,
        "direct imported natural reference with explicit priority study",
        natural_patterns=inputs.patterns,
        recorded_minimum=inputs.recorded,
        required_study_components=study.required_components,
        study_trigger=source.trigger,
        study_need=source.need,
    )
    return NaturalRouteInputs(tier.location, source.classification, (tier,))


def assemble_regime(classes, period, method, source):
    """Actual pre-quality source family → complete local composition and final physical inputs."""
    required = (
        (FinalCondition.QUALITY, FinalCondition.STUDY)
        if method is EcologicalRegimeMethod.STUDY
        else (FinalCondition.QUALITY,)
    )
    compositions, final_classes, physical = [], [], []
    for item in classes:
        final_samples = []
        for base in item.samples:
            q = local_quality(base)
            result = compose_requirement(base, base.provenance, quality=q)
            assert result.candidate is not None
            sample = result.candidate
            final_samples.append(sample)
            compositions.append(ClassComposition(item.design, result))
            kwargs = {}
            if method is EcologicalRegimeMethod.STUDY:
                study = study_component(
                    sample, pulse=sample.interval.start.month == 6 and sample.interval.start.day == 1
                )
                kwargs = {"study_selection": study.study, "study_relations": study.relations}
            physical.append(ClassAssessment(item.design, assess_requirement(sample, required, quality=q, **kwargs)))
        final_classes.append(ClassRequirement(item.design, tuple(final_samples)))
    first = final_classes[0].samples[0]
    family = RequirementFamily(family_basis(first, period, method.value), tuple(final_classes))
    selection = single_selection(family)
    member = selection.members[0].identifier
    return RegimeInputs(
        selection,
        method,
        required,
        tuple(physical),
        MemberConstruction(member, source, tuple(compositions), route=natural_route(source)),
        tuple(MemberPhysical(member, p) for p in physical),
    )


def supported_top(*, dry_flow=12):
    """Accepted direct natural50=10 × habitat12/pulse20 → uncapped top family."""
    from examples.natural_baseline import PROVENANCE, accepted_family

    patterns, record = accepted_family(AccountingYear(2023, 1, 0))
    hydro = baseline_family(patterns, record, provenance=PROVENANCE, profile_version="top-direct-hydrology-v1")
    assert hydro.candidate is not None
    classes, studies = [], []
    for item in hydro.candidate.classes:
        daily = []
        for original in item.samples:
            pulse = original.interval.start.month == 6 and original.interval.start.day == 1
            sample = replace(original, value=Flow(20 if pulse else dry_flow if item.design is DesignClass.DRY else 12))
            component = study_component(sample, pulse=pulse)
            studies.append(ClassStudy(item.design, (component.name,), (component,)))
            daily.append(sample)
        classes.append(ClassRequirement(item.design, tuple(daily)))
    source = StudySource(
        BaselineSource(hydro, PROVENANCE, "top-direct-hydrology-v1"),
        NATURAL,
        TopTierEligibility.PRIORITY,
        HighFlowTrigger.OTHER_SUPPORTED,
        StudyNeed("specified June high-flow need and habitat", "hypothetical ecologist", date(2027, 1, 1)),
        tuple(studies),
    )
    return assemble_regime(tuple(classes), hydro.candidate.calendar.interval, EcologicalRegimeMethod.STUDY, source)


def supported_transfer():
    """Qualified donor ecological2/4 over natural4/8 × recipient6/10 → local quality6."""
    from examples.ecological_transfer import synthetic_transfer

    source = synthetic_transfer()
    assert source.candidate is not None
    return assemble_regime(
        source.candidate.classes, source.candidate.calendar.interval, EcologicalRegimeMethod.TRANSFER, source
    )


def finalize_direct_floors(samples, method, source):
    """Actual floor-only sizing samples → daily active-quality floors, without regime/obligation."""
    from fishy.floor_construction import FloorComponent, FloorConstruction
    from fishy.time import Interval

    compositions = tuple(
        compose_requirement(s, s.provenance, quality=local_quality(s, route=QualityRoute.FLOOR_ONLY)) for s in samples
    )
    for composition in compositions:
        assert composition.candidate is not None
    finals = tuple(c.candidate for c in compositions if c.candidate is not None)
    first = finals[0]
    series = FloorSeries(family_basis(first, Interval(first.interval.start, finals[-1].interval.end), method), finals)
    selection = single_selection(series)
    required = (FinalCondition.QUALITY,)
    physical = tuple(
        assess_requirement(s, required, quality=c.quality) for s, c in zip(finals, compositions, strict=True)
    )
    construction = FloorConstruction(
        selection.members[0].identifier, tuple(FloorComponent(source, composition) for composition in compositions)
    )
    return finalize_floors(
        selection,
        required,
        physical,
        version="direct-final-v1",
        constructions=(construction,),
        member_physical=tuple(FloorMemberAssessment(construction.member, item) for item in physical),
    )


def supported_presumptive():
    from examples.ecological_transfer import synthetic_inputs
    from fishy.presumptive_floor import (
        PresumptiveProfile,
        SeasonalFraction,
        presumptive_floor,
        presumptive_reference_identity,
    )

    reference = synthetic_inputs(AccountingYear(2023, 1, 0))[2][0]
    profile = PresumptiveProfile(
        "direct-presumptive-v1",
        "direct imported recipient P25 reference",
        presumptive_reference_identity(reference),
        (SeasonalFraction("annual", 0, 365, Fraction(1, 5)),),
        "hypothetical supplied fraction, not national policy",
        "stipulated synthetic reference support",
    )
    base = presumptive_floor(reference, profile)
    from fishy.floor_construction import PresumptiveFloorSource

    source = PresumptiveFloorSource(base, NaturalRouteInputs(reference.location, NATURAL, ()))
    return base, finalize_direct_floors(base.samples, "presumptive_floor", source)


def main():
    """Print actual-versus-expected supported alternative results at exact precision."""
    for label, inputs, expected in (("top", supported_top(), Flow(12)), ("transfer", supported_transfer(), Flow(6))):
        result = inputs.finalize()
        assert result.floor is not None
        print(
            f"{label}: checks={result.checks.finding.value}; floor={result.floor.sample.value.value}; expected={expected.value}; duration-tests={len(result.duration)}"
        )
    _, result = supported_presumptive()
    print(
        f"presumptive: checks={result.checks.finding.value}; final-floor={result.floors[0].sample.value.value}; expected=6; days={len(result.floors)}; no regime/obligation"
    )


if __name__ == "__main__":
    main()
