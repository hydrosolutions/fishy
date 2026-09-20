"""assess_safeguards : SafeguardSites × SiteStudies → AttributedResidualMinima.

GSchG (2025-08-01) Art. 31(2); FOEN Guide (2000), section 4.4.
Supplied total-flow requirements are site relationships, not invented hydraulic equations.
"""

from dataclasses import dataclass, replace
from enum import StrEnum
from hashlib import sha256

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    ProductionMethod,
    ScientificAdequacy,
    _text,
    permitted_use,
    warmup_restrictions,
)
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, interval_use
from fishy.quantities import Elevation, Flow
from fishy.spatial import Location


class Safeguard(StrEnum):
    WATER_QUALITY = "31(2)(a):surface_quality_existing_wastewater"
    DRINKING_RECHARGE = "31(2)(b):dependent_drinking_recharge"
    SOIL_WATER = "31(2)(b):agricultural_soil_water"
    RARE_HABITATS = "31(2)(c):rare_habitats_communities"
    FISH_PASSAGE = "31(2)(d):free_fish_passage_depth"
    SPAWNING_REARING = "31(2)(e):spawning_rearing_functions"


class FishFunction(StrEnum):
    SPAWNING_OR_REARING = "spawning_or_rearing"
    NEITHER = "neither_with_site_evidence"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SafeguardSite:
    """One affected control point and exact seasonal/event interval, not only the intake."""

    identifier: str
    starting_minimum: FlowSample
    q347: Flow
    elevation: Elevation
    fish_function: FishFunction
    inventory_source: str

    def __post_init__(self) -> None:
        _text(self.identifier, "site identifier")
        _text(self.inventory_source, "affected-point and fish-function inventory source")
        for value, kind in (
            (self.starting_minimum, FlowSample),
            (self.q347, Flow),
            (self.elevation, Elevation),
            (self.fish_function, FishFunction),
        ):
            if not isinstance(value, kind):
                raise TypeError("safeguard site requires typed inputs")

    def scope(self, safeguard: Safeguard) -> EvidenceScope:
        sample = self.starting_minimum
        subject = sha256(repr(self).encode()).hexdigest()
        return EvidenceScope(
            f"Swiss safeguard site:{self.identifier}:{subject}",
            sample.location.reach.identifier,
            sample.provenance.reference_member,
            sample.interval,
            f"Swiss safeguard {safeguard.value}",
        )


class SafeguardTreatment(StrEnum):
    FLOW_REQUIREMENT = "supported_total_flow_requirement"
    ALTERNATIVE = "selected_alternative_measure"
    PRESERVATION = "rare_habitat_preservation_measure"
    REPLACEMENT = "equivalent_rare_habitat_replacement"
    NOT_APPLICABLE = "supported_site_inapplicability"
    IMPOSSIBLE = "supported_requirement_cannot_be_met"


@dataclass(frozen=True)
class FlowNeed:
    """A supplied study's total lower bound within its accepted discharge domain.

    The relationship and acceptance criterion explain the inversion performed by
    the specialist; Fishy does not derive depth or quality from discharge.
    """

    total: Flow
    domain_lower: Flow
    domain_upper: Flow
    relationship: str
    acceptance_criterion: str

    def __post_init__(self) -> None:
        if any(not isinstance(x, Flow) for x in (self.total, self.domain_lower, self.domain_upper)):
            raise TypeError("flow need requires Flow quantities")
        if self.domain_lower.value > self.domain_upper.value:
            raise ValueError("relationship discharge domain is reversed")
        _text(self.relationship, "site relationship")
        _text(self.acceptance_criterion, "site acceptance criterion")


@dataclass(frozen=True)
class HabitatReplacement:
    equivalence: CheckFinding
    overriding_reasons_absent: CheckFinding
    replacement_possible: CheckFinding
    source: str

    def __post_init__(self) -> None:
        _text(self.source, "replacement qualification source")
        for state in (self.equivalence, self.overriding_reasons_absent, self.replacement_possible):
            if not isinstance(state, CheckFinding):
                raise TypeError("replacement qualifications require CheckFinding")


