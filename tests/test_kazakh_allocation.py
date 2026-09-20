from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction

import pytest

from fishy.evidence import (
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    ScientificAdequacy,
    UseRestriction,
)
from fishy.flows import FlowSample, Presence
from fishy.kazakh_allocation import (
    AllocationRoute,
    AllocationStatus,
    AnnualQuantile,
    DesignClass,
    NaturalAnnualReference,
    NaturalExceedance,
    ObservationRoute,
    initial_allocation,
)
from fishy.quantities import Flow, Volume
from fishy.seasonal_allocation import (
    ScheduleStage,
    SeasonalShape,
    ShapeChoice,
    ShapeOrdinate,
    appendix1_report,
    seasonal_schedule,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

YEAR = Interval(datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC))
HISTORY = Interval(datetime(1990, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC))
LOCATION = Location(Reach("reach", "v1", WaterBody("river-body", "v1")), CalculationSection("section", "v1"), "map1")
PROVENANCE = Provenance(
    "synthetic reference",
    "scenario1",
    "member1",
    "test",
    "data1",
    "config1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
    ReferenceKind.PRESENT_CLIMATE_NATURAL,
)


def evidence(product, period=HISTORY, use="initial_allocation", provenance=PROVENANCE, location=LOCATION):
    return EvidenceFindings(
        EvidenceScope(product, location.reach.identifier, provenance.reference_member, period, use),
        provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("synthetic only",),
    )


def reference(values=(100, 80, 60, 40), route=ObservationRoute.ADEQUATE):
    return NaturalAnnualReference(
        LOCATION,
        HISTORY,
        tuple(
            AnnualQuantile(p, Volume(v * 1_000_000))
            for p, v in zip(
                (NaturalExceedance.P50, NaturalExceedance.P75, NaturalExceedance.P90, NaturalExceedance.P97),
                values,
                strict=True,
            )
        ),
        route,
        PROVENANCE,
        evidence("natural_annual_reference"),
    )


def shape(probability, values):
    step = (YEAR.end - YEAR.start) / len(values)
    points = tuple(
        ShapeOrdinate(Interval(YEAR.start + i * step, YEAR.start + (i + 1) * step), Fraction(str(v)))
        for i, v in enumerate(values)
    )
    return SeasonalShape(
        LOCATION,
        YEAR,
        probability,
        points,
        PROVENANCE,
        evidence(f"seasonal_shape_P{probability.value}", YEAR, "seasonal_allocation"),
    )


@pytest.mark.parametrize(
    "design,volume,alpha",
    zip(DesignClass, (100, 80, 60, 40), (1, Fraction(4, 5), Fraction(3, 5), Fraction(2, 5)), strict=True),
)
def test_both_initial_routes_not_second_reduction(design, volume, alpha):
    ref = reference()
    shifted = initial_allocation(ref, design, AllocationRoute.PROBABILITY_SHIFT)
    coefficient = initial_allocation(ref, design, AllocationRoute.MEDIAN_NORMALISED)
    assert shifted.volume == coefficient.volume == Volume(volume * 1_000_000)
    assert coefficient.coefficient == alpha
    assert shifted.reference.evidence.official_admissibility is OfficialAdmissibility.PENDING


def test_zero_ratio_unidentified_but_independent_shift_survives():
    ref = reference((0, 0, 0, 0))
    assert initial_allocation(ref, DesignClass.DRY, AllocationRoute.PROBABILITY_SHIFT).volume == Volume(0)
    assert (
        initial_allocation(ref, DesignClass.DRY, AllocationRoute.MEDIAN_NORMALISED).status
        is AllocationStatus.UNRESOLVED
    )
    assert (
        initial_allocation(reference((100, 0, 0, 0)), DesignClass.DRY, AllocationRoute.MEDIAN_NORMALISED).coefficient
        == 0
    )
    with pytest.raises(ValueError):
        Volume(-1)


