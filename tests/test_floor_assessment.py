"""Derived synthetic witnesses from Appendix A floor-uncertainty fixtures (2026-09-19).

All numbers are assumptions, not uncertainty defaults or application observations.
"""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from examples.issued_duty import scenario, scenario_evidence
from fishy.comparison_evidence import (
    Attribution,
    AttributionFinding,
    ButForFlow,
    MarginBounds,
    NumericalFinding,
)
from fishy.duties import Delivery, Floor
from fishy.evidence import Check, CheckFinding, OfficialAdmissibility, ProductionMethod
from fishy.floor_assessment import JointMargin, JointSupportKind, assess_floor
from fishy.flows import Coverage, Presence
from fishy.quantities import Flow, FlowBounds
from fishy.spatial import CompliancePoint

CASES = [
    ("uncertain_counterfactual_changes_finding", "5", ["3.8", "4.2"], ["3", "6"], ["-1.2", "1.2"], "indeterminate"),
    ("supported_numerical_shortfall_cause_unknown", "5", ["3.8", "4.2"], ["4.8", "6"], ["-1.2", "-0.6"], "below"),
    ("supported_not_below", "5", ["5.1", "5.3"], ["4", "6"], ["0.1", "1.3"], "not_below"),
    ("equality_at_upper_margin_is_indeterminate", "5", ["4.8", "5.0"], ["5", "6"], ["-0.2", "0"], "indeterminate"),
    ("point_equality_is_not_below", "5", ["5", "5"], ["5", "5"], ["0", "0"], "not_below"),
    ("absent_natural_supply_is_not_breach", "5", ["0", "0"], ["0", "0"], ["0", "0"], "not_below"),
    ("fixed_counterfactual_reproduces_old_comparison", "5", ["3.8", "4.2"], ["4.5", "4.5"], ["-0.7", "-0.3"], "below"),
    ("missing_counterfactual_uncertainty", "5", ["3.8", "4.2"], None, None, "unavailable"),
    ("supported_dependence_tightens_margin", "10", ["2", "4"], ["3", "5"], None, "joint"),
    ("invalid_reversed_interval", "5", ["4.2", "3.8"], ["4.8", "6"], None, "invalid"),
]


def inputs(floor_value="5", actual_bounds=("3.8", "4.2"), but_for_bounds=("3", "6")):
    _, delivery, existing = scenario(datetime(2020, 2, 29, tzinfo=UTC))
    template = delivery.actual.sample

    def bounded(bounds, fallback="4.5"):
        if bounds is None:
            return replace(template, value=Flow(fallback), uncertainty=None)
        lower, upper = map(Flow, bounds)
        return replace(
            template,
            value=Flow((lower.value + upper.value) / 2),
            uncertainty=FlowBounds(
                lower,
                upper,
                "stipulated enclosing fictional bounds",
                "floor-fixture-v1",
                "no independence or joint confidence assumed",
            ),
        )

    floor = Floor(replace(existing.floor.sample, value=Flow(floor_value), uncertainty=None), "floor-v1")
    actual = Delivery(bounded(actual_bounds), "actual-v1")
    but_for = ButForFlow(bounded(but_for_bounds), "but-for-v1", "tested abstraction")
    return floor, actual, but_for


@pytest.mark.parametrize("case_id,F,A,P,expected_margin,expected_finding", CASES, ids=[row[0] for row in CASES])
def test_all_ten_source_floor_witnesses(case_id, F, A, P, expected_margin, expected_finding):
    if expected_finding == "invalid":
        with pytest.raises(ValueError, match="ordered"):
            inputs(F, A, P)
        return
    floor, actual, but_for = inputs(F, A, P)
    evidence = scenario_evidence(floor, actual, but_for)
    joint = None
    if expected_finding == "joint":
        joint = JointMargin(
            floor,
            actual,
            but_for,
            MarginBounds(-1, -1),
            JointSupportKind.ENCLOSING,
            "analytic P=A+1 throughout support",
            "fixture-v1",
            "P=A+1",
            "full stipulated support",
        )
        expected_margin, expected_finding = ("-1", "-1"), "below"
    result = assess_floor(floor, actual, but_for, evidence=evidence, joint_margin=joint)
    assert result.numerical.value == expected_finding
    assert result.margin == (None if expected_margin is None else MarginBounds(*expected_margin))
    if joint:
        assert result.rectangular_margin == MarginBounds(-3, 1)
        assert result.rectangular_margin.finding is NumericalFinding.INDETERMINATE
    assert result.official.finding is CheckFinding.UNKNOWN
    assert result.responsibility.finding is CheckFinding.UNKNOWN
    assert result.floor == floor


