"""Official findings cannot promote hypothetical operands through imported wrappers."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from examples.issued_duty import scenario, scenario_evidence
from fishy.comparison_evidence import Attribution, AttributionFinding, NumericalFinding
from fishy.delivery_assessment import assess_issued_delivery
from fishy.evidence import Check, CheckFinding, OfficialAdmissibility, ProductionMethod
from fishy.floor_assessment import assess_floor
from fishy.spatial import CompliancePoint
from fishy.uzbek_issuance import issue_obligation


def produced(sample, method, *, components=()):
    return replace(sample, provenance=replace(sample.provenance, production_method=method), components=components)


def admitted(threshold, actual, but_for=None):
    return replace(
        scenario_evidence(threshold, actual, but_for),
        point=CompliancePoint("point", "v1", threshold.sample.location.section, "supplied designation"),
        official_admissibility=OfficialAdmissibility.ADMISSIBLE,
        attribution=Attribution(
            AttributionFinding.TO_TESTED_CONDUCT,
            "supplied attribution-v1",
            Check("operator_control", CheckFinding.PASS, ("supported control",)),
            "hypothetical abstraction",
        ),
    )


@pytest.mark.parametrize("method", [ProductionMethod.ILLUSTRATIVE, ProductionMethod.SIMULATED])
@pytest.mark.parametrize("depth", [0, 1, 3])
@pytest.mark.parametrize("role", ["floor", "but_for"])
def test_hypothetical_floor_or_counterfactual_never_becomes_official_through_imports(method, depth, role):
    _, delivery, original = scenario(datetime(2020, 2, 29, tzinfo=UTC))
    actual = replace(delivery.actual, sample=produced(delivery.actual.sample, ProductionMethod.OBSERVED))
    floor = replace(original.floor, sample=produced(original.floor.sample, ProductionMethod.IMPORTED))
    but_for = replace(original.but_for, sample=produced(original.but_for.sample, ProductionMethod.RECONSTRUCTED))
    operand = floor if role == "floor" else but_for
    sample = produced(operand.sample, method)
    for _ in range(depth):
        sample = produced(operand.sample, ProductionMethod.IMPORTED, components=(sample,))
    if role == "floor":
        floor = replace(floor, sample=sample)
    else:
        but_for = replace(but_for, sample=sample)
    result = assess_floor(floor, actual, but_for, evidence=admitted(floor, actual, but_for))
    assert result.numerical is NumericalFinding.BELOW
    assert result.official.finding is CheckFinding.UNKNOWN
    assert result.responsibility.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize("method", [ProductionMethod.ILLUSTRATIVE, ProductionMethod.SIMULATED])
@pytest.mark.parametrize("role", ["requirement", "deliverability"])
@pytest.mark.parametrize("depth", [0, 2])
def test_imported_issuance_retains_hypothetical_operand_meaning(method, role, depth):
    issue, delivery, _ = scenario(datetime(2020, 2, 29, tzinfo=UTC))
    actual = replace(delivery.actual, sample=produced(delivery.actual.sample, ProductionMethod.OBSERVED))
    requirement = replace(issue.requirement, sample=produced(issue.requirement.sample, ProductionMethod.IMPORTED))
    capacity = replace(issue.deliverability, sample=produced(issue.deliverability.sample, ProductionMethod.IMPORTED))
    operand = requirement if role == "requirement" else capacity
    sample = produced(operand.sample, method)
    for _ in range(depth):
        sample = produced(operand.sample, ProductionMethod.IMPORTED, components=(sample,))
    if role == "requirement":
        requirement = replace(requirement, sample=sample)
    else:
        capacity = replace(capacity, sample=sample)
    issued = issue_obligation(
        requirement,
        capacity,
        version="v2",
        provenance=replace(issue.obligation.sample.provenance, production_method=ProductionMethod.IMPORTED),
    )
    result = assess_issued_delivery(issued.obligation, actual, evidence=admitted(issued.obligation, actual))
    assert result.numerical is NumericalFinding.BELOW
    assert result.raw_shortfall.value == 1
    assert result.official.finding is CheckFinding.UNKNOWN
    assert result.responsibility.finding is CheckFinding.UNKNOWN


def test_supported_reconstruction_is_not_rejected_as_hypothetical():
    _, delivery, original = scenario(datetime(2020, 2, 29, tzinfo=UTC))
    actual = replace(delivery.actual, sample=produced(delivery.actual.sample, ProductionMethod.OBSERVED))
    floor = replace(original.floor, sample=produced(original.floor.sample, ProductionMethod.IMPORTED))
    reconstruction = produced(original.but_for.sample, ProductionMethod.RECONSTRUCTED)
    but_for = replace(
        original.but_for, sample=produced(reconstruction, ProductionMethod.IMPORTED, components=(reconstruction,))
    )
    result = assess_floor(floor, actual, but_for, evidence=admitted(floor, actual, but_for))
    assert result.numerical is NumericalFinding.BELOW
    assert result.official.finding is CheckFinding.PASS
    assert result.responsibility.finding is CheckFinding.PASS