def test_observation_routes_and_exact_evidence_scope():
    ref = reference(route=ObservationRoute.INSUFFICIENT)
    assert initial_allocation(ref, DesignClass.WET, AllocationRoute.PROBABILITY_SHIFT).volume is None
    ref = replace(ref, reconstruction=evidence("annual_monthly_reconstruction"))
    assert initial_allocation(ref, DesignClass.WET, AllocationRoute.PROBABILITY_SHIFT).volume == Volume(100_000_000)
    ref = replace(
        ref, evidence=replace(ref.evidence, restrictions=(UseRestriction("not sizing", ("initial_allocation",)),))
    )
    assert initial_allocation(ref, DesignClass.WET, AllocationRoute.PROBABILITY_SHIFT).volume is None
    absent = reference(route=ObservationRoute.ABSENT)
    assert (
        initial_allocation(absent, DesignClass.WET, AllocationRoute.PROBABILITY_SHIFT).status
        is AllocationStatus.FURTHER_STUDY
    )
    wrong = replace(reference(), evidence=evidence("other_product"))
    assert initial_allocation(wrong, DesignClass.WET, AllocationRoute.PROBABILITY_SHIFT).volume is None


@pytest.mark.parametrize(
    "choice,probability,values,expected",
    [
        (ShapeChoice.DESIGN_CLASS, NaturalExceedance.P25, (1.6, 1.2, 0.8, 0.4), (16, 12, 8, 4)),
        (ShapeChoice.SHIFTED_CLASS, NaturalExceedance.P50, (0.4, 0.8, 1.2, 1.6), (4, 8, 12, 16)),
    ],
)
def test_explicit_shape_operators(choice, probability, values, expected):
    ref = replace(reference(), quantiles=(AnnualQuantile(NaturalExceedance.P50, Volume(10 * YEAR.seconds)),))
    initial = initial_allocation(ref, DesignClass.WET, AllocationRoute.PROBABILITY_SHIFT)
    result = seasonal_schedule(initial, YEAR, choice, shape(probability, values))
    values = []
    for sample in result.samples:
        assert sample.value is not None
        values.append(sample.value.value)
    assert tuple(values) == expected
    report = appendix1_report(initial, YEAR, result.samples, ScheduleStage.INITIAL)
    assert report.annual.volume == initial.volume
    assert report.annual.flow == Flow(10)
    assert report.monthly[0].presence is Presence.UNSUPPORTED  # quarterly is not monthly


def test_missing_choice_pattern_and_unsupported_pattern_keep_annual():
    initial = initial_allocation(reference(), DesignClass.WET, AllocationRoute.PROBABILITY_SHIFT)
    result = seasonal_schedule(initial, YEAR, None, None)
    assert result.initial.volume == Volume(100_000_000)
    assert not result.samples
    pattern = shape(NaturalExceedance.P50, (1, 1, 1, 1))
    pattern = replace(pattern, evidence=replace(pattern.evidence, scientific_adequacy=ScientificAdequacy.UNKNOWN))
    assert not seasonal_schedule(initial, YEAR, ShapeChoice.SHIFTED_CLASS, pattern).samples
    with pytest.raises(ValueError, match="mean"):
        shape(NaturalExceedance.P50, (1, 1, 1, 2))
    with pytest.raises(ValueError):
        shape(NaturalExceedance.P50, (1, 1, 1, -1))


DEFAULT_FLOW = Flow(10)


def monthly_samples(flow=DEFAULT_FLOW):
    return tuple(
        FlowSample(
            LOCATION,
            Interval(datetime(2024, m, 1, tzinfo=UTC), datetime(2024 + (m == 12), m % 12 + 1, 1, tzinfo=UTC)),
            flow,
            Presence.PRESENT,
            PROVENANCE,
        )
        for m in range(1, 13)
    )


