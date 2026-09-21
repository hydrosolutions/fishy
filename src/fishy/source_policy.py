"""source_policy_checks : (BaselineSource | StudySource | TransferResult)* → CheckSummary.

floor_policy_checks : DirectFloorSource* → CheckSummary.

Compare actual policy components, not scientific observations or reference identity.
A missing required component is unknown; it cannot hide a known policy mismatch.
"""

from dataclasses import dataclass
from hashlib import sha256

from fishy.annual_statistics import ImportedDerivation
from fishy.daily_patterns import DailyPattern, PatternMethod
from fishy.ecological_transfer import TransferResult
from fishy.evidence import Check, CheckFinding, CheckSummary
from fishy.floor_construction import DirectFloorSource, EntryFloorSource, PresumptiveFloorSource, assess_floor_source
from fishy.potential_requirements import PotentialFloorResult, PotentialRoute
from fishy.requirement_construction import BaselineSource, StudySource
from fishy.scientific_acceptance import ScientificAssessment, ScientificCriterion
from fishy.study_requirements import StudySelection


@dataclass(frozen=True)
class PolicyComponent:
    name: str
    fingerprint: str | None


def _known(name: str, policy: object) -> PolicyComponent:
    return PolicyComponent(name, sha256(repr(policy).encode()).hexdigest())


def _criterion(c: ScientificCriterion) -> tuple[object, ...]:
    return (
        c.criterion_id,
        c.role,
        c.formula,
        c.domain,
        c.units,
        c.measure,
        c.aggregation,
        c.comparison,
        float(c.limit) + 0.0,
        c.justification,
        c.requirement,
    )


def _scientific(name: str, assessment: ScientificAssessment | None) -> PolicyComponent:
    if assessment is None:
        return PolicyComponent(name, None)
    record = assessment.record
    return _known(
        name,
        (
            record.profile_version,
            record.permitted_uses,
            tuple(sorted((_criterion(c) for c in record.criteria), key=repr)),
        ),
    )


def _derivation(derivation: ImportedDerivation | None) -> tuple[object, ...] | None:
    if derivation is None:
        return None
    return (
        derivation.equation,
        derivation.parameter_estimation,
        derivation.extrapolation,
        derivation.uncertainty_method,
        derivation.covariates,
        derivation.evaluation,
    )


def _patterns(prefix: str, patterns: tuple[DailyPattern, ...]) -> tuple[PolicyComponent, ...]:
    components = [_known(prefix + ":targets", tuple(sorted(p.magnitude.target.value for p in patterns)))]
    for pattern in patterns:
        name = f"{prefix}:{pattern.magnitude.target.value}"
        components.append(
            _known(
                name + ":method",
                (
                    pattern.method,
                    pattern.magnitude.estimator,
                    pattern.magnitude.profile_version,
                    _derivation(pattern.magnitude.derivation),
                    _derivation(pattern.imported_derivation),
                    pattern.requested_use,
                    pattern.purpose,
                ),
            )
        )
        components.extend(
            (
                _scientific(name + ":magnitude_acceptance", pattern.magnitude_assessment),
                _scientific(name + ":shape_acceptance", pattern.shape_assessment),
            )
        )
        profile = pattern.profile
        if profile is None:
            components.append(
                _known(name + ":profile", "imported: no computed profile")
                if pattern.method is PatternMethod.IMPORTED
                else PolicyComponent(name + ":profile", None)
            )
        else:
            components.append(
                _known(
                    name + ":profile",
                    (
                        profile.version,
                        profile.target,
                        profile.band,
                        profile.scenario,
                        profile.climate_basis,
                        profile.estimator,
                        tuple((d.location, d.descriptors) for d in profile.donors),
                        profile.minimum_source_years,
                        profile.minimum_climate_clusters,
                        profile.alignment,
                        profile.acceptance_profile,
                        profile.reference_period,
                    ),
                )
            )
    return tuple(components)