@dataclass(frozen=True)
class SafeguardStudy:
    site_identifier: str
    safeguard: Safeguard
    location: Location
    findings: EvidenceFindings
    treatment: SafeguardTreatment
    rationale: str
    flow_need: FlowNeed | None = None
    measure: str | None = None
    replacement: HabitatReplacement | None = None

    def __post_init__(self) -> None:
        _text(self.site_identifier, "site identifier")
        _text(self.rationale, "study rationale")
        for value, kind in (
            (self.safeguard, Safeguard),
            (self.location, Location),
            (self.findings, EvidenceFindings),
            (self.treatment, SafeguardTreatment),
        ):
            if not isinstance(value, kind):
                raise TypeError("safeguard study requires typed inputs")
        if self.treatment is SafeguardTreatment.FLOW_REQUIREMENT:
            if not isinstance(self.flow_need, FlowNeed):
                raise ValueError("flow treatment needs a supported total and relationship")
        elif self.flow_need is not None:
            raise ValueError("only flow treatment carries a flow requirement")
        if self.treatment in (
            SafeguardTreatment.ALTERNATIVE,
            SafeguardTreatment.PRESERVATION,
            SafeguardTreatment.REPLACEMENT,
        ):
            if self.measure is None:
                raise ValueError("alternative treatment must identify the selected protective measure")
            _text(self.measure, "selected protective measure")
        elif self.measure is not None:
            raise ValueError("measure belongs to alternative/replacement treatment")
        if self.treatment is SafeguardTreatment.PRESERVATION and self.safeguard is not Safeguard.RARE_HABITATS:
            raise ValueError("habitat preservation treatment belongs to rare habitats")
        if self.treatment is SafeguardTreatment.REPLACEMENT:
            if self.safeguard is not Safeguard.RARE_HABITATS or not isinstance(self.replacement, HabitatReplacement):
                raise ValueError("rare habitat replacement requires statutory qualifications")
        elif self.replacement is not None:
            raise ValueError("replacement qualifications belong to replacement treatment")
        if self.safeguard is Safeguard.RARE_HABITATS and self.treatment is SafeguardTreatment.ALTERNATIVE:
            raise ValueError("rare habitat measures require explicit qualified replacement or preservation treatment")


def safeguard_study_scope(
    site: SafeguardSite,
    safeguard: Safeguard,
    treatment: SafeguardTreatment,
    flow_need: FlowNeed | None = None,
    measure: str | None = None,
    replacement: HabitatReplacement | None = None,
) -> EvidenceScope:
    """Bind acceptance to the exact reviewed site, criterion, relationship and treatment.

    The digest is a versioned in-memory subject identity, not legal authentication.
    Replacing a requirement or physical/context revision needs new scoped findings.
    """
    scope = site.scope(safeguard)
    subject = sha256(repr((treatment, flow_need, measure, replacement)).encode()).hexdigest()
    return replace(scope, product=f"{scope.product}:study:{subject}")


@dataclass(frozen=True)
class SiteMinimum:
    site: SafeguardSite
    minimum: FlowSample
    studies: tuple[SafeguardStudy, ...]
    summary: CheckSummary
    measures: tuple[str, ...]
    initial_conditions: CheckSummary


class SafeguardUse(StrEnum):
    SCENARIO = "labelled_scenario"
    FINAL_SIZING = "final_sizing"


@dataclass(frozen=True)
class SafeguardAssessment:
    sites: tuple[SiteMinimum, ...]
    summary: CheckSummary
    use: SafeguardUse
    source: str = "GSchG 2025-08-01 Art.31(2); FOEN Guide 2000 section 4.4 pp.39-48"


def _spawning_applicability(site: SafeguardSite) -> CheckFinding:
    if site.q347.value > Flow(40, "l/s").value or site.elevation.metres >= 800:
        return CheckFinding.FAIL  # not applicable, not a failed ecological condition
    if site.fish_function is FishFunction.UNKNOWN:
        return CheckFinding.UNKNOWN
    return CheckFinding.PASS if site.fish_function is FishFunction.SPAWNING_OR_REARING else CheckFinding.FAIL


