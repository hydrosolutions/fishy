"""Public scientific-use acceptance: supplied study settings are synthetic, not policy."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from fishy.evidence import (
    CheckFinding,
    Completeness,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    ScientificAdequacy,
    UseRestriction,
)
from fishy.quantities import Flow
from fishy.scientific_acceptance import (
    AcceptanceRecord,
    Aggregation,
    ClimateTreatment,
    Comparison,
    CriterionRole,
    DailyDerivation,
    DiagnosticObservation,
    ErrorMeasure,
    EvidenceItem,
    EvidenceRequirement,
    HydrologicalProduct,
    HydrologicalProductKind,
    RatingSupport,
    ScientificCriterion,
    ScientificEvidence,
    TemporalResolution,
    UsePurpose,
    ValidationEvidence,
    ValidationMethod,
    assess_scientific_use,
    compare_criterion,
    minimum_evidence,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def moment(day):
    return datetime(2026, 9, day, tzinfo=UTC)


def product(kind=HydrologicalProductKind.ANNUAL_MAGNITUDE):
    provenance = Provenance(
        "synthetic independent study",
        "scenario-a",
        "member-a",
        "test-version",
        "data-v1",
        "profile-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
    )
    scope = EvidenceScope(
        "annual P50; stationary imported estimate v1",
        "reach-a",
        "member-a",
        Interval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC)),
        "annual screen",
    )
    return HydrologicalProduct(
        scope,
        provenance,
        kind,
        "annual mean discharge at P50",
        "m3/s",
        "January-December UTC fixed 86400-second days",
        TemporalResolution.ANNUAL,
        UsePurpose.SCREENING,
        0.5,
        None,
        Location(Reach("reach-a", "v1", WaterBody("river", "v1")), CalculationSection("section", "v1"), "mapping-v1"),
        "present climate 2000-2019",
        "complete annual mean discharge observations",
        "full accepted reference content hash/version v1",
        "annual P50 estimate content hash/version v1",
        Flow(25),
    )


def criterion(**changes):
    c = ScientificCriterion(
        "timing",
        CriterionRole.MANDATORY,
        "candidate-reference",
        "synthetic season",
        "days",
        ErrorMeasure.ABSOLUTE,
        Aggregation.EACH_CASE,
        Comparison.AT_MOST,
        3.0,
        ("heldout-a", "heldout-b"),
        "Synthetic distinction of events separated by three days; not policy",
    )
    return replace(c, **changes)


def observation(case="heldout-a", candidate=3.0, reference=0.0, **changes):
    return DiagnosticObservation(
        "timing",
        case,
        candidate,
        reference,
        "days",
        "candidate-reference",
        "synthetic season",
        "synthetic independent holdout",
        **changes,
    )


def supplied(subject=None):
    subject = product() if subject is None else subject
    c = criterion()
    record = AcceptanceRecord(
        subject,
        "study-v1",
        "preparer-a",
        "reviewer-b",
        moment(1),
        moment(4),
        (c,),
        "rating and conditional sampling uncertainty; declared coverage 0.9",
        ("unrepresented structural alternatives",),
        "declared climate and P50 annual screen only",
        (subject.scope.intended_use,),
        (),
        "new supported independent evidence required",
    )
    validation = ValidationEvidence(
        ValidationMethod.WITHHELD,
        ("climate-2001",),
        ("climate-2010", "climate-2011"),
        (),
        (),
        ("trained-a",),
        c.cases,
        ("climate-2001",),
        c.cases,
        ("donor-a",),
        ("rating errors shared across flows",),
        moment(3),
        "caller-owned complete-year holdout study",
    )
    items = tuple(
        EvidenceItem(r, CheckFinding.PASS, "synthetic evidence source", "hypothetical supplied specialist finding")
        for r in minimum_evidence(subject, DailyDerivation.NATIVE)
    )
    evidence = ScientificEvidence(
        subject,
        "study-v1",
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        OfficialAdmissibility.PENDING,
        items,
        (observation(), observation("heldout-b", -3.0)),
        validation,
        RatingSupport.WITHIN_RANGE,
        ClimateTreatment.COMMON_BASIS,
        DailyDerivation.NATIVE,
        frozen_record=record,
    )
    return record, evidence


def check(result, name):
    return next(c for c in result.checks.checks if c.check_id == name)


def test_equal_maximum_passes_and_official_pending_is_independent():
    record, evidence = supplied()
    result = assess_scientific_use(record, evidence)
    assert [c.actual for c in result.comparisons] == [3.0, 3.0]
    assert result.findings.scientific_adequacy is ScientificAdequacy.ACCEPTED
    assert result.findings.official_admissibility is OfficialAdmissibility.PENDING
    assert result.acceptance_for(record.product).finding is CheckFinding.PASS
    assert result.checks.completeness is Completeness.COMPLETE


def test_failure_survives_missing_other_case():
    record, evidence = supplied()
    result = assess_scientific_use(record, replace(evidence, observations=(observation(candidate=4.0),)))
    assert [c.finding for c in result.comparisons] == [CheckFinding.FAIL, CheckFinding.UNKNOWN]
    assert result.checks.finding is CheckFinding.FAIL
    assert result.checks.completeness is Completeness.INCOMPLETE
    assert result.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED


def test_strict_equality_is_configured_not_rounded():
    c = criterion(comparison=Comparison.LESS_THAN)
    result = compare_criterion(c, (observation(), observation("heldout-b", -3.0)))
    assert all(r.finding is CheckFinding.FAIL for r in result)


def test_signed_absolute_and_zero_denominator_retained():
    o = observation(candidate=4.0, reference=0.0)
    assert o.signed_error == 4.0
    assert o.absolute_error == 4.0
    assert o.relative_error is None
    relative = compare_criterion(criterion(measure=ErrorMeasure.RELATIVE), (o,))
    assert relative[0].actual is None
    assert relative[0].finding is CheckFinding.UNKNOWN
    negative = observation(candidate=1.0, reference=3.0)
    assert negative.signed_error == -2.0
    assert negative.absolute_error == 2.0
    assert negative.relative_error == pytest.approx(-2 / 3)


@pytest.mark.parametrize(
    "aggregation, expected", [(Aggregation.MAXIMUM, 3.0), (Aggregation.MEAN, 2.0), (Aggregation.MINIMUM, 1.0)]
)
def test_frozen_aggregation(aggregation, expected):
    c = criterion(aggregation=aggregation)
    observations = (observation(candidate=1.0), observation("heldout-b", 3.0))
    result = compare_criterion(c, observations)
    assert result[0].actual == expected
    assert compare_criterion(c, observations[:1])[0].finding is CheckFinding.UNKNOWN


def test_missing_acceptance_basis_preserves_exploratory_number():
    record, evidence = supplied()
    result = assess_scientific_use(replace(record, criteria=()), replace(evidence, observations=()))
    assert result.findings.computability is Computability.COMPUTABLE
    assert result.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED
    assert "acceptance basis missing" in result.findings.reasons


def test_short_record_indicative_no_length_gate_and_rating_restriction_survives():
    record, evidence = supplied()
    record = replace(record, indicative_basis="short record supports declared annual screen with uncertainty")
    result = assess_scientific_use(record, replace(evidence, rating=RatingSupport.OUTSIDE_RANGE, frozen_record=record))
    assert result.findings.scientific_adequacy is ScientificAdequacy.ACCEPTED_AS_INDICATIVE
    assert result.acceptance_for(record.product).finding is CheckFinding.PASS
    assert any(UsePurpose.SIZING.value in r.prohibited_uses for r in result.findings.restrictions)


def test_rating_cannot_size_even_with_indicative_label():
    subject = replace(product(), purpose=UsePurpose.SIZING)
    record, evidence = supplied(subject)
    result = assess_scientific_use(
        replace(record, indicative_basis="short record"), replace(evidence, rating=RatingSupport.OUTSIDE_RANGE)
    )
    assert result.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED
    assert result.acceptance_for(subject).finding is CheckFinding.FAIL


def test_untreated_trend_and_inherited_restrictions_bind():
    record, evidence = supplied()
    result = assess_scientific_use(record, replace(evidence, climate=ClimateTreatment.UNTREATED_TREND))
    assert check(result, "climate_basis").finding is CheckFinding.FAIL
    result = assess_scientific_use(
        record,
        replace(
            evidence, restrictions=(UseRestriction("confirmed invalid source", (record.product.scope.intended_use,)),)
        ),
    )
    assert result.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED
    assert "confirmed invalid source" in result.findings.reasons


@pytest.mark.parametrize(
    "field, value",
    [("target_probability", 0.99), ("statistic_name", "different estimator"), ("calendar", "different calendar")],
)
def test_no_acceptance_transfer_when_scope_string_coincides(field, value):
    record, evidence = supplied()
    result = assess_scientific_use(record, evidence)
    assert result.acceptance_for(replace(record.product, **{field: value})).finding is CheckFinding.UNKNOWN
    with pytest.raises(ValueError, match="exact product"):
        assess_scientific_use(record, replace(evidence, product=replace(record.product, **{field: value})))


def test_no_profile_or_provenance_transfer():
    record, evidence = supplied()
    with pytest.raises(ValueError, match="frozen profile"):
        assess_scientific_use(record, replace(evidence, profile_version="v2"))
    subject = replace(record.product, provenance=replace(record.product.provenance, scenario="scenario-b"))
    assert assess_scientific_use(record, evidence).acceptance_for(subject).finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize(
    "changes, gate",
    [
        ({"training_clusters": ("climate-2010",)}, "climate_cluster_separation"),
        ({"previously_exposed_clusters": ("climate-2010",)}, "climate_cluster_separation"),
        ({"excluded_clusters": ("climate-2010",)}, "climate_cluster_separation"),
        ({"training_cases": ("heldout-a",)}, "case_separation"),
        ({"evaluated_at": moment(1).replace(year=2025)}, "frozen_before_validation"),
        ({"validation_clusters": ()}, "withheld_coverage"),
    ],
)
def test_withholding_cannot_be_claimed_over_contaminated_or_absent_evidence(changes, gate):
    record, evidence = supplied()
    result = assess_scientific_use(record, replace(evidence, validation=replace(evidence.validation, **changes)))
    assert check(result, gate).finding is CheckFinding.FAIL


def test_revisions_need_new_version_old_result_and_reserved_validation():
    record, evidence = supplied()
    with pytest.raises(ValueError, match="previous profile"):
        replace(record, previous_profile="old-v1")
    revision = replace(
        record,
        previous_profile="old-v1",
        revision_reason="changed criteria after development",
        previous_result="failed earlier heldout season",
    )
    assert check(assess_scientific_use(revision, evidence), "revision_exposure_disclosed").finding is CheckFinding.FAIL
    result = assess_scientific_use(
        revision,
        replace(
            evidence,
            frozen_record=revision,
            validation=replace(
                evidence.validation, previously_exposed_clusters=("climate-2009",), method=ValidationMethod.NESTED
            ),
        ),
    )
    assert result.findings.scientific_adequacy is ScientificAdequacy.ACCEPTED


def test_missing_nonwaivable_evidence_not_waived_by_advisory_diagnostics():
    record, evidence = supplied()
    result = assess_scientific_use(
        record,
        replace(
            evidence, items=tuple(i for i in evidence.items if i.requirement is not EvidenceRequirement.UNCERTAINTY)
        ),
    )
    assert check(result, "uncertainty_and_coverage").finding is CheckFinding.UNKNOWN
    assert result.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED


def test_rare_tail_separate_from_less_extreme_holdouts_and_annual_acceptance():
    record, evidence = supplied()
    assert assess_scientific_use(record, evidence).findings.scientific_adequacy is ScientificAdequacy.ACCEPTED
    subject = replace(record.product, target_probability=0.99)
    result = assess_scientific_use(replace(record, product=subject), replace(evidence, product=subject))
    assert check(result, "independent_rare_tail_applicability").finding is CheckFinding.UNKNOWN
    assert result.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED


def daily_product():
    return replace(
        product(),
        kind=HydrologicalProductKind.DAILY_PATTERN,
        resolution=TemporalResolution.DAILY,
        statistic_name="conditional daily design pattern",
    )


def test_daily_shape_cannot_pass_on_annual_or_string_only_evidence():
    record, evidence = supplied(daily_product())
    result = assess_scientific_use(record, evidence)
    assert result.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED
    assert check(result, "daily_numeric_criteria").finding is CheckFinding.UNKNOWN


def test_daily_disaggregation_requires_colocated_tail_spells_and_propagation():
    record, evidence = supplied(daily_product())
    result = assess_scientific_use(record, replace(evidence, daily_derivation=DailyDerivation.DISAGGREGATED))
    for requirement in (
        EvidenceRequirement.COLOCATED_DAILY,
        EvidenceRequirement.DAILY_LOW_TAIL,
        EvidenceRequirement.DAILY_SPELLS,
        EvidenceRequirement.PROPAGATED_UNCERTAINTY,
    ):
        assert check(result, requirement.value).finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize(
    "changes, gate",
    [
        ({"benchmark_training_clusters": ("climate-2010",)}, "benchmark_separation"),
        ({"benchmark_cases": ("heldout-a",)}, "benchmark_same_cases"),
        ({"method": ValidationMethod.REGIONAL}, "daily_withheld_years"),
    ],
)
def test_daily_benchmark_and_withheld_minimum(changes, gate):
    record, evidence = supplied(daily_product())
    result = assess_scientific_use(record, replace(evidence, validation=replace(evidence.validation, **changes)))
    assert check(result, gate).finding is CheckFinding.FAIL


def test_dekadal_actual_intervals_and_name_preserved_without_daily_equivalence():
    intervals = (
        Interval(datetime(2019, 2, 1, tzinfo=UTC), datetime(2019, 2, 11, tzinfo=UTC)),
        Interval(datetime(2019, 2, 11, tzinfo=UTC), datetime(2019, 2, 21, tzinfo=UTC)),
        Interval(datetime(2019, 2, 21, tzinfo=UTC), datetime(2019, 3, 1, tzinfo=UTC)),
    )
    subject = replace(
        product(),
        resolution=TemporalResolution.DEKADAL,
        kind=HydrologicalProductKind.COARSE_STATISTIC,
        statistic_name="dekadal 95-percent exceedance",
        intervals=intervals,
    )
    record, evidence = supplied(subject)
    result = assess_scientific_use(record, evidence)
    assert result.findings.scientific_adequacy is ScientificAdequacy.ACCEPTED
    assert result.record.product.intervals[-1].seconds == 8 * 86400
    for name in ("Q347", "daily Q95", "dekadal Q95"):
        with pytest.raises(ValueError, match="labelled"):
            replace(subject, statistic_name=name)
    with pytest.raises(ValueError, match="daily or duration"):
        replace(subject, kind=HydrologicalProductKind.DAILY_PATTERN)


@pytest.mark.parametrize(
    "changes",
    [
        {"preparer": " Reviewer-B "},
        {"criteria": [criterion()]},
        {"frozen_at": datetime(2026, 9, 1)},
        {"permitted_uses": ("",)},
    ],
)
def test_record_invariants(changes):
    record, _ = supplied()
    with pytest.raises((TypeError, ValueError)):
        replace(record, **changes)


@pytest.mark.parametrize("field", ["candidate", "reference"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), True])
def test_invalid_diagnostic_values_rejected(field, value):
    with pytest.raises(ValueError, match="finite"):
        replace(observation(), **{field: value})


def test_wrong_units_formula_domain_duplicate_and_undeclared_cases_refused():
    for changes in ({"units": "m3/s"}, {"formula": "other"}, {"domain": "elsewhere"}, {"case": "undeclared"}):
        with pytest.raises(ValueError, match="frozen criterion"):
            compare_criterion(criterion(), (replace(observation(), **changes),))
    with pytest.raises(ValueError, match="duplicate"):
        compare_criterion(criterion(), (observation(), observation()))


def test_missing_and_uncomputable_paths_remain_distinct():
    record, evidence = supplied()
    result = assess_scientific_use(record, replace(evidence, validation=None))
    assert result.checks.completeness is Completeness.INCOMPLETE
    unavailable = assess_scientific_use(record, replace(evidence, computability=Computability.NOT_COMPUTABLE))
    assert unavailable.findings.computability is Computability.NOT_COMPUTABLE
    assert unavailable.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED


def supported_daily():
    record, evidence = supplied(daily_product())
    contracts = (
        (EvidenceRequirement.SEASONAL_SHARES, "percent", "seasonal-volume/year-volume*100", 2.0),
        (EvidenceRequirement.TIMING, "days", "nonwrapping-first-half-volume", 3.0),
        (EvidenceRequirement.MINIMA, "m3/s", "minimum-complete-seven-day-mean", 1.0),
        (EvidenceRequirement.SPELLS, "days", "longest-strict-below-predeclared-flow", 1.0),
    )
    criteria = tuple(
        criterion(criterion_id=r.value, requirement=r, units=unit, formula=formula, limit=limit)
        for r, unit, formula, limit in contracts
    )
    observations = tuple(
        DiagnosticObservation(
            c.criterion_id, case, c.limit, 0.0, c.units, c.formula, c.domain, "synthetic distinct supplied diagnostic"
        )
        for c in criteria
        for case in c.cases
    )
    record = replace(record, criteria=criteria)
    return record, replace(evidence, observations=observations, frozen_record=record)


def test_daily_success_requires_distinct_quantitative_diagnostic_limits():
    record, evidence = supported_daily()
    result = assess_scientific_use(record, evidence)
    assert result.findings.scientific_adequacy is ScientificAdequacy.ACCEPTED
    assert result.acceptance_for(record.product).finding is CheckFinding.PASS
    assert [c.actual for c in result.comparisons] == [2.0, 2.0, 3.0, 3.0, 1.0, 1.0, 1.0, 1.0]


def test_failed_signed_minimum_does_not_disappear_in_other_good_shape_metrics():
    record, evidence = supported_daily()
    key = EvidenceRequirement.MINIMA.value
    criteria = tuple(replace(c, measure=ErrorMeasure.SIGNED) if c.criterion_id == key else c for c in record.criteria)
    observations = tuple(
        replace(o, candidate=2.0) if o.criterion_id == key and o.case == "heldout-a" else o
        for o in evidence.observations
    )
    result = assess_scientific_use(replace(record, criteria=criteria), replace(evidence, observations=observations))
    assert result.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED
    failure = next(c for c in result.comparisons if c.criterion.criterion_id == key and c.case == "heldout-a")
    assert failure.actual == 2.0
    assert failure.observations[0].signed_error == 2.0
    assert failure.observations[0].absolute_error == 2.0


def test_advisory_label_cannot_waive_required_daily_metric():
    record, evidence = supported_daily()
    criteria = tuple(
        replace(c, role=CriterionRole.ADVISORY) if c.requirement is EvidenceRequirement.MINIMA else c
        for c in record.criteria
    )
    record = replace(record, criteria=criteria)
    observations = tuple(
        replace(o, candidate=2.0) if o.criterion_id == EvidenceRequirement.MINIMA.value else o
        for o in evidence.observations
    )
    result = assess_scientific_use(record, replace(evidence, observations=observations, frozen_record=record))
    assert check(result, "daily_numeric_criteria").finding is CheckFinding.PASS
    assert any(c.finding is CheckFinding.FAIL for c in result.checks.checks if "duration_minimum" in c.check_id)
    assert result.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED


def test_validation_cases_not_replaced_by_favourable_subset():
    record, evidence = supplied()
    result = assess_scientific_use(
        replace(record, criteria=(criterion(cases=("heldout-a",)),)),
        replace(evidence, observations=evidence.observations[:1]),
    )
    assert check(result, "diagnostic_validation_cases").finding is CheckFinding.FAIL


def test_relative_output_units_are_dimensionless():
    c = criterion(measure=ErrorMeasure.RELATIVE)
    assert c.units == "days"
    assert c.comparison_units == "1"


def test_forged_assessment_cannot_promote_failed_evidence():
    record, evidence = supplied()
    failed = assess_scientific_use(record, replace(evidence, observations=(observation(candidate=4.0),)))
    forged = replace(failed, findings=replace(failed.findings, scientific_adequacy=ScientificAdequacy.ACCEPTED))
    assert forged.acceptance_for(record.product).finding is CheckFinding.FAIL


def test_runnable_annual_screening_example():
    from examples.scientific_use import annual_screening_study

    record, evidence = annual_screening_study()
    result = assess_scientific_use(record, evidence)
    assert result.findings.scientific_adequacy is ScientificAdequacy.ACCEPTED_AS_INDICATIVE
    assert result.comparisons[0].actual == 3.0
    assert result.findings.official_admissibility is OfficialAdmissibility.PENDING


def test_full_physical_climate_population_and_value_identity():
    record, evidence = supplied()
    result = assess_scientific_use(record, evidence)
    subjects = (
        replace(record.product, location=replace(record.product.location, mapping_version="v2")),
        replace(record.product, climate_basis="future scenario"),
        replace(record.product, population="seasonal minima"),
        replace(record.product, reference_identity="other complete reference"),
        replace(record.product, result_identity="other result"),
        replace(record.product, result_value=Flow(0)),
    )
    assert all(result.acceptance_for(subject).finding is CheckFinding.UNKNOWN for subject in subjects)


def test_declared_scalar_result_cannot_be_missing_and_accepted():
    subject = replace(product(), result_value=None)
    record, evidence = supplied(subject)
    result = assess_scientific_use(record, evidence)
    assert check(result, "scalar_result").finding is CheckFinding.UNKNOWN
    assert result.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED


def test_development_limitation_retains_exact_noncertifying_meaning():
    from fishy.scientific_acceptance import DESIGN_PATTERN_DEVELOPMENT_LIMITATION

    assert "All 21 dry held-out cases" in DESIGN_PATTERN_DEVELOPMENT_LIMITATION
    assert "seven-day minimum" in DESIGN_PATTERN_DEVELOPMENT_LIMITATION
    assert "three, not all four" in DESIGN_PATTERN_DEVELOPMENT_LIMITATION
    assert "not naturalised Uzbek" in DESIGN_PATTERN_DEVELOPMENT_LIMITATION


def test_frozen_criteria_cannot_change_without_new_validation_profile():
    record, evidence = supplied()
    evidence = replace(evidence, observations=(observation(candidate=4), observation("heldout-b", candidate=4)))
    assert assess_scientific_use(record, evidence).findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED
    relaxed = replace(record, criteria=(replace(record.criteria[0], limit=4.0),))
    assert assess_scientific_use(relaxed, evidence).findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED


def test_disaggregated_duration_minimum_cannot_avoid_daily_evidence_by_annual_resolution():
    subject = replace(product(), kind=HydrologicalProductKind.DURATION_MINIMUM, duration_days=7)
    record, evidence = supplied(subject)
    result = assess_scientific_use(record, replace(evidence, daily_derivation=DailyDerivation.DISAGGREGATED))
    assert result.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED


def test_advisory_required_applicability_failure_cannot_be_waived():
    record, evidence = supported_daily()
    transfer = replace(
        record.criteria[0],
        criterion_id="target-transfer",
        requirement=EvidenceRequirement.TARGET_TRANSFER,
        role=CriterionRole.ADVISORY,
        limit=-1.0,
    )
    observations = tuple(
        replace(o, criterion_id=transfer.criterion_id)
        for o in evidence.observations
        if o.criterion_id == record.criteria[0].criterion_id
    )
    record = replace(record, criteria=record.criteria + (transfer,))
    result = assess_scientific_use(
        record, replace(evidence, observations=evidence.observations + observations, frozen_record=record)
    )
    assert check(result, "frozen_record_identity").finding is CheckFinding.PASS
    assert any(c.finding is CheckFinding.FAIL for c in result.checks.checks if "target-transfer" in c.check_id)
    assert result.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED


def test_known_maximum_error_failure_survives_missing_case():
    record, evidence = supplied()
    record = replace(record, criteria=(replace(record.criteria[0], aggregation=Aggregation.MAXIMUM),))
    evidence = replace(evidence, observations=(observation(candidate=4),), frozen_record=record)
    result = assess_scientific_use(record, evidence)
    assert check(result, "frozen_record_identity").finding is CheckFinding.PASS
    assert result.checks.completeness is Completeness.INCOMPLETE
    assert result.checks.finding is CheckFinding.FAIL


@pytest.mark.parametrize(
    "aggregation, comparison, candidate, expected",
    [
        (Aggregation.MAXIMUM, Comparison.AT_MOST, 4.0, CheckFinding.FAIL),
        (Aggregation.MAXIMUM, Comparison.LESS_THAN, 3.0, CheckFinding.FAIL),
        (Aggregation.MINIMUM, Comparison.AT_LEAST, 2.0, CheckFinding.FAIL),
        (Aggregation.MINIMUM, Comparison.GREATER_THAN, 3.0, CheckFinding.FAIL),
        (Aggregation.MAXIMUM, Comparison.AT_LEAST, 2.0, CheckFinding.UNKNOWN),
        (Aggregation.MINIMUM, Comparison.AT_MOST, 4.0, CheckFinding.UNKNOWN),
        (Aggregation.MEAN, Comparison.AT_MOST, 4.0, CheckFinding.UNKNOWN),
    ],
)
def test_partial_aggregate_only_claims_mathematically_proven_failure(aggregation, comparison, candidate, expected):
    record, evidence = supplied()
    record = replace(record, criteria=(criterion(aggregation=aggregation, comparison=comparison),))
    evidence = replace(evidence, frozen_record=record, observations=(observation(candidate=candidate),))
    result = assess_scientific_use(record, evidence)
    assert result.comparisons[0].finding is expected
    assert result.comparisons[0].actual is None
    assert result.checks.finding is expected
    assert result.checks.completeness is Completeness.INCOMPLETE


def test_nonwaivable_advisory_cannot_select_favourable_validation_subset():
    record, evidence = supported_daily()
    transfer = replace(
        record.criteria[0],
        criterion_id="target-transfer",
        requirement=EvidenceRequirement.TARGET_TRANSFER,
        role=CriterionRole.ADVISORY,
        cases=("heldout-a",),
    )
    observations = tuple(
        replace(o, criterion_id=transfer.criterion_id)
        for o in evidence.observations
        if o.criterion_id == record.criteria[0].criterion_id and o.case == "heldout-a"
    )
    record = replace(record, criteria=record.criteria + (transfer,))
    result = assess_scientific_use(
        record, replace(evidence, frozen_record=record, observations=evidence.observations + observations)
    )
    assert result.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED
