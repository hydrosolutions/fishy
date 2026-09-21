"""U4 full-calendar proposed Uzbek baseline witnesses; exact arithmetic, no tolerance."""

from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction

import pytest

from examples.natural_baseline import PROVENANCE, accepted_family, synthetic_acceptance
from fishy.design_conditions import DesignClass
from fishy.evidence import CheckFinding
from fishy.natural_baseline import (
    ActualYearConvention,
    AdvisorySpawning,
    ClassificationBasis,
    ClassInterval,
    EndpointRule,
    ReachCoefficients,
    RiverRegulation,
    WinterProvision,
    baseline_family,
    coefficient_scope,
    recorded_minimum_product,
    select_actual_year,
    spawning_scope,
    winter_scope,
)
from fishy.pattern_calendar import AccountingYear
from fishy.quantities import Flow
from fishy.scientific_acceptance import UsePurpose


def supported_optional(value, patterns):
    scope_function = coefficient_scope if isinstance(value, ReachCoefficients) else winter_scope
    scope = scope_function(value, patterns[0].location, patterns[0].calendar, PROVENANCE, UsePurpose.SIZING.value)
    findings = replace(
        patterns[0].magnitude_assessment.findings,
        scope=scope,
        reasons=("explicit hypothetical specialist support for this exact optional operand",),
    )
    return replace(value, findings=findings)


def calculate(patterns, record, **kwargs):
    return baseline_family(patterns, record, provenance=PROVENANCE, profile_version="U4", **kwargs)


def test_four_shifted_classes_own_bounds_and_leap_year():
    patterns, record = accepted_family()
    result = calculate(patterns, record)
    assert result.checks.finding is CheckFinding.PASS
    assert tuple(r.samples[0].value for r in result.candidate.classes) == tuple(map(Flow, (10, 8, 6, 4)))
    assert all(len(r.samples) == 366 for r in result.candidate.classes)
    assert all(
        d.natural50 == Flow(10) and d.natural99 == Flow(2) and d.recorded_minimum == Flow(1) for d in result.diagnostics
    )
    assert record.value == Flow(1)
    assert len(record.days) == 365


def test_alpha_replaces_magnitude_retains_shifted_shape():
    calendar = AccountingYear(2023, 1, 0)
    shapes = {p: (Fraction(1),) * 365 for p in (50, 75, 90, 97, 99)}
    shapes[75] = (Fraction(1, 2), Fraction(3, 2)) + (Fraction(1),) * 363
    patterns, record = accepted_family(calendar, magnitudes=(10, 4, 3, 2, 1), shapes=shapes)
    alpha = ReachCoefficients(
        tuple(zip(DesignClass, map(Fraction, ("1", ".6", ".3", ".2")), strict=True)),
        "explicit hypothetical qualified reach",
        "median normalised scenario",
    )
    alpha = supported_optional(alpha, patterns)
    result = calculate(patterns, record, alpha=alpha)
    assert result.candidate.classes[1].samples[0].value == Flow(3)
    assert result.candidate.classes[1].samples[1].value == Flow(9)
    assert calculate(patterns, record).candidate.classes[1].samples[0].value == Flow(2)


def test_recorded_minimum_is_scalar_and_supported_zero_survives():
    patterns, record = accepted_family(minimum=0)
    result = calculate(patterns, record)
    assert record.value == Flow(0)
    assert all(d.recorded_minimum == Flow(0) for d in result.diagnostics)
    patterns, record = accepted_family(minimum=7)
    result = calculate(patterns, record)
    assert result.candidate.classes[-1].samples[0].value == Flow(7)


def test_winter_only_regulated_november_december_and_spawning_is_advisory():
    patterns, record = accepted_family()
    winter = WinterProvision(
        RiverRegulation.REGULATED_NATURAL, Flow(10), Fraction(9, 10), "hypothetical adoption", "supported reference"
    )
    spawning = AdvisorySpawning(
        (Fraction(13, 10),) * 366,
        patterns[0].calendar,
        "supported temperature-triggered biological timing",
        "hypothetical Uzbek coefficients",
    )
    winter = supported_optional(winter, patterns)
    spawning = replace(
        spawning,
        findings=replace(
            patterns[0].magnitude_assessment.findings,
            scope=spawning_scope(spawning, patterns[0].location, PROVENANCE, UsePurpose.SIZING.value),
        ),
    )
    result = calculate(patterns, record, winter=winter, spawning=spawning)
    dry = result.candidate.classes[-1]
    assert dry.samples[0].value == Flow(4)
    assert dry.samples[-1].value == Flow(9)
    assert result.advisory_spawning[-1].samples[-1].value == Flow(Fraction(117, 10))
    assert tuple(r.design for r in result.advisory_spawning) == (DesignClass.MODERATELY_DRY, DesignClass.DRY)
    inactive = calculate(patterns, record, winter=replace(winter, regulation=RiverRegulation.UNREGULATED_NATURAL))
    assert inactive.candidate.classes[-1].samples[-1].value == Flow(4)