def _baseline(source: BaselineSource) -> tuple[PolicyComponent, ...]:
    inputs = source.result.inputs
    alpha, winter, spawning = inputs.alpha, inputs.winter, inputs.spawning
    return (
        _known("baseline:version", source.profile_version),
        _known(
            "baseline:alpha",
            "standard" if alpha is None else (tuple(sorted(alpha.values)), alpha.qualification, alpha.derivation),
        ),
        _known(
            "baseline:winter",
            "inactive" if winter is None else (winter.regulation, winter.share, winter.adoption_basis),
        ),
        _known(
            "baseline:spawning",
            "inactive"
            if spawning is None
            else (
                spawning.coefficients,
                spawning.calendar,
                spawning.biological_timing,
                spawning.coefficient_provenance,
            ),
        ),
        *_patterns("baseline:patterns", inputs.patterns),
        _scientific("baseline:recorded_acceptance", None if inputs.recorded is None else inputs.recorded.assessment),
    )


def _study(selection: StudySelection) -> tuple[object, ...]:
    return (
        selection.scope.purpose,
        selection.scope.season,
        selection.selection_source,
        selection.objective,
        selection.criteria,
        selection.required_conditions,
        tuple((c.component, c.variable, c.units, c.domain, c.criterion) for c in selection.conditions),
        None if selection.holistic_assessment is None else selection.holistic_assessment.criterion,
    )


def source_policy_components(source: BaselineSource | StudySource | TransferResult) -> tuple[PolicyComponent, ...]:
    if isinstance(source, BaselineSource):
        return (_known("method", "baseline"), *_baseline(source))
    if isinstance(source, StudySource):
        return (
            _known("method", "study"),
            *_baseline(source.hydrology),
            _known("study:rules", (source.classification, source.eligibility, source.trigger, source.need)),
            _known(
                "study:criteria",
                tuple(
                    (c.design, c.required_components, tuple((s.name, s.kind, _study(s.study)) for s in c.components))
                    for c in source.studies
                ),
            ),
        )
    profile = source.profile
    return (
        _known("method", "transfer"),
        _known("transfer:donor", (source.donor.method, source.donor.profile_version)),
        *_patterns("transfer:donor_patterns", source.donor_natural),
        *_patterns("transfer:recipient_patterns", source.recipient_natural),
        PolicyComponent("transfer:profile", None)
        if profile is None
        else _known(
            "transfer:profile",
            (
                profile.version,
                profile.donor,
                profile.recipient,
                profile.choice_justification,
                tuple((q.aspect, _criterion(q.criterion)) for q in profile.qualification),
                profile.donor_uncertainty,
                profile.calendar_sensitivity,
            ),
        ),
        _known("transfer:register", source.register),
    )