def _study_support(site: SafeguardSite, study: SafeguardStudy, use: SafeguardUse) -> Check:
    support = permitted_use(
        study.findings,
        safeguard_study_scope(
            site, study.safeguard, study.treatment, study.flow_need, study.measure, study.replacement
        ),
    )
    if support.finding is CheckFinding.FAIL:
        return support
    excluded = warmup_restrictions(study.findings.provenance, site.starting_minimum.interval)
    if excluded:
        return Check("permitted_use", CheckFinding.UNKNOWN, excluded)
    if (
        use is SafeguardUse.FINAL_SIZING
        and study.findings.scientific_adequacy is ScientificAdequacy.ACCEPTED_AS_INDICATIVE
    ):
        return Check("permitted_use", CheckFinding.UNKNOWN, ("indicative study does not support final sizing",))
    return support


def assess_safeguards(
    sites: tuple[SafeguardSite, ...], studies: tuple[SafeguardStudy, ...], *, use: SafeguardUse = SafeguardUse.SCENARIO
) -> SafeguardAssessment:
    """Compute supported same-water lower bounds and retain every unassessed safeguard.

    The caller declares the complete affected-point inventory. Separate exact
    intervals represent seasonal and event needs. No requirement transfers to
    another point; intake translation belongs to a supported routing relationship.
    Numerical minima can remain available while scientific coverage is incomplete.
    """
    if not isinstance(use, SafeguardUse):
        raise TypeError("safeguard use requires SafeguardUse")
    if not isinstance(sites, tuple) or not isinstance(studies, tuple):
        raise TypeError("sites and studies must be immutable tuples")
    if any(not isinstance(site, SafeguardSite) for site in sites) or any(
        not isinstance(s, SafeguardStudy) for s in studies
    ):
        raise TypeError("typed safeguard sites and studies required")
    if not sites:
        return SafeguardAssessment(
            (),
            CheckSummary((Check("affected_points", CheckFinding.UNKNOWN, ("affected-point inventory absent",)),)),
            use,
        )
    ids = [site.identifier for site in sites]
    if len(set(ids)) != len(ids):
        raise ValueError("each point/interval must have a unique inventory identifier")
    physical_keys = [(site.starting_minimum.location, site.starting_minimum.interval) for site in sites]
    if len(set(physical_keys)) != len(physical_keys):
        raise ValueError("duplicate physical point and interval in safeguard inventory")
    first = sites[0].starting_minimum.provenance
    for site in sites:
        if any(
            getattr(site.starting_minimum.provenance, key) != getattr(first, key)
            for key in ("scenario", "reference_member", "reference_kind", "data_version", "configuration_version")
        ):
            raise ValueError("affected points have incompatible scenario/reference identity")
    keys = [(s.site_identifier, s.safeguard) for s in studies]
    if len(set(keys)) != len(keys) or any(key[0] not in ids for key in keys):
        raise ValueError("duplicate or undeclared safeguard study")
    by_key = dict(zip(keys, studies, strict=True))
    results = []
    for site in sites:
        sample = site.starting_minimum
        base_supported = (
            sample.presence is Presence.PRESENT
            and sample.coverage is Coverage.COMPLETE
            and interval_use(sample) is IntervalUse.ELIGIBLE
            and sample.value is not None
        )
        checks = [
            Check(
                f"{site.identifier}:starting_minimum",
                CheckFinding.PASS if base_supported else CheckFinding.UNKNOWN,
                ("attributable starting minimum" if base_supported else "starting minimum unsupported",),
            )
        ]
        totals = [sample.value.value] if base_supported and sample.value is not None else []
        selected = []
        measures = []
        initial_checks = []
        for safeguard in Safeguard:
            key = f"{site.identifier}:{safeguard.value}"
            applicability = (
                _spawning_applicability(site) if safeguard is Safeguard.SPAWNING_REARING else CheckFinding.PASS
            )
            if applicability is CheckFinding.FAIL:
                initial_checks.append(Check(key, CheckFinding.PASS, ("statutory spawning condition not applicable",)))
                checks.append(Check(key, CheckFinding.PASS, ("31(2)(e) not applicable at this affected point",)))
                continue
            study = by_key.get((site.identifier, safeguard))
            if study is None:
                initial_checks.append(Check(key, CheckFinding.UNKNOWN, ("initial condition unassessed",)))
                checks.append(Check(key, CheckFinding.UNKNOWN, ("required site study absent",)))
                continue
            selected.append(study)
            if study.location != sample.location or any(
                getattr(study.findings.provenance, field) != getattr(sample.provenance, field)
                for field in ("scenario", "reference_member", "reference_kind", "data_version", "configuration_version")
            ):
                raise ValueError(
                    "study location/scenario/reference/data/configuration identity differs from affected point"
                )
            support = _study_support(site, study, use)
            checks.append(Check(key + ":scientific_use", support.finding, support.reasons))
            initial_finding = CheckFinding.UNKNOWN
            if support.finding is CheckFinding.PASS and base_supported and sample.value is not None:
                if study.flow_need is not None:
                    need = study.flow_need
                    initial_finding = (
                        CheckFinding.PASS
                        if max(need.total.value, need.domain_lower.value)
                        <= sample.value.value
                        <= need.domain_upper.value
                        else CheckFinding.FAIL
                    )
                elif study.treatment is SafeguardTreatment.IMPOSSIBLE:
                    initial_finding = CheckFinding.FAIL
                elif study.treatment is SafeguardTreatment.NOT_APPLICABLE:
                    initial_finding = CheckFinding.PASS
            initial_checks.append(
                Check(key, initial_finding, ("initial minimum without newly selected protective measures",))
            )
            if applicability is CheckFinding.UNKNOWN:
                checks.append(
                    Check(key + ":applicability", CheckFinding.UNKNOWN, ("spawning/rearing function unknown",))
                )
            if support.finding is not CheckFinding.PASS:
                checks.append(Check(key, CheckFinding.UNKNOWN, ("no accepted site relationship for this use",)))
                continue
            finding = CheckFinding.PASS
            reasons = (study.rationale,)
            if study.treatment is SafeguardTreatment.IMPOSSIBLE:
                finding = CheckFinding.FAIL
            elif study.treatment is SafeguardTreatment.FLOW_REQUIREMENT:
                need = study.flow_need
                assert need is not None
                required = max(need.total.value, need.domain_lower.value)
                candidate = (
                    max(required, sample.value.value) if base_supported and sample.value is not None else required
                )
                if candidate > need.domain_upper.value:
                    finding = CheckFinding.FAIL
                    reasons += ("required flow outside supplied relationship domain",)
                elif applicability is CheckFinding.PASS:
                    totals.append(required)
            elif study.treatment is SafeguardTreatment.REPLACEMENT:
                replacement = study.replacement
                assert replacement is not None
                qualification = CheckSummary(
                    tuple(
                        Check(f"replacement:{i}", state)
                        for i, state in enumerate(
                            (
                                replacement.equivalence,
                                replacement.overriding_reasons_absent,
                                replacement.replacement_possible,
                            )
                        )
                    )
                )
                finding = qualification.finding
                reasons += (replacement.source,)
            elif study.treatment is SafeguardTreatment.NOT_APPLICABLE and safeguard is Safeguard.SPAWNING_REARING:
                finding = CheckFinding.FAIL if applicability is CheckFinding.PASS else CheckFinding.UNKNOWN
                reasons += ("site inventory establishes the statutory spawning/rearing condition",)
            checks.append(Check(key, finding, reasons))
            if finding is CheckFinding.PASS and study.measure is not None:
                measures.append(study.measure)
        # Recheck all supported relationship upper bounds after combining requirements.
        total = Flow(max(totals)) if base_supported and totals else None
        if total is not None:
            for study in selected:
                if study.flow_need is not None and _study_support(site, study, use).finding is CheckFinding.PASS:
                    checks.append(
                        Check(
                            f"{site.identifier}:{study.safeguard.value}:combined_domain",
                            CheckFinding.PASS
                            if total.value <= study.flow_need.domain_upper.value
                            else CheckFinding.FAIL,
                            ("combined total checked against supplied site relationship domain",),
                        )
                    )
        minimum = replace(
            sample,
            value=total,
            provenance=replace(sample.provenance, production_method=ProductionMethod.RECONSTRUCTED)
            if sample.provenance.production_method is ProductionMethod.OBSERVED
            else sample.provenance,
            presence=Presence.PRESENT if total is not None else Presence.UNSUPPORTED,
            uncertainty=None,
            reasons=sample.reasons + ("supported partial minimum; consult safeguard coverage",),
            components=(sample,),
        )
        results.append(
            SiteMinimum(
                site,
                minimum,
                tuple(selected),
                CheckSummary(tuple(checks)),
                tuple(measures),
                CheckSummary(tuple(initial_checks)),
            )
        )
    return SafeguardAssessment(
        tuple(results), CheckSummary(tuple(c for result in results for c in result.summary.checks)), use
    )