def test_appendix1_leap_months_corrected_volume_no_renormalisation():
    initial = initial_allocation(reference(), DesignClass.WET, AllocationRoute.PROBABILITY_SHIFT)
    report = appendix1_report(initial, YEAR, monthly_samples(), ScheduleStage.CORRECTED)
    assert report.monthly[1].volume == Volume(10 * 29 * 86400)
    assert report.annual.volume == Volume(10 * 366 * 86400)
    assert report.annual.million_m3 == Fraction(10 * 366 * 86400, 1_000_000)
    assert report.annual.volume != report.initial.volume
    shares = []
    for cell in report.monthly:
        assert cell.annual_share_percent is not None
        shares.append(cell.annual_share_percent)
    assert sum(shares) == 100
    assert report.location == LOCATION
    assert report.design is DesignClass.WET


def test_zero_missing_unsupported_outside_and_partial_are_distinct():
    initial = initial_allocation(reference((0, 0, 0, 0)), DesignClass.WET, AllocationRoute.PROBABILITY_SHIFT)
    report = appendix1_report(initial, YEAR, monthly_samples(Flow(0)), ScheduleStage.INITIAL)
    assert report.annual.volume == Volume(0)
    assert all(c.annual_share_percent is None for c in (*report.monthly, report.annual))
    assert report.monthly[0].presence is Presence.PRESENT
    for state in (Presence.MISSING, Presence.UNSUPPORTED, Presence.OUTSIDE_HORIZON, Presence.ABSENT):
        samples = tuple(
            replace(s, value=None, presence=state, reasons=("supplied unavailable",)) for s in monthly_samples()
        )
        report = appendix1_report(initial, YEAR, samples, ScheduleStage.CORRECTED)
        assert report.annual.presence is state
        assert report.annual.volume is None
    report = appendix1_report(initial, YEAR, monthly_samples()[:-1], ScheduleStage.CORRECTED)
    assert report.annual.volume is None
    assert report.monthly[0].volume is not None
    assert report.monthly[0].annual_share_percent is None
    assert report.monthly[-1].presence is Presence.MISSING


def test_invalid_inputs_identity_immutability_warmup():
    initial = initial_allocation(reference(), DesignClass.WET, AllocationRoute.PROBABILITY_SHIFT)
    with pytest.raises(ValueError, match="duplicate"):
        replace(reference(), quantiles=reference().quantiles * 2)
    with pytest.raises(ValueError, match="increase"):
        reference((1, 2, 3, 4))
    with pytest.raises(ValueError):
        appendix1_report(initial, YEAR, monthly_samples() * 2, ScheduleStage.INITIAL)
    with pytest.raises(ValueError, match="identity"):
        appendix1_report(
            initial,
            YEAR,
            tuple(replace(s, provenance=replace(PROVENANCE, scenario="different")) for s in monthly_samples()),
            ScheduleStage.CORRECTED,
        )
    samples = monthly_samples()
    changed = replace(samples[0], value=Flow(11))
    assert samples[0].value == Flow(10)
    assert changed.value == Flow(11)
    warm = tuple(replace(s, provenance=replace(PROVENANCE, excluded_warmup=(YEAR,))) for s in samples)
    assert appendix1_report(initial, YEAR, warm, ScheduleStage.INITIAL).annual.volume is None
    with pytest.raises(ValueError):
        Flow(float("nan"))


def test_single_design_class_carrier_and_invalid_domain():
    from fishy.design_conditions import DesignClass as SharedDesignClass

    assert SharedDesignClass is DesignClass
    assert tuple(c.value for c in DesignClass) == (25, 50, 75, 95)
    with pytest.raises(ValueError):
        DesignClass(90)
    with pytest.raises(TypeError):
        initial_allocation(reference(), 25, AllocationRoute.PROBABILITY_SHIFT)  # ty: ignore[invalid-argument-type]


