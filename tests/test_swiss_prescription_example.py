"""Executable supported Swiss path with no simulator import."""

from dataclasses import replace

from examples.swiss_prescription import scenario
from fishy.duties import Delivery, DutyApplicability, Obligation, SuppliedDuty
from fishy.evidence import CheckFinding, OfficialAdmissibility
from fishy.quantities import Flow
from fishy.swiss_delivery import assess_swiss_delivery


def test_complete_supported_swiss_scenario():
    result = scenario()
    assert result.starting.q347.value == Flow(160, "l/s")
    assert result.starting.value == Flow(130, "l/s")
    assert result.safeguards.sites[0].minimum.value == Flow(180, "l/s")
    assert result.balancing.supported_final_total[0].value == Flow(220, "l/s")
    assert result.intake.schedule[0].value == Flow(220, "l/s")
    assert result.intake.numerical_schedule[0].value == Flow(220, "l/s")
    assert result.intake.projected_downstream[0].value == Flow(220, "l/s")
    for summary in (
        result.hydrology,
        result.permit.summary,
        result.process.summary,
        result.safeguards.summary,
        result.balancing.summary,
        result.intake.summary,
    ):
        assert summary.finding is CheckFinding.PASS
    adjustment = result.delivery.adjustments[0]
    assert adjustment.nominal.sample.value == Flow(220, "l/s")
    assert adjustment.inflow_proof is not None
    assert adjustment.inflow_proof.sample.value == Flow(150, "l/s")
    assert adjustment.justified.sample.value == Flow(150, "l/s")
    assert result.delivery.delivery.intervals[0].shortfall == Flow(30, "l/s")
    assert result.delivery.nominal_duty.schedule[0].sample.value == Flow(220, "l/s")
    assert result.delivery.control_evidence.finding is CheckFinding.PASS
    assert result.balancing.decision is not None
    assert result.balancing.decision.evidence is not None
    assert result.balancing.decision.evidence.official_admissibility is OfficialAdmissibility.PENDING


def test_already_prescribed_duty_runs_without_any_historical_sizing():
    # Reuse only a located attributed sample; no estimator, safeguards or balancing
    # result is passed into the supplied-duty assessment.
    from datetime import UTC, datetime

    from fishy.evidence import CorrectionState, ProductionMethod, Provenance
    from fishy.flows import FlowSample, Presence
    from fishy.spatial import CalculationSection, Location, Reach, WaterBody
    from fishy.time import Interval

    location = Location(
        Reach("supplied duty reach", "1", WaterBody("river", "1")), CalculationSection("intake", "1"), "1"
    )
    period = Interval(datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 1, 2, tzinfo=UTC))
    provenance = Provenance(
        "supplied duty record",
        "hypothetical assessment",
        None,
        "1",
        "1",
        "1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )
    nominal = FlowSample(location, period, Flow(220, "l/s"), Presence.PRESENT, provenance)
    duty = SuppliedDuty(
        "supplied independent duty",
        "v1",
        "supplied Swiss instrument",
        DutyApplicability.HYPOTHETICAL,
        (Obligation(nominal, "v1"),),
        "historic sizing unavailable; scenario copy of independently supplied duty",
    )
    result = assess_swiss_delivery(duty, (Delivery(replace(nominal, value=Flow(120, "l/s")), "v1"),))
    assert result.delivery.intervals[0].shortfall == Flow(100, "l/s")
    assert result.adjustments[0].justified.sample.value == Flow(220, "l/s")
    assert result.nominal_duty is duty


def test_scenario_configuration_does_not_mutate_issued_values():
    result = scenario()
    issued = result.delivery.nominal_duty
    changed = replace(
        issued,
        identifier="new scenario",
        version="v2",
        schedule=tuple(
            Obligation(
                replace(
                    o.sample,
                    value=Flow(300, "l/s"),
                    provenance=replace(
                        o.sample.provenance, scenario="alternative", configuration_version="scenario-v2"
                    ),
                ),
                "v2",
            )
            for o in issued.schedule
        ),
    )
    assert changed.schedule[0].sample.value == Flow(300, "l/s")
    assert issued.schedule[0].sample.value == Flow(220, "l/s")
    assert result.starting.value == Flow(130, "l/s")


def test_changed_swiss_configuration_executes_without_changing_independent_operations():
    from fishy.duties import assess_duty
    from fishy.residual_flow import statutory_minimum
    from fishy.swiss_safeguards import Safeguard, assess_safeguards, safeguard_study_scope

    original = scenario()
    issued = original.delivery.nominal_duty
    actual = original.delivery.delivery.intervals[0].delivery
    assert isinstance(actual, Delivery)
    independent_before = assess_duty(issued, (actual,))
    table_before = statutory_minimum(Flow(160, "l/s"))
    original_row = original.safeguards.sites[0]
    alternative_provenance = replace(
        original_row.site.starting_minimum.provenance,
        scenario="alternative passage study",
        configuration_version="scenario-v2",
    )
    alternative_site = replace(
        original_row.site,
        starting_minimum=replace(original_row.site.starting_minimum, provenance=alternative_provenance),
    )
    alternative_studies = []
    for study in original_row.studies:
        need = study.flow_need
        assert need is not None
        if study.safeguard is Safeguard.FISH_PASSAGE:
            need = replace(need, total=Flow(240, "l/s"))
        findings = replace(
            study.findings,
            provenance=alternative_provenance,
            scope=safeguard_study_scope(
                alternative_site, study.safeguard, study.treatment, need, study.measure, study.replacement
            ),
        )
        alternative_studies.append(replace(study, flow_need=need, findings=findings))
    changed = assess_safeguards((alternative_site,), tuple(alternative_studies), use=original.safeguards.use)
    assert changed.summary.finding is CheckFinding.PASS
    assert changed.sites[0].minimum.value == Flow(240, "l/s")
    assert changed.sites[0].minimum.provenance.configuration_version == "scenario-v2"
    assert original.safeguards.sites[0].minimum.value == Flow(180, "l/s")
    assert scenario() == original
    assert statutory_minimum(Flow(160, "l/s")) == table_before == Flow(130, "l/s")
    assert assess_duty(issued, (actual,)) == independent_before
    assert issued.schedule[0].sample.value == Flow(220, "l/s")
    assert original.delivery.delivery.intervals[0].shortfall == Flow(30, "l/s")