@pytest.mark.parametrize("cause", ["minimum", "winter", "class", "natural99"])
def test_any_strict_crossing_declines_whole_family_before_cap(cause):
    patterns, record = accepted_family(
        minimum=11 if cause == "minimum" else 1,
        magnitudes=(10, 11 if cause == "class" else 8, 6, 4, 11 if cause == "natural99" else 2),
    )
    winter = (
        WinterProvision(
            RiverRegulation.REGULATED_NATURAL, Flow("10.000000000001"), Fraction(1), "scenario", "reference"
        )
        if cause == "winter"
        else None
    )
    winter = None if winter is None else supported_optional(winter, patterns)
    result = calculate(patterns, record, winter=winter)
    assert result.candidate is None
    assert result.checks.finding is CheckFinding.FAIL
    assert any(d.crossing is CheckFinding.FAIL for d in result.diagnostics)


@pytest.mark.parametrize("missing", ["pattern", "minimum", "shape_acceptance", "minimum_acceptance"])
def test_missing_inputs_never_create_candidate(missing):
    patterns, record = accepted_family()
    if missing == "pattern":
        patterns = patterns[:-1]
    if missing == "minimum":
        record = None
    if missing == "shape_acceptance":
        patterns = (*patterns[:-1], replace(patterns[-1], shape_assessment=None, shape_evidence=None))
    if missing == "minimum_acceptance":
        assert record is not None
        record = replace(record, assessment=None)
    result = calculate(patterns, record)
    assert result.candidate is None
    assert result.checks.finding is not CheckFinding.PASS


def test_minimum_acceptance_cannot_transfer_to_changed_content():
    patterns, record = accepted_family()
    result = calculate(patterns, replace(record, uncertainty="changed assumption"))
    assert result.candidate is None
    assert result.checks.finding is not CheckFinding.PASS


def test_minimum_rejects_partial_record_and_candidate_rejects_partial_calendar():
    patterns, record = accepted_family()
    with pytest.raises(ValueError, match="all accepted"):
        replace(record, years=())
    result = calculate(patterns, record)
    first = result.candidate.classes[0]
    with pytest.raises(ValueError, match="complete receiving"):
        replace(result.candidate, classes=(replace(first, samples=first.samples[:-1]), *result.candidate.classes[1:]))


def convention():
    bounds = tuple(map(Fraction, ("0", ".35", ".65", ".85", "1")))
    return ActualYearConvention(
        "scenario-v1",
        AccountingYear(2024, 1, 0),
        "accepted-reference-v1",
        tuple(
            ClassInterval(
                c,
                bounds[i],
                bounds[i + 1],
                EndpointRule.INCLUDED,
                EndpointRule.INCLUDED if i == 3 else EndpointRule.EXCLUDED,
            )
            for i, c in enumerate(DesignClass)
        ),
        "lower endpoint owns tie",
    )


def test_actual_year_pending_and_supplied_complete_convention():
    patterns, _ = accepted_family()
    config = replace(convention(), reference_identity=patterns[0].magnitude.reference_identity)

    def select(p, convention, reference, basis=ClassificationBasis.FORECAST):
        return select_actual_year(
            p,
            convention,
            reference=reference,
            calendar=config.calendar,
            reference_identity=config.reference_identity,
            basis=basis,
            issue_date=datetime(2024, 3, 1, tzinfo=UTC),
            assumptions="accepted forecast on supplied reference",
        )

    assert select(Fraction(1, 2), config, None).design is None
    assert select(Fraction(1, 2), None, patterns[0]).design is None
    assert select(Fraction(35, 100), config, patterns[0]).design is DesignClass.MEDIUM
    assert select(Fraction(1), config, patterns[0]).design is DesignClass.DRY
    assert select(Fraction(0), config, patterns[0]).design is DesignClass.WET
    with pytest.raises(ValueError, match="completed"):
        select(Fraction(1, 2), config, patterns[0], ClassificationBasis.OBSERVED)
    with pytest.raises(ValueError, match="gap/overlap"):
        replace(
            config, intervals=(replace(config.intervals[0], upper_rule=EndpointRule.INCLUDED), *config.intervals[1:])
        )