def test_receiving_parent_transfer_success_missing_and_incompatible():
    from fishy.basin import Basin, DonorRelation, PreparedTopology, River, RiverConnection, SectionContext
    from fishy.kazakh_allocation import DonorChoice, InitialCoefficient, transfer_allocation

    main = River("main", "v1", 0)
    tributary = River("tributary", "v1", 1)
    donor = Location(Reach("main-reach", "v1", WaterBody("main-body", "v1")), CalculationSection("mouth", "v1"), "map1")
    topology = PreparedTopology(
        Basin("basin", "v1"),
        "topology1",
        (main, tributary),
        (RiverConnection(tributary, main),),
        (SectionContext(main, donor, None), SectionContext(tributary, LOCATION, donor)),
    )
    ref = reference(route=ObservationRoute.ABSENT)
    relation = DonorRelation(tributary, main, evidence("receiving_parent_transfer"))
    coefficient = InitialCoefficient(
        DesignClass.MEDIUM,
        Fraction(4, 5),
        donor,
        evidence("initial_coefficient_P50", use="initial_allocation_transfer", location=donor),
    )
    result = transfer_allocation(
        ref, DesignClass.MEDIUM, topology, tributary, relation, coefficient, DonorChoice.RECEIVING_PARENT
    )
    assert result.volume == Volume(80_000_000)
    assert result.status is AllocationStatus.SUPPORTED
    assert len(result.supporting_evidence) == 2
    for rel, coeff, choice in (
        (None, coefficient, DonorChoice.RECEIVING_PARENT),
        (relation, None, DonorChoice.RECEIVING_PARENT),
        (relation, coefficient, None),
    ):
        result = transfer_allocation(ref, DesignClass.MEDIUM, topology, tributary, rel, coeff, choice)
        assert result.status is AllocationStatus.FURTHER_STUDY
        assert result.volume is None
    bad = replace(
        coefficient,
        evidence=replace(
            coefficient.evidence, scope=replace(coefficient.evidence.scope, product="post_spawning_coefficient")
        ),
    )
    assert (
        transfer_allocation(
            ref, DesignClass.MEDIUM, topology, tributary, relation, bad, DonorChoice.RECEIVING_PARENT
        ).volume
        is None
    )
    with pytest.raises(ValueError, match="donor location"):
        transfer_allocation(
            ref,
            DesignClass.MEDIUM,
            topology,
            tributary,
            relation,
            replace(coefficient, donor=LOCATION),
            DonorChoice.RECEIVING_PARENT,
        )


def test_reporting_identities_and_meaningful_annual_only_result():
    from fishy.basin import Basin, River
    from fishy.seasonal_allocation import ReportingIdentity

    initial = initial_allocation(reference(), DesignClass.WET, AllocationRoute.PROBABILITY_SHIFT)
    identity = ReportingIdentity(
        Basin("basin-code", "rev1"), River("river-code", "rev2", 0), LOCATION, "district-section-code"
    )
    complete = appendix1_report(initial, YEAR, monthly_samples(), ScheduleStage.CORRECTED, identity)
    assert complete.identity == identity
    assert not complete.limitations
    partial = appendix1_report(initial, YEAR, (), ScheduleStage.INITIAL, identity)
    assert partial.initial.volume == Volume(100_000_000)
    assert partial.annual.volume is None
    assert all(c.presence is Presence.MISSING for c in partial.monthly)


def test_scaled_observed_pattern_cannot_become_observed_discharge():
    initial = initial_allocation(reference(), DesignClass.WET, AllocationRoute.PROBABILITY_SHIFT)
    pattern = shape(NaturalExceedance.P50, (1, 1, 1, 1))
    observed = replace(PROVENANCE, production_method=ProductionMethod.OBSERVED)
    pattern = replace(pattern, provenance=observed, evidence=replace(pattern.evidence, provenance=observed))
    result = seasonal_schedule(initial, YEAR, ShapeChoice.SHIFTED_CLASS, pattern)
    assert result.samples
    assert all(s.provenance.production_method is not ProductionMethod.OBSERVED for s in result.samples)
    assert result.shape is not None
    assert result.shape.provenance.production_method is ProductionMethod.OBSERVED
    assert any("synthetic only" in reason for reason in result.samples[0].provenance.limitations)
    assert any("accepted as indicative" in reason for reason in result.samples[0].provenance.limitations)
    report = appendix1_report(initial, YEAR, result.samples, ScheduleStage.INITIAL)
    assert any("synthetic only" in reason for reason in report.samples[0].provenance.limitations)