def test_finite_draws_are_not_joint_support_and_do_not_change_rectangular_finding():
    floor, actual, but_for = inputs("10", ("2", "4"), ("3", "5"))
    joint = JointMargin(
        floor,
        actual,
        but_for,
        MarginBounds(-1, -1),
        JointSupportKind.FINITE_DRAWS,
        "sample extrema",
        "draws-v1",
        "shared errors",
        "ten draws, no enclosing proof",
    )
    result = assess_floor(
        floor, actual, but_for, evidence=scenario_evidence(floor, actual, but_for), joint_margin=joint
    )
    assert result.numerical is NumericalFinding.INDETERMINATE
    assert result.margin == MarginBounds(-3, 1)
    assert "finite draws" in result.reasons[0]


@pytest.mark.parametrize(
    "check_id",
    [
        "coverage",
        "infill",
        "authentication",
        "reconciliation",
        "uncertainty",
        "abstraction_metering",
        "downstream_of_conduct",
    ],
)
@pytest.mark.parametrize("finding", [CheckFinding.FAIL, CheckFinding.UNKNOWN])
def test_each_rejected_or_missing_prerequisite_makes_numeric_comparison_unavailable(check_id, finding):
    floor, actual, but_for = inputs("5", ("3.8", "4.2"), ("4.8", "6"))
    evidence = scenario_evidence(floor, actual, but_for)
    checks = tuple(
        replace(c, finding=finding, reasons=("required support unavailable",)) if c.check_id == check_id else c
        for c in evidence.checks
    )
    result = assess_floor(floor, actual, but_for, evidence=replace(evidence, checks=checks))
    assert result.numerical is NumericalFinding.UNAVAILABLE
    assert result.margin is None
    assert result.raw_shortfall == Flow(1)  # nominal diagnostic survives rejected evidence
    assert result.responsibility.finding is CheckFinding.UNKNOWN


def test_omitted_evidence_is_unavailable_not_indeterminate():
    floor, actual, but_for = inputs()
    evidence = replace(scenario_evidence(floor, actual, but_for), checks=())
    result = assess_floor(floor, actual, but_for, evidence=evidence)
    assert result.numerical is NumericalFinding.UNAVAILABLE
    assert len(evidence.admission.checks) == 7


@pytest.mark.parametrize("which", ["actual", "but_for"])
def test_missing_bounds_or_operand_are_not_zero_width(which):
    floor, actual, but_for = inputs()
    if which == "actual":
        actual = replace(actual, sample=replace(actual.sample, uncertainty=None))
    else:
        but_for = replace(but_for, sample=replace(but_for.sample, uncertainty=None))
    result = assess_floor(floor, actual, but_for, evidence=scenario_evidence(floor, actual, but_for))
    assert result.numerical is NumericalFinding.UNAVAILABLE
    if which == "actual":
        actual = None
    else:
        but_for = None
    result = assess_floor(floor, actual, but_for, evidence=scenario_evidence(floor, actual, but_for))
    assert result.numerical is NumericalFinding.UNAVAILABLE
    assert result.raw_shortfall is None


def test_floor_uncertainty_is_not_applied_to_fixed_issued_threshold():
    floor, actual, but_for = inputs("5", ("3.8", "4.2"), ("4.8", "6"))
    historical = replace(
        floor,
        sample=replace(
            floor.sample,
            uncertainty=FlowBounds(
                Flow(0), Flow(100), "historical estimation only", "old sizing study", "not operative threshold support"
            ),
        ),
    )
    result = assess_floor(historical, actual, but_for, evidence=scenario_evidence(historical, actual, but_for))
    assert result.margin == MarginBounds("-1.2", "-0.6")
    with pytest.raises(FrozenInstanceError):
        historical.version = "changed"


@pytest.mark.parametrize("missing", ["designation", "admission", "attribution", "scenario"])
def test_numeric_shortfall_stays_separate_from_official_and_causal_findings(missing):
    floor, actual, but_for = inputs("5", ("3.8", "4.2"), ("4.8", "6"))
    floor = replace(
        floor,
        sample=replace(
            floor.sample, provenance=replace(floor.sample.provenance, production_method=ProductionMethod.IMPORTED)
        ),
    )
    actual = replace(
        actual,
        sample=replace(
            actual.sample, provenance=replace(actual.sample.provenance, production_method=ProductionMethod.OBSERVED)
        ),
    )
    but_for = replace(
        but_for,
        sample=replace(
            but_for.sample,
            provenance=replace(but_for.sample.provenance, production_method=ProductionMethod.RECONSTRUCTED),
        ),
    )
    evidence = replace(
        scenario_evidence(floor, actual, but_for),
        point=CompliancePoint("control", "v1", floor.sample.location.section, "supplied designation"),
        official_admissibility=OfficialAdmissibility.ADMISSIBLE,
        attribution=Attribution(
            AttributionFinding.TO_TESTED_CONDUCT,
            "independent attribution-v1",
            Check("control", CheckFinding.PASS, ("operator control established",)),
            but_for.conduct,
        ),
    )
    if missing == "designation":
        evidence = replace(evidence, point=None)
    elif missing == "admission":
        evidence = replace(evidence, official_admissibility=OfficialAdmissibility.NOT_ADMISSIBLE)
    elif missing == "attribution":
        evidence = replace(
            evidence,
            attribution=Attribution(
                AttributionFinding.INDETERMINATE,
                "cause unresolved",
                Check("control", CheckFinding.UNKNOWN, ("missing control evidence",)),
            ),
        )
    else:
        actual = replace(
            actual,
            sample=replace(
                actual.sample,
                provenance=replace(actual.sample.provenance, production_method=ProductionMethod.SIMULATED),
            ),
        )
        evidence = replace(evidence, actual=actual)
    result = assess_floor(floor, actual, but_for, evidence=evidence)
    assert result.numerical is NumericalFinding.BELOW
    assert result.responsibility.finding is CheckFinding.UNKNOWN
    assert result.official.finding is (CheckFinding.PASS if missing == "attribution" else CheckFinding.UNKNOWN)


