"""Executable synthetic inventory-to-point-to-reach-to-overall acceptance."""

from examples.hydrological_condition import scenario
from fishy.evidence import Completeness, OfficialAdmissibility, ScientificAdequacy
from fishy.hydrological_condition import Indicator


def test_complete_and_partial_hydrological_example():
    output = scenario()
    assert [r.classification for r in output.point.condition.indicators] == [2, 1, 1, 3, 1, 2, 2, 2, 2]
    assert (output.point.condition.points, output.point.condition.classification) == (17, 3)
    assert output.overall.classification == 2
    assert output.overall.completeness is Completeness.COMPLETE
    assert output.partial_overall.classification is None
    assert output.partial_overall.completeness is Completeness.INCOMPLETE
    mean = next(r for r in output.point.calculations if r.indicator is Indicator.MEAN_FLOW)
    assert any(m.value == 36 for m in mean.metrics)
    assert output.partial_point.calculations[0] == output.point.calculations[0]
    findings = output.point.condition.context.evidence[0]
    assert findings.scientific_adequacy is ScientificAdequacy.ACCEPTED_AS_INDICATIVE
    assert findings.official_admissibility is OfficialAdmissibility.PENDING


def test_computed_conditions_do_not_change_swiss_prescription_or_delivery():
    from fractions import Fraction

    from test_swiss_delivery import duty, sample, specialist_findings

    from fishy.duties import Delivery
    from fishy.flow_events import InstantaneousDischarge
    from fishy.flow_pulses import HydropeakingMetrics, StageRate, assess_hydropeaking
    from fishy.hydrological_condition import AssessmentContext
    from fishy.quantities import Area, Flow
    from fishy.swiss_delivery import ConditionFinding, assess_swiss_delivery

    prescribed = duty()
    delivered = sample(220)
    ctx = AssessmentContext(delivered.location, delivered.interval, delivered.provenance)
    assessments = []
    classes = []
    for ratio in (Fraction(5, 2), Fraction(13, 2)):
        calculated = assess_hydropeaking(
            ctx,
            HydropeakingMetrics(
                InstantaneousDischarge(1),
                InstantaneousDischarge(Fraction(1, 10)),
                ratio,
                StageRate(Fraction(2)),
                StageRate(Fraction(2)),
                "supplied supported pulse metrics",
            ),
            Flow(1),
            Area(250, "km2"),
        )
        assert calculated.classification is not None
        classes.append(calculated.classification)
        identity = ("HYDMOD hydropeaking", f"class {calculated.classification.value}")
        finding = ConditionFinding(
            delivered.location,
            delivered.interval,
            *identity,
            specialist_findings(delivered, "specialist_condition", identity),
        )
        assessments.append(assess_swiss_delivery(prescribed, (Delivery(delivered, "v1"),), conditions=(finding,)))
    assert classes == [2, 5]
    assert assessments[0].nominal_duty == assessments[1].nominal_duty == prescribed
    assert assessments[0].delivery == assessments[1].delivery
    assert assessments[0].conditions != assessments[1].conditions