def assess_safeguard_candidate(assessment: SafeguardAssessment, candidates: tuple[FlowSample, ...]) -> CheckSummary:
    """Recheck the actual supplied site relationships at a later final total.

    A passing lower-bound assessment alone cannot establish a higher candidate:
    an upper relationship domain, event window or required alternative may bind.
    Every original site and exact interval remains required.
    """
    if not isinstance(assessment, SafeguardAssessment) or not isinstance(candidates, tuple):
        raise TypeError("candidate check needs SafeguardAssessment and immutable FlowSamples")
    if any(not isinstance(sample, FlowSample) for sample in candidates):
        raise TypeError("candidate quantities require FlowSample")
    # Derived summaries are convenient outputs, not reusable proof. Recompute the
    # required checks and minima from the retained actual site/study inputs.
    assessment = assess_safeguards(
        tuple(row.site for row in assessment.sites),
        tuple(study for row in assessment.sites for study in row.studies),
        use=assessment.use,
    )
    required = {
        (row.site.starting_minimum.location, row.site.starting_minimum.interval): row for row in assessment.sites
    }
    supplied = {(sample.location, sample.interval): sample for sample in candidates}
    if len(supplied) != len(candidates) or set(supplied) - set(required):
        raise ValueError("duplicate or undeclared candidate site/interval")
    checks = [replace(check, check_id="preceding:" + check.check_id) for check in assessment.summary.checks]
    for key, row in required.items():
        candidate = supplied.get(key)
        prefix = row.site.identifier + ":candidate"
        if candidate is None:
            checks.append(Check(prefix, CheckFinding.UNKNOWN, ("required final site/interval missing",)))
            continue
        if any(
            getattr(candidate.provenance, field) != getattr(row.minimum.provenance, field)
            for field in ("scenario", "reference_member", "reference_kind", "data_version", "configuration_version")
        ):
            raise ValueError("candidate scenario/reference/data/configuration identity mismatch")
        available = (
            candidate.presence is Presence.PRESENT
            and candidate.coverage is Coverage.COMPLETE
            and interval_use(candidate) is IntervalUse.ELIGIBLE
            and candidate.value is not None
        )
        checks.append(
            Check(
                prefix + ":support",
                CheckFinding.PASS if available else CheckFinding.UNKNOWN,
                ("candidate temporal and quantity support",),
            )
        )
        if not available or candidate.value is None:
            continue
        if row.minimum.value is not None:
            checks.append(
                Check(
                    prefix + ":minimum",
                    CheckFinding.PASS if candidate.value.value >= row.minimum.value.value else CheckFinding.FAIL,
                    ("candidate must retain the applicable supported minimum",),
                )
            )
        for study in row.studies:
            support = _study_support(row.site, study, assessment.use)
            if study.flow_need is not None and support.finding is CheckFinding.PASS:
                need = study.flow_need
                value = candidate.value.value
                checks.append(
                    Check(
                        prefix + ":" + study.safeguard.value,
                        CheckFinding.PASS
                        if max(need.total.value, need.domain_lower.value) <= value <= need.domain_upper.value
                        else CheckFinding.FAIL,
                        (
                            need.relationship,
                            need.acceptance_criterion,
                            "final total rechecked in original supplied site relationship",
                        ),
                    )
                )
    return CheckSummary(tuple(checks))