def floor_policy_components(source: DirectFloorSource) -> tuple[PolicyComponent, ...]:
    if isinstance(source, EntryFloorSource):
        result = source.result
        product = result.statistic.product
        return (
            _known("method", "entry"),
            PolicyComponent("entry:curve", None) if result.curve is None else _known("entry:curve", result.curve),
            PolicyComponent("entry:screen", None) if result.screen is None else _known("entry:screen", result.screen),
            _scientific("entry:acceptance", result.statistic.assessment),
            _known(
                "entry:statistic",
                (
                    product.kind,
                    product.statistic_name,
                    product.units,
                    product.calendar,
                    product.resolution,
                    product.purpose,
                    product.target_probability,
                    product.duration_days,
                    product.low_flow_return_period,
                ),
            ),
        )
    if isinstance(source, PresumptiveFloorSource):
        profile = source.result.profile
        return (
            _known("method", "presumptive"),
            PolicyComponent("presumptive:profile", None)
            if profile is None
            else _known(
                "presumptive:profile",
                (
                    profile.version,
                    profile.reference_definition,
                    profile.seasons,
                    profile.adoption_or_scenario_basis,
                    profile.uncertainty,
                ),
            ),
        )
    components = [_known("method", "potential"), _known("potential:classification", source.classification)]
    for name, study in (("habitat", source.habitat), ("hydraulics", source.hydraulics)):
        components.append(_known("potential:" + name + ":applicability", study.applicability))
    result, _ = assess_floor_source(source)
    selected = result.selected_route if isinstance(result, PotentialFloorResult) else None
    components.append(
        PolicyComponent("potential:selected_route", None)
        if selected is None
        else _known("potential:selected_route", selected)
    )
    # Earlier unresolved routes remain in the source assessment. They are not
    # required policy components of the supported, ordered fallback route.
    chosen = (
        source.habitat
        if selected is PotentialRoute.HABITAT
        else source.hydraulics
        if selected is PotentialRoute.HYDRAULIC
        else None
    )
    if chosen is not None:
        components.append(
            PolicyComponent("potential:selected_criteria", None)
            if chosen.selection is None
            else _known("potential:selected_criteria", _study(chosen.selection))
        )
    if selected is PotentialRoute.CONVEYANCE:
        request = source.conveyance
        assert isinstance(result, PotentialFloorResult)
        route = next(r for r in result.routes if r.route is PotentialRoute.CONVEYANCE)
        conveyance = route.conveyance
        if request is None or conveyance is None:
            components.append(PolicyComponent("potential:conveyance", None))
        else:
            components.extend(
                (
                    _known("potential:conveyance:stopping", request.stopping),
                    PolicyComponent("potential:conveyance:capacity", None)
                    if request.capacity is None
                    else _known("potential:conveyance:capacity", request.capacity),
                    PolicyComponent("potential:conveyance:ramp", None)
                    if request.ramp is None
                    else _known(
                        "potential:conveyance:ramp",
                        (request.ramp.transition.seconds, request.ramp.rise, request.ramp.fall),
                    ),
                    _known(
                        "potential:conveyance:duties",
                        tuple(
                            sorted(
                                (
                                    (d.identifier, d.location, d.source, d.authentication, d.volume, d.capacity)
                                    for d in conveyance.selected_duties
                                ),
                                key=repr,
                            )
                        ),
                    ),
                )
            )
            relation = request.relation
            components.append(
                PolicyComponent("potential:conveyance:relation", None)
                if relation is None
                else _known(
                    "potential:conveyance:relation",
                    (
                        relation.location,
                        relation.storage_location,
                        relation.geometry_version,
                        relation.boundary_conditions,
                        relation.interpolation,
                        relation.uncertainty,
                    ),
                )
            )
    components.append(
        _known(
            "potential:conditions",
            tuple(
                (c.component, c.variable, c.units, c.domain, c.criterion)
                for c in (*source.additional_conditions, *source.active_quality)
            ),
        )
    )
    return tuple(components)


def _compare(policies: tuple[tuple[PolicyComponent, ...], ...]) -> CheckSummary:
    if not policies:
        return CheckSummary((Check("source_policy:coverage", CheckFinding.UNKNOWN, ("actual sources missing",)),))
    by_source = tuple({c.name: c.fingerprint for c in policy} for policy in policies)
    checks = []
    for name in sorted({c.name for policy in policies for c in policy}):
        present = {row[name] for row in by_source if name in row and row[name] is not None}
        missing = tuple(i for i, row in enumerate(by_source) if name not in row or row[name] is None)
        if len(present) > 1:
            checks.append(Check("source_policy:" + name, CheckFinding.FAIL, ("actual policy components differ",)))
        elif not missing:
            checks.append(Check("source_policy:" + name, CheckFinding.PASS))
        if missing:
            checks.append(
                Check(
                    "source_policy:" + name + ":coverage",
                    CheckFinding.UNKNOWN,
                    (f"required policy component missing from sources {missing}",),
                )
            )
    return CheckSummary(tuple(checks))


def source_policy_checks(sources: tuple[BaselineSource | StudySource | TransferResult, ...]) -> CheckSummary:
    return _compare(tuple(source_policy_components(source) for source in sources))


def floor_policy_checks(sources: tuple[DirectFloorSource, ...]) -> CheckSummary:
    return _compare(tuple(floor_policy_components(source) for source in sources))