def test_optional_operand_labels_do_not_grant_permission():
    patterns, record = accepted_family()
    alpha = ReachCoefficients(
        tuple((c, Fraction(1, 2)) for c in DesignClass), "claimed qualification", "claimed derivation"
    )
    result = calculate(patterns, record, alpha=alpha)
    assert result.candidate.classes[0].samples[0].value == Flow(10)
    assert result.optional_evidence.finding is CheckFinding.UNKNOWN
    supported = supported_optional(alpha, patterns)
    assert calculate(patterns, record, alpha=supported).candidate.classes[0].samples[0].value == Flow(5)
    changed = replace(supported, derivation="changed basis")
    assert calculate(patterns, record, alpha=changed).candidate.classes[0].samples[0].value == Flow(10)
    winter = WinterProvision(
        RiverRegulation.REGULATED_NATURAL, Flow(10), Fraction(9, 10), "claimed adoption", "claimed reference"
    )
    result = calculate(patterns, record, winter=winter)
    assert result.candidate.classes[-1].samples[-1].value == Flow(4)
    assert result.optional_evidence.finding is CheckFinding.UNKNOWN


def test_known_natural_failure_survives_missing_scientific_acceptance():
    patterns, record = accepted_family(minimum=11)
    record = replace(record, assessment=None)
    result = calculate(patterns, record)
    assert result.checks.finding is CheckFinding.FAIL
    assert result.candidate is None
    assert result.diagnostics
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks.checks)


def test_scalar_product_preserves_source_days_and_cannot_be_duration_frequency():
    from fishy.scientific_acceptance import HydrologicalProductKind, TemporalResolution

    patterns, record = accepted_family()
    product = recorded_minimum_product(record, intended_use=UsePurpose.SIZING.value, purpose=UsePurpose.SIZING)
    assert product.kind is HydrologicalProductKind.RECORDED_MINIMUM
    assert product.resolution is TemporalResolution.DAILY
    assert product.result_value == record.value
    assert product.target_probability is None
    assert product.low_flow_return_period is None
    assert product.intervals == tuple(s.interval for y in record.years for s in y.samples)
    with pytest.raises(ValueError):
        replace(product, target_probability=Fraction(99, 100))


def test_minimum_actual_lowest_day_not_minimum_by_calendar_day():
    patterns, record = accepted_family()
    source = record.years[0]
    samples = tuple(replace(s, value=Flow(0 if i == 8 else Fraction(365, 364))) for i, s in enumerate(source.samples))
    changed = replace(source, samples=samples)
    record = replace(record, years=(changed,), assessment=None)
    record = replace(
        record,
        assessment=synthetic_acceptance(
            recorded_minimum_product(record, intended_use=UsePurpose.SIZING.value, purpose=UsePurpose.SIZING)
        ),
    )
    assert record.value == Flow(0)
    assert record.days == (samples[8].interval,)
    result = calculate(patterns, record)
    assert result.candidate is not None
    assert all(d.recorded_minimum == Flow(0) for d in result.diagnostics)


def test_unsupported_spawning_is_not_reported_as_supported_advice():
    patterns, record = accepted_family()
    spawning = AdvisorySpawning(
        (Fraction(13, 10),) * patterns[0].calendar.days, patterns[0].calendar, "claimed biology", "claimed coefficient"
    )
    result = calculate(patterns, record, spawning=spawning)
    assert result.candidate is not None
    assert result.advisory_spawning == ()
    assert result.optional_evidence.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize("change", ["values", "calendar", "member"])
def test_optional_scope_cannot_recycle_changed_evidence(change):
    patterns, record = accepted_family()
    alpha = supported_optional(
        ReachCoefficients(
            tuple((c, Fraction(1, 2)) for c in DesignClass), "scenario qualification", "scenario derivation"
        ),
        patterns,
    )
    if change == "values":
        alpha = replace(alpha, values=tuple((c, Fraction(3, 5)) for c in DesignClass))
    elif change == "calendar":
        alpha = replace(
            alpha,
            findings=replace(
                alpha.findings, scope=replace(alpha.findings.scope, period=AccountingYear(2023, 1, 0).interval)
            ),
        )
    else:
        alpha = replace(
            alpha, findings=replace(alpha.findings, provenance=replace(PROVENANCE, reference_member="other"))
        )
    result = calculate(patterns, record, alpha=alpha)
    assert result.candidate.classes[0].samples[0].value == Flow(10)
    assert result.optional_evidence.finding is not CheckFinding.PASS


def test_screening_acceptance_is_not_promoted_to_sizing():
    patterns, record = accepted_family(purpose=UsePurpose.SCREENING)
    assert all(p.use_checks.finding is CheckFinding.PASS for p in patterns)
    result = calculate(patterns, record)
    assert result.candidate is None
    assert result.diagnostics
    assert result.checks.finding is CheckFinding.UNKNOWN
