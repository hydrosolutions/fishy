"""Selected minimum recurrence conversion and real supplied-product use boundaries."""

from dataclasses import replace
from fractions import Fraction

import pytest

from examples.scientific_use import annual_screening_study
from examples.supplied_low_flow_frequency import supplied_minimum_product
from fishy.evidence import CheckFinding, ScientificAdequacy
from fishy.low_flow_frequency import LowFlowReturnPeriod
from fishy.scientific_acceptance import (
    DailyDerivation,
    EvidenceItem,
    HydrologicalProductKind,
    TemporalResolution,
    assess_scientific_use,
    minimum_evidence,
)


@pytest.mark.parametrize(
    "years,u,p",
    [
        (2, Fraction(1, 2), Fraction(1, 2)),
        (10, Fraction(1, 10), Fraction(9, 10)),
        (3, Fraction(1, 3), Fraction(2, 3)),
        ("2.5", Fraction(2, 5), Fraction(3, 5)),
    ],
)
def test_exact_lower_tail_conversion(years, u, p):
    recurrence = LowFlowReturnPeriod(years)
    assert recurrence.nonexceedance_probability == u
    assert recurrence.exceedance_probability == p
    assert u + p == 1


@pytest.mark.parametrize("invalid", [1, 0, -1, ".999999", "nan", "inf", "-inf", True, False])
def test_invalid_return_period_is_refused(invalid):
    with pytest.raises((ValueError, TypeError)):
        LowFlowReturnPeriod(invalid)


def test_product_requires_exact_probability_and_retains_return_period():
    subject = supplied_minimum_product()
    assert subject.low_flow_return_period == LowFlowReturnPeriod(10)
    assert subject.target_probability == Fraction(9, 10)
    assert replace(subject, target_probability=0.9) == subject
    with pytest.raises(ValueError, match="disagrees"):
        replace(subject, target_probability=0.99)
    with pytest.raises(ValueError, match="declared target"):
        replace(subject, target_probability=None)
    with pytest.raises(TypeError, match="LowFlowReturnPeriod"):
        replace(subject, low_flow_return_period=10)
    thirds = replace(subject, low_flow_return_period=LowFlowReturnPeriod(3), target_probability=Fraction(2, 3))
    assert thirds.target_probability == Fraction(2, 3)
    with pytest.raises(ValueError, match="disagrees"):
        replace(thirds, target_probability=float(Fraction(2, 3)))


@pytest.mark.parametrize(
    "kind",
    [
        HydrologicalProductKind.ANNUAL_MAGNITUDE,
        HydrologicalProductKind.DAILY_PATTERN,
        HydrologicalProductKind.RARE_TAIL,
        HydrologicalProductKind.COARSE_STATISTIC,
    ],
)
def test_return_period_cannot_relabel_other_populations(kind):
    with pytest.raises(ValueError, match="duration-minimum"):
        replace(supplied_minimum_product(), kind=kind)


@pytest.mark.parametrize(
    "changes",
    [
        {"duration_days": None},
        {"duration_days": 0},
        {"duration_days": True},
        {"population": ""},
        {"population": " "},
        {"resolution": TemporalResolution.DAILY},
        {"resolution": TemporalResolution.DEKADAL},
    ],
)
def test_minimum_duration_population_and_annual_statistical_resolution_required(changes):
    with pytest.raises((ValueError, TypeError)):
        replace(supplied_minimum_product(), **changes)


def minimum_study():
    # Reuse synthetic review mechanics, but supply explicit minimum product and
    # minimum diagnostic identities. This does not derive minima from annual means.
    record, evidence = annual_screening_study()
    subject = supplied_minimum_product()
    criterion = replace(
        record.criteria[0],
        criterion_id="minimum_error",
        formula="candidate seven-day annual minimum minus reference minimum",
        domain="withheld complete accounting year",
        justification="synthetic minimum screening distinction, not policy",
    )
    record = replace(
        record,
        product=subject,
        profile_version="minimum-screen-v1",
        criteria=(criterion,),
        applicability="declared minimum population at Tr10 screening only",
        permitted_uses=(subject.scope.intended_use,),
        indicative_basis="synthetic short minimum record supports this limited screening use",
    )
    observations = tuple(
        replace(o, criterion_id=criterion.criterion_id, formula=criterion.formula, domain=criterion.domain)
        for o in evidence.observations
    )
    items = tuple(
        EvidenceItem(r, CheckFinding.PASS, "synthetic minimum evidence", "illustrative specialist support")
        for r in minimum_evidence(subject, DailyDerivation.NATIVE)
    )
    evidence = replace(
        evidence,
        product=subject,
        profile_version=record.profile_version,
        items=items,
        observations=observations,
        frozen_record=record,
    )
    return record, evidence


def test_actual_scientific_assessment_supports_supplied_minimum_without_constructing_it():
    record, evidence = minimum_study()
    result = assess_scientific_use(record, evidence)
    assert result.findings.scientific_adequacy is ScientificAdequacy.ACCEPTED_AS_INDICATIVE
    assert result.acceptance_for(record.product).finding is CheckFinding.PASS
    missing = assess_scientific_use(record, replace(evidence, validation=None))
    assert missing.findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED
    assert record.product.result_value == evidence.product.result_value


@pytest.mark.parametrize(
    "changes",
    [
        {"low_flow_return_period": LowFlowReturnPeriod(2), "target_probability": Fraction(1, 2)},
        {"duration_days": 30},
        {"population": "one summer-season minimum per complete accounting year"},
        {"low_flow_return_period": None},
    ],
)
def test_acceptance_does_not_transfer_to_changed_recurrence_duration_or_population(changes):
    record, evidence = minimum_study()
    result = assess_scientific_use(record, evidence)
    changed = replace(record.product, **changes)
    assert result.acceptance_for(changed).finding is not CheckFinding.PASS
    with pytest.raises(ValueError, match="exact product"):
        assess_scientific_use(record, replace(evidence, product=changed))


def test_existing_probability_only_supplied_minimum_remains_compatible():
    record, evidence = minimum_study()
    independent = replace(record.product, low_flow_return_period=None, target_probability=0.85)
    record = replace(record, product=independent)
    evidence = replace(evidence, product=independent, frozen_record=record)
    assert assess_scientific_use(record, evidence).acceptance_for(independent).finding is CheckFinding.PASS


def test_exact_large_return_period_does_not_round_exceedance_to_one():
    recurrence = LowFlowReturnPeriod(10**30)
    product = replace(
        supplied_minimum_product(),
        low_flow_return_period=recurrence,
        target_probability=recurrence.exceedance_probability,
    )
    assert product.target_probability is not None
    assert 1 - product.target_probability == Fraction(1, 10**30)
    assert product.target_probability < 1