def test_supported_official_prerequisites_and_supplied_cause_are_not_legal_liability():
    floor, actual, but_for = inputs("5", ("3.8", "4.2"), ("4.8", "6"))
    floor = replace(
        floor,
        sample=replace(
            floor.sample, provenance=replace(floor.sample.provenance, production_method=ProductionMethod.IMPORTED)
        ),
    )
    actual = replace(
        actual,
        sample=replace(
            actual.sample, provenance=replace(actual.sample.provenance, production_method=ProductionMethod.OBSERVED)
        ),
    )
    but_for = replace(
        but_for,
        sample=replace(
            but_for.sample,
            provenance=replace(but_for.sample.provenance, production_method=ProductionMethod.RECONSTRUCTED),
        ),
    )
    evidence = replace(
        scenario_evidence(floor, actual, but_for),
        point=CompliancePoint("control", "v1", floor.sample.location.section, "supplied designation"),
        official_admissibility=OfficialAdmissibility.ADMISSIBLE,
        attribution=Attribution(
            AttributionFinding.TO_TESTED_CONDUCT,
            "independent attribution-v1",
            Check("control", CheckFinding.PASS, ("operator control established",)),
            but_for.conduct,
        ),
    )
    result = assess_floor(floor, actual, but_for, evidence=evidence)
    assert result.official.finding is CheckFinding.PASS
    assert result.responsibility.finding is CheckFinding.PASS
    assert "not a legal liability decision" in result.responsibility.reasons[0]
    with pytest.raises(ValueError, match="operator control"):
        replace(evidence.attribution, operator_control=Check("control", CheckFinding.UNKNOWN))
    with pytest.raises(ValueError, match="same tested conduct"):
        replace(evidence, attribution=replace(evidence.attribution, conduct="other abstraction"))


@pytest.mark.parametrize("value", ["NaN", "inf", "-inf", "-1"])
def test_nonfinite_or_negative_flow_refused(value):
    with pytest.raises(ValueError):
        inputs(value)
    with pytest.raises(ValueError):
        inputs("5", (value, "10"))


def test_evidence_and_joint_support_cannot_transfer_to_revised_operands():
    floor, actual, but_for = inputs()
    evidence = scenario_evidence(floor, actual, but_for)
    with pytest.raises(ValueError, match="exact floor operands"):
        assess_floor(replace(floor, version="floor-v2"), actual, but_for, evidence=evidence)
    with pytest.raises(ValueError, match="mix scenarios"):
        replace(
            evidence,
            actual=replace(
                actual, sample=replace(actual.sample, provenance=replace(actual.sample.provenance, scenario="other"))
            ),
        )
    with pytest.raises(ValueError, match="identical location"):
        replace(
            evidence,
            actual=replace(
                actual,
                sample=replace(
                    actual.sample, interval=replace(actual.sample.interval, end=datetime(2020, 3, 2, tzinfo=UTC))
                ),
            ),
        )
    joint = JointMargin(
        floor,
        actual,
        but_for,
        MarginBounds(0, 0),
        JointSupportKind.ENCLOSING,
        "supported method",
        "source-v1",
        "dependence",
        "coverage",
    )
    with pytest.raises(ValueError, match="joint margin does not bind"):
        assess_floor(
            floor, actual, but_for, evidence=evidence, joint_margin=replace(joint, floor=replace(floor, version="v2"))
        )


@pytest.mark.parametrize("status", [Presence.MISSING, Presence.UNSUPPORTED, Presence.OUTSIDE_HORIZON])
def test_unavailable_samples_and_partial_intervals_do_not_pass(status):
    floor, actual, but_for = inputs()
    actual = replace(
        actual,
        sample=replace(
            actual.sample, value=None, uncertainty=None, presence=status, reasons=("missing physical evidence",)
        ),
    )
    result = assess_floor(floor, actual, but_for, evidence=scenario_evidence(floor, actual, but_for))
    assert result.numerical is NumericalFinding.UNAVAILABLE
    floor, actual, but_for = inputs()
    actual = replace(actual, sample=replace(actual.sample, coverage=Coverage.PARTIAL, reasons=("partial day",)))
    assert (
        assess_floor(floor, actual, but_for, evidence=scenario_evidence(floor, actual, but_for)).numerical
        is NumericalFinding.UNAVAILABLE
    )
