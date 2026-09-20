"""External adapters for all original quality cases, not historical software APIs.

Fixture decimals parse exactly. Only three source-rounded repeating answers use
an absolute 1e-14 comparison; production policy endpoints always remain exact.
Underspecified behavioral fixtures receive explicit synthetic values below, not
invented source meanings, observations, national profiles, or approvals.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path

import pytest

from fishy.evidence import CheckFinding, Completeness, CorrectionState, ProductionMethod, Provenance
from fishy.flows import Presence
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
from fishy.mixing import (
    BoundarySupport,
    CheckOutcome,
    Endpoint,
    Feasibility,
    FixedBoundary,
    FlowConstraints,
    LoadRate,
    MixingConstituent,
    quality_constraints,
    recheck_mixing,
    solve_mixing,
)
from fishy.quality import (
    Censoring,
    ChemicalBehavior,
    ChemicalIdentity,
    Comparison,
    GroupMember,
    GroupTarget,
    ObservationKind,
    ProfileStatus,
    QualityBounds,
    QualityObservation,
    QualityProfile,
    QualityTarget,
    QualityValue,
    UnresolvedTarget,
    assess_quality,
)
from fishy.quality_activation import (
    ActivationCondition,
    ActivationConditions,
    ActivationMode,
    BackgroundAccountMapping,
    ComponentStatus,
    EvidenceState,
    QualityActivation,
    QualityRoute,
    apply_quality_component,
)
from fishy.quantities import Flow, Volume
from fishy.source_control import screen_single_load
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

FIXTURES = json.loads((Path(__file__).parent / "data/quality_fixtures.json").read_text(), parse_float=Fraction)[
    "fixtures"
]
LOCATION = Location(Reach("synthetic-reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "1")
START = datetime(2026, 1, 1, tzinfo=UTC)
PERIOD = Interval(START, START + timedelta(seconds=1))
PROVENANCE = Provenance(
    "supplied synthetic case", "synthetic", None, "1", "1", "1", ProductionMethod.ILLUSTRATIVE, CorrectionState.ORIGINAL
)
SUPPORT = BoundarySupport(
    "Synthetic completely mixed fixed point boundary; arrival excluded from background; all carriers and separate loads counted once"
)


def chemical(name):
    behavior = ChemicalBehavior.TOTAL_DISSOLVED_SOLIDS if name == "tds" else ChemicalBehavior.CONSERVATIVE
    return ChemicalIdentity(name, name, name + " mass", "dissolved", behavior)


def target(name, limit, operator=Comparison.LE, identifier="individual", unit="kg/m3"):
    return QualityTarget(
        identifier, chemical(name), operator, QualityValue(limit, unit), "interval mean", "synthetic fixture"
    )


def group(limits, operator=Comparison.LE, unit="kg/m3"):
    return GroupTarget(
        "group",
        tuple(GroupMember(chemical(n), QualityValue(v, unit)) for n, v in limits.items()),
        operator,
        "interval mean",
        "synthetic fixture",
        "explicit synthetic group only",
    )


def profile(targets):
    return QualityProfile(
        "synthetic-profile",
        "1",
        "synthetic",
        "fixture",
        "1",
        "synthetic category",
        "screen",
        LOCATION,
        PERIOD,
        "synthetic",
        ProfileStatus.SCENARIO,
        tuple(t.identifier for t in targets),
        targets,
        "supplied section",
        "whole defensible interval",
        "explicit synthetic interpretation",
    )


def observation(name, value, upper=None, unit="mg/L", identity=None, censoring=Censoring.NONE):
    return QualityObservation(
        name,
        chemical(name) if identity is None else identity,
        QualityBounds(
            QualityValue(value, unit),
            QualityValue(value if upper is None else upper, unit),
            "supplied bounds",
            "synthetic fixture",
        ),
        LOCATION,
        PERIOD,
        "interval mean",
        Presence.PRESENT,
        PROVENANCE,
        ObservationKind.SYNTHETIC,
        "synthetic fully supported point/interval",
        "declared section and interval",
        censoring,
    )


def mixing_inputs(inputs, strict=False):
    if strict:
        loads, concentrations = {"salt": inputs["B_kg_s"]}, {"salt": inputs["Cs_kg_m3"]}
        targets = (target("salt", inputs["limit_kg_m3"], Comparison(inputs["operator"])),)
    else:
        loads, concentrations = inputs["B_kg_s"], inputs["Cs_kg_m3"]
        targets = tuple(
            group(t["limits_kg_m3"])
            if t["kind"] == "group_upper"
            else target(
                t["constituent"], t["limit_kg_m3"], Comparison.GE if t["kind"] == "lower" else Comparison.LE, str(i)
            )
            for i, t in enumerate(inputs["tests"])
        )
    boundary = FixedBoundary(
        LOCATION,
        PERIOD,
        Flow(inputs["Qb_m3s"]),
        tuple(
            MixingConstituent(chemical(n), LoadRate(v), QualityValue(concentrations[n], "kg/m3"))
            for n, v in loads.items()
        ),
        SUPPORT,
        PROVENANCE,
    )
    bounds = FlowConstraints(
        LOCATION,
        PERIOD,
        capacity=Flow(inputs["capacity_m3s"]) if "capacity_m3s" in inputs else None,
        ecological_total=Flow(inputs["ecological_total_m3s"]) if "ecological_total_m3s" in inputs else None,
    )
    return boundary, targets, bounds


def rounded(actual, expected):
    assert abs(actual - expected) <= Fraction(1, 10**14)


def check_mixing(case):
    inputs, expected, identifier = case["inputs"], case["expected"], case["id"]
    boundary, targets, bounds = mixing_inputs(inputs, case["kind"] == "mixing_strict_limit")
    result = solve_mixing(boundary, targets, bounds)
    for key in ("q_min_m3s", "quality_q_min_m3s"):
        if key in expected:
            assert result.quality_interval.minimum == expected[key]
    if "q_candidate_m3s" in expected:
        assert result.candidate is not None
        assert result.candidate.arrival.value == expected["q_candidate_m3s"]
    if "section_total_m3s" in expected:
        assert result.candidate is not None
        assert result.candidate.total.value == expected["section_total_m3s"]
    if "C_kg_m3" in expected:
        assert result.candidate is not None
        assert {c.identifier: v.value for c, v in result.candidate.predictions} == expected["C_kg_m3"]
    for key in ("q_interval_m3s", "quality_q_interval_m3s"):
        if key in expected:
            lower, upper = expected[key]
            if identifier == "lower_and_upper":
                assert result.quality_interval.lower == Fraction(20, 7)
                rounded(result.quality_interval.lower, lower)
            else:
                assert result.quality_interval.lower == lower
            assert result.quality_interval.upper == upper
    if identifier == "source_equals_limit":
        assert result.quality_interval.empty and result.status is Feasibility.SOURCE_WATER_INFEASIBLE
        inequalities, missing = quality_constraints(boundary, targets)
        assert not missing and inequalities[0].coefficient == 0 and inequalities[0].rhs < 0
    elif identifier == "capacity_limited":
        assert result.combined_interval.empty and result.status is Feasibility.CAPACITY_LIMITED
        assert result.capacity_check is not None
        concentration = result.capacity_check.predictions[0][1].value
        assert concentration == Fraction(17, 30)
        rounded(concentration, expected["C_at_capacity_kg_m3"]["salt"])
    elif identifier == "ecological_quality_conflict":
        assert result.combined_interval.empty and result.status is Feasibility.INDETERMINATE
        assert any("known conflicting" in reason for reason in result.reasons)
        assert recheck_mixing(boundary, targets, Flow(10)).outcome is CheckOutcome.FAIL
    elif identifier == "dry_channel_open_interval":
        assert result.quality_interval.lower_endpoint is Endpoint.OPEN
        assert result.quality_interval.minimum is None and result.quality_interval.infimum == 0
        zero = recheck_mixing(boundary, targets, Flow(0))
        assert zero.predictions == () and zero.outcome is CheckOutcome.INDETERMINATE
        assert "undefined" in zero.checks[0].reason
    elif identifier == "grouped_upper":
        assert result.candidate is not None
        assert result.candidate.checks[0].value == expected["group_sum_at_qmin"]
    elif identifier == "tds_standalone":
        assert [m.chemical.identifier for m in targets[1].members] == ["chloride", "sulphate"]
        assert result.candidate is not None
        assert result.candidate.outcome is CheckOutcome.PASS
        with pytest.raises(ValueError, match="TDS"):
            replace(targets[1], members=targets[1].members + (GroupMember(chemical("tds"), QualityValue(1, "kg/m3")),))
    elif identifier == "background_not_new_legal_floor":
        assert result.quality_total == Flow(10)
        assert not hasattr(result, "issued_floor") and not hasattr(result, "obligation")
    elif identifier == "strict_upper_open_minimum":
        endpoint = expected["additional_flow_interval_m3s"]
        assert result.quality_interval.lower == endpoint["lower"]
        assert result.quality_interval.upper is endpoint["upper"] is None
        assert result.quality_interval.lower_endpoint is Endpoint.OPEN
        assert result.quality_interval.minimum is None
        assert recheck_mixing(boundary, targets, Flow(endpoint["lower"])).outcome is CheckOutcome.FAIL
        candidate = recheck_mixing(boundary, targets, Flow(8))
        assert candidate.outcome is CheckOutcome.PASS
        assert candidate.predictions[0][1].value == Fraction(22, 45)
        rounded(candidate.predictions[0][1].value, expected["q_8_concentration_kg_m3"])
        capped = solve_mixing(boundary, targets, replace(bounds, capacity=Flow(endpoint["lower"])))
        assert capped.status is Feasibility.CAPACITY_LIMITED and capped.combined_interval.empty
    elif identifier == "strict_equality_zero_coefficient":
        assert result.quality_interval.empty and result.status is Feasibility.SOURCE_WATER_INFEASIBLE
        inequalities, _ = quality_constraints(boundary, targets)
        assert inequalities[0].coefficient == inequalities[0].rhs == 0
        assert inequalities[0].endpoint is Endpoint.OPEN


def account(boundary, arrival, outgoing):
    """Translate rates to explicit one-second synthetic interval accounts."""
    c = boundary.constituents[0]
    empty = Inventory(Volume(0), Mass(0))
    local = LoadAccount(
        "section",
        c.chemical,
        PERIOD,
        "synthetic",
        empty,
        empty,
        PROVENANCE,
    )
    seconds = PERIOD.seconds
    transfers = (
        AccountTransfer(
            "background",
            None,
            "section",
            Inventory(Volume(boundary.background.value * seconds), Mass(c.background_load.value * seconds)),
        ),
        AccountTransfer(
            "arrival",
            None,
            "section",
            Inventory(Volume(arrival * seconds), Mass(arrival * c.source_concentration.value * seconds)),
        ),
        AccountTransfer(
            "outlet",
            "section",
            None,
            Inventory(
                Volume(outgoing.total.value * seconds),
                Mass(outgoing.total.value * outgoing.predictions[0][1].value * seconds),
            ),
        ),
    )
    return assess_load_accounts((local,), transfers)


@pytest.mark.parametrize("case", FIXTURES, ids=lambda case: case["id"])
def test_supplied_quality_case(case):
    inputs, expected, identifier = case["inputs"], case["expected"], case["id"]
    if case["kind"] in ("mixing", "mixing_strict_limit"):
        check_mixing(case)
    elif identifier == "missing_group_member":
        selected = profile((group(inputs["group_limits"], unit="mg/L"),))
        observed = tuple(observation(n, v) for n, v in inputs["concentrations"].items() if v is not None)
        result = assess_quality(selected, observed)
        assert result.summary.finding is CheckFinding.UNKNOWN
        assert result.summary.completeness is Completeness.INCOMPLETE
    elif identifier == "censored_upper":
        lo, hi = inputs["concentration_interval_mg_l"]
        result = assess_quality(
            profile((target("salt", inputs["upper_limit_mg_l"], unit="mg/L"),)),
            (observation("salt", lo, hi, censoring=Censoring.NON_DETECT),),
        )
        assert result.summary.finding is CheckFinding.UNKNOWN
        assert result.results[0].upper == Fraction(3, 5)
    elif identifier == "unit_conversion":
        concentration = QualityValue(inputs["C_mg_l"], "mg/L")
        assert concentration.value == expected["C_kg_m3"]
        assert LoadRate(Flow(inputs["Q_m3s"]).value * concentration.value).value == expected["load_kg_s"]
    elif identifier == "single_load_control":
        result = screen_single_load(
            Flow(inputs["Q_m3s"]),
            QualityValue(inputs["limit_kg_m3"], "kg/m3"),
            LoadRate(inputs["other_load_kg_s"]),
            LoadRate(inputs["controlled_load_kg_s"]),
        )
        assert result.allowance is not None
        assert result.allowance.value == expected["allowed_load_kg_s"]
        assert result.reduction is not None
        assert result.reduction.value == expected["reduction_kg_s"]
    elif identifier == "conservation":
        boundary = FixedBoundary(
            LOCATION,
            PERIOD,
            Flow(inputs["Qb_m3s"]),
            (
                MixingConstituent(
                    chemical("salt"), LoadRate(inputs["B_kg_s"]), QualityValue(inputs["Cs_kg_m3"], "kg/m3")
                ),
            ),
            SUPPORT,
            PROVENANCE,
        )
        checked = recheck_mixing(boundary, (target("salt", Fraction(1, 2)),), Flow(inputs["q_m3s"]))
        result = account(boundary, inputs["q_m3s"], checked)
        result.require_valid()
        assert (
            sum(t.amount.mass.value for t in result.transfers if t.origin is None) / PERIOD.seconds
            == expected["incoming_load_kg_s"]
        )
        assert result.transfers[-1].amount.mass.value / PERIOD.seconds == expected["outgoing_load_kg_s"]
        assert result.basin.mass_kg / PERIOD.seconds == expected["residual_kg_s"]
    elif identifier == "inactive_quality":
        # Fixture supplies component totals, not a physical boundary. This explicit
        # synthetic boundary realizes its quality total: 10 kg/s / .5 kg/m3 = 20 m3/s.
        boundary = FixedBoundary(
            LOCATION,
            PERIOD,
            Flow(inputs["Qeco"]),
            (
                MixingConstituent(
                    chemical("salt"), LoadRate(Fraction(inputs["quality_candidate"], 2)), QualityValue(0, "kg/m3")
                ),
            ),
            SUPPORT,
            PROVENANCE,
        )
        targets = (target("salt", Fraction(1, 2)),)
        checked = solve_mixing(boundary, targets).candidate
        assert checked is not None
        closure = account(boundary, checked.arrival.value, checked)
        missing = ActivationCondition(EvidenceState.MISSING, "fixture does not supply approvals")
        activation = QualityActivation(
            "synthetic",
            QualityRoute.REGIME,
            ActivationMode.ADVISORY,
            ActivationConditions(missing, missing, missing, missing, missing),
            "explicit inactive fixture",
        )
        controls = SourceControlEvidence(
            "synthetic",
            "section",
            PERIOD,
            ControlState.EXHAUSTED,
            (("diffuse", ResidualSourceKind.UNCONTROLLABLE_DIFFUSE),),
            "explicit synthetic supporting inventory",
        )
        result = apply_quality_component(
            Flow(inputs["Qeco"]),
            boundary,
            targets,
            activation,
            controls,
            (closure,),
            BackgroundAccountMapping(
                ("background",), "explicit synthetic background and arrival ledger", LOCATION, ("arrival",)
            ),
        )
        assert result.quality.quality_total == Flow(inputs["quality_candidate"])
        assert result.requirement == Flow(expected["report_requirement"])
        assert result.status is ComponentStatus.ADVISORY
    elif identifier == "invalid_group_limit":
        with pytest.raises(ValueError, match="positive"):
            GroupMember(chemical("salt"), QualityValue(inputs["limit"], "kg/m3"))
    elif identifier == "negative_load":
        with pytest.raises(ValueError, match="negative"):
            LoadRate(inputs["B_kg_s"])
    elif identifier == "group_equality_interpretations":
        operators = (Comparison.LE, Comparison.LT, Comparison.UNRESOLVED_UPPER)
        findings = (CheckFinding.PASS, CheckFinding.FAIL, CheckFinding.UNKNOWN)
        for name, operator, finding in zip(inputs["profiles"], operators, findings, strict=True):
            selected = profile((replace(group({"a": 1, "b": 1}, operator), limit=Fraction(inputs["sum_limit"])),))
            result = assess_quality(
                replace(selected, interpretation=name),
                tuple(
                    observation(n, v, unit="kg/m3")
                    for n, v in zip(("a", "b"), inputs["normalised_ratios"], strict=True)
                ),
            )
            assert result.results[0].lower == expected["sum"]
            assert result.summary.finding is finding
    elif identifier == "nitrite_reporting_basis_unresolved":
        measurement, limit = inputs["measurement"], inputs["configured_limit"]
        ion = replace(chemical("nitrite"), reporting_basis=measurement["basis"])
        configured = replace(
            target("nitrite", limit["value"], unit=limit["unit"]), chemical=replace(ion, reporting_basis=limit["basis"])
        )
        result = assess_quality(
            profile((configured,)),
            (observation("nitrite", measurement["value"], unit=measurement["unit"], identity=ion),),
        )
        assert result.summary.finding is CheckFinding.UNKNOWN
        assert "reporting basis mismatch" in result.results[0].check.reasons[0]
    elif identifier == "source_range_not_automatically_interval":
        unresolved = UnresolvedTarget(
            "raw range", f"uninterpreted source cell: {inputs['source_cell']}", "supplied source table"
        )
        result = assess_quality(profile((unresolved,)), ())
        assert result.summary.finding is CheckFinding.UNKNOWN
        assert inputs["source_cell"] in result.results[0].check.reasons[0]
    elif identifier == "missing_group_member_preserves_individual_failure":
        # This behavioral fixture supplies outcomes, not magnitudes. Explicit
        # synthetic a=120>100 realizes its required individual failure.
        selected = profile(
            (target("a", 100, unit="mg/L"), group(dict.fromkeys(inputs["required_group_members"], 100), unit="mg/L"))
        )
        result = assess_quality(selected, tuple(observation(n, 120) for n in inputs["observed_members"]))
        assert result.results[0].check.finding is CheckFinding.FAIL
        assert result.results[1].check.finding is CheckFinding.UNKNOWN
        assert result.summary.finding is CheckFinding.FAIL
        assert result.summary.completeness is Completeness.INCOMPLETE
    else:
        pytest.fail(f"Original case lacks a behavioral adapter: {identifier}")
