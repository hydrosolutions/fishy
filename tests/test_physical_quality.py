"""Current realised conservative transport feeds configured quality, live and saved."""

from datetime import UTC, datetime
from fractions import Fraction

import polars as pl
import pytest

pytest.importorskip("taqsim")
from taqsim import ConservationQuantum, IntervalVolume, TimeAxis, WaterSystem, WaterVolume
from taqsim.constituents import (
    Composition,
    Concentration,
    ConservativeTransport,
    Constituent,
    ConstituentInput,
    DomainSupport,
    InputMetadata,
    LocationMapping,
    Mass,
    ProcessAccount,
    RunMetadata,
)
from taqsim.persistence import load_run
from taqsim.vocabulary import EvaporateThenRelease, Release, TravelDelay

from fishy.evidence import CheckFinding, Completeness, CorrectionState, ProductionMethod, Provenance
from fishy.flows import Presence
from fishy.physical import ExchangeView, PhysicalProjection, TimeInterpretation
from fishy.quality import (
    ChemicalBehavior,
    ChemicalIdentity,
    Comparison,
    ProfileStatus,
    QualityProfile,
    QualityTarget,
    QualityValue,
    assess_quality,
    from_constituent_sample,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody


def location():
    return Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "map-1")


def provenance():
    return Provenance(
        "synthetic boundary inputs",
        "quality-example",
        None,
        "taqsim-396ad09",
        "1",
        "1",
        ProductionMethod.SIMULATED,
        CorrectionState.ORIGINAL,
    )


def project(result, model_location="outlet", view=ExchangeView.INCOMING):
    return PhysicalProjection(result, location(), model_location, provenance(), view, TimeInterpretation.UTC)


def add_source(model, name, volumes):
    frame = pl.DataFrame(
        {
            "time": [model.time.datetime_at(i).replace(tzinfo=None) for i in range(len(volumes))],
            "value": [float(value) for value in volumes],
        }
    )
    model.source(name, IntervalVolume(frame, "m3", model.time.frequency, "0.001 m3"))


def mixing_run(frequency="1d", support=DomainSupport.SUPPORTED, process_accounts=()):
    """Two realised sources mix in one compartment; chloride intentionally unknown."""
    model = WaterSystem(time=TimeAxis("2020-02-29", 1, frequency), quantum=ConservationQuantum.LITRE)
    add_source(model, "background", (10,))
    add_source(model, "arrival", (5,))
    model.reach("background-reach", "background", "mix")
    model.reach("arrival-reach", "arrival", "mix")
    model.reach("mix", "background-reach", "outlet")
    model.configure_transport(
        ConservativeTransport(
            (
                Constituent("salt", "NaCl", "as NaCl"),
                Constituent("chloride", "Cl-", "as Cl"),
                Constituent("sulphate", "SO4", "as SO4"),
            ),
            boundaries={
                name: (
                    Composition(
                        (
                            ConstituentInput("salt", concentration=Concentration(value)),
                            ConstituentInput("sulphate", concentration=Concentration("0.2")),
                        )
                    ),
                )
                for name, value in (("background", "0.8"), ("arrival", "0.2"))
            },
            metadata=RunMetadata(scenario="quality-example", support=support),
            location_mappings=(LocationMapping("outlet", "river", "section", "map-1"),),
            process_accounts=process_accounts,
        )
    )
    return model.build().run(bytes(16))


SALT = ChemicalIdentity("salt", "NaCl", "as NaCl", "dissolved", ChemicalBehavior.CONSERVATIVE)
CHLORIDE = ChemicalIdentity("chloride", "Cl-", "as Cl", "dissolved", ChemicalBehavior.CONSERVATIVE)
BASIS = "interval volume-weighted transfer concentration"


def profile(interval, missing=False, chemical=SALT):
    targets = (
        QualityTarget(
            "salt-upper",
            chemical,
            Comparison.LE,
            QualityValue(500, "mg/l"),
            BASIS,
            "synthetic threshold; not an adopted limit",
        ),
    )
    if missing:
        targets += (
            QualityTarget(
                "chloride-upper",
                CHLORIDE,
                Comparison.LE,
                QualityValue(100, "mg/l"),
                BASIS,
                "synthetic missing-member check",
            ),
        )
    return QualityProfile(
        "physical-quality",
        "1",
        "synthetic",
        "configured quality example",
        "1",
        "illustration",
        "physical quality screen",
        location(),
        interval,
        "quality-example",
        ProfileStatus.SCENARIO,
        tuple(target.identifier for target in targets),
        targets,
        "only the stated mixing section",
        "exact model counts are not measurement uncertainty",
        "explicit inclusive scenario",
    )


def assess(adapter, *, start=0, stop=None, missing=False):
    sample = adapter.constituent("salt", chemical_form="NaCl", reporting_basis="as NaCl", start=start, stop=stop)
    observations = (from_constituent_sample(sample, chemical=SALT, basis=BASIS),)
    if missing:
        chloride = adapter.constituent("chloride", chemical_form="Cl-", reporting_basis="as Cl", start=start, stop=stop)
        observations += (from_constituent_sample(chloride, chemical=CHLORIDE, basis=BASIS),)
    return sample, assess_quality(profile(sample.interval, missing), observations)


@pytest.mark.parametrize("frequency,seconds", [("1d", 86400), ("1h", 3600), ("2d", 172800)])
def test_a13_realised_mixing_live_saved_quality_failure(tmp_path, frequency, seconds):
    live = mixing_run(frequency)
    path = tmp_path / "mixed.taqsim"
    live.save(path)
    source_document = live.physical.to_dict()
    digest = live.physical.digest
    for run in (live, load_run(path)):
        adapter = project(run.physical)
        sample, result = assess(adapter)
        assert sample.water.value == 15
        assert sample.mass_kg == 9
        assert sample.concentration_kg_m3 == Fraction(3, 5)
        assert sample.interval.seconds == seconds
        assert sample.interval.start == datetime(2020, 2, 29, tzinfo=UTC)
        assert adapter.flows()[0].value.value == Fraction(15, seconds)
        assert result.results[0].lower == QualityValue(600, "mg/l").value
        assert result.results[0].target.limit == QualityValue(500, "mg/l")
        assert result.summary.finding is CheckFinding.FAIL
        assert result.summary.completeness is Completeness.COMPLETE
        assert run.physical.to_dict() == source_document
        assert run.physical.digest == digest
        assert result.results[0].observations[0].provenance.dependencies[-1] == f"taqsim-physical-sha256:{digest}"
        assert all(
            balance.residual == 0
            for balance in (*run.physical.balances, *run.physical.basin_balances)
            if balance.substance in ("water", "salt")
        )
        assert all(
            balance.residual is None for balance in run.physical.basin_balances if balance.substance == "chloride"
        )
        # The same realised water at the reach outlet has a different prepared view,
        # not stored inventory masquerading as a transfer.
        outgoing, outgoing_result = assess(project(run.physical, "mix", ExchangeView.OUTGOING))
        assert outgoing.mass_kg == sample.mass_kg
        assert outgoing_result.summary.finding is CheckFinding.FAIL
        assert run.physical.concentration("mix", 0, "salt", view="storage") is None


def test_a13_known_failure_survives_missing_required_constituent_live_saved(tmp_path):
    live = mixing_run()
    path = tmp_path / "incomplete.taqsim"
    live.save(path)
    for run in (live, load_run(path)):
        sample, result = assess(project(run.physical), missing=True)
        assert sample.mass_kg == 9
        assert [item.check.finding for item in result.results] == [CheckFinding.FAIL, CheckFinding.UNKNOWN]
        assert result.summary.finding is CheckFinding.FAIL
        assert result.summary.completeness is Completeness.INCOMPLETE
        assert result.results[1].observations[0].presence is Presence.MISSING


def test_a13_unsupported_domain_and_failed_account_do_not_certify(tmp_path):
    failed_account = ProcessAccount(
        "specialist",
        "outlet",
        0,
        "salt",
        1,
        0,
        0,
        0,
        InputMetadata(source="supplied failed account", version="1", owner="specialist"),
    )
    for name, run in (
        ("domain", mixing_run(support=DomainSupport.UNSUPPORTED)),
        ("account", mixing_run(process_accounts=(failed_account,))),
    ):
        path = tmp_path / f"{name}.taqsim"
        run.save(path)
        for value in (run, load_run(path)):
            sample, result = assess(project(value.physical))
            assert sample.presence is Presence.UNSUPPORTED
            assert result.summary.finding is CheckFinding.UNKNOWN
            assert result.summary.completeness is Completeness.INCOMPLETE


def test_realised_delayed_aggregate_uses_mass_water_not_mean_and_retains_presence(tmp_path):
    model = WaterSystem(time=TimeAxis("2020-02-28", 3), quantum=ConservationQuantum.LITRE)
    add_source(model, "source", (10, 5, 0))
    model.reach("transit", "source", "outlet", rule=TravelDelay(1))
    model.configure_transport(
        ConservativeTransport(
            (Constituent("salt", "NaCl", "as NaCl"),),
            boundaries={
                "source": tuple(Composition((ConstituentInput("salt", mass=Mass(mass)),)) for mass in (8, 1, 0))
            },
            metadata=RunMetadata(scenario="quality-example"),
        )
    )
    run = model.build().run(bytes(16))
    path = tmp_path / "delay.taqsim"
    run.save(path)
    for value in (run, load_run(path)):
        adapter = project(value.physical)
        first, _ = assess(adapter, start=1, stop=2)
        second, _ = assess(adapter, start=2, stop=3)
        aggregate, result = assess(adapter, start=1, stop=3)
        assert (first.concentration_kg_m3 + second.concentration_kg_m3) / 2 == Fraction(1, 2)
        assert aggregate.concentration_kg_m3 == Fraction(3, 5)
        assert result.summary.finding is CheckFinding.FAIL
        assert "aggregate loses within-interval resolution" in result.limitations
        for start, stop, presence in ((0, 1, Presence.DRY), (3, 4, Presence.OUTSIDE_HORIZON)):
            unavailable, unassessed = assess(adapter, start=start, stop=stop)
            assert unavailable.presence is presence
            assert unassessed.summary.finding is CheckFinding.UNKNOWN
        absent = adapter.constituent("chloride", chemical_form="Cl-", reporting_basis="as Cl")
        assert absent.presence is Presence.ABSENT
        absent_observation = from_constituent_sample(absent, chemical=CHLORIDE, basis=BASIS)
        assert (
            assess_quality(profile(absent.interval, chemical=CHLORIDE), (absent_observation,)).summary.finding
            is CheckFinding.UNKNOWN
        )
        with pytest.raises(ValueError, match="basis"):
            adapter.constituent("salt", chemical_form="NaCl", reporting_basis="as chloride")


def test_transferred_concentration_differs_from_final_storage_after_evaporation():
    model = WaterSystem(time=TimeAxis("2020-02-29", 1), quantum=ConservationQuantum.LITRE)
    add_source(model, "source", (0,))
    model.reach("release", "source", "store", initial_water=WaterVolume(10, "m3"), rule=Release(WaterVolume(4, "m3")))
    model.reach("store", "release", "outlet", rule=EvaporateThenRelease(WaterVolume(2, "m3"), WaterVolume(0, "m3")))
    model.configure_transport(
        ConservativeTransport(
            (Constituent("salt", "NaCl", "as NaCl"),),
            initial={"release": Composition((ConstituentInput("salt", mass=Mass(5)),))},
            boundaries={"source": (Composition((ConstituentInput("salt", mass=Mass(0)),)),)},
            metadata=RunMetadata(scenario="quality-example"),
        )
    )
    run = model.build().run(bytes(16))
    sample, result = assess(project(run.physical, "store"))
    assert sample.concentration_kg_m3 == Fraction(1, 2)
    assert result.summary.finding is CheckFinding.PASS
    assert run.physical.concentration("store", 0, "salt", view="storage") == 1


def test_independent_quality_survives_affected_constituent_balance_failure_live_saved(tmp_path):
    failed = ProcessAccount(
        "specialist",
        "outlet",
        0,
        "salt",
        1,
        0,
        0,
        0,
        InputMetadata(source="failed specialist salt account", version="1", owner="specialist"),
    )
    live = mixing_run(process_accounts=(failed,))
    path = tmp_path / "independent.taqsim"
    live.save(path)
    sulphate = ChemicalIdentity("sulphate", "SO4", "as SO4", "dissolved", ChemicalBehavior.CONSERVATIVE)
    for run in (live, load_run(path)):
        adapter = project(run.physical)
        salt_sample, salt_result = assess(adapter)
        assert salt_sample.presence is Presence.UNSUPPORTED
        assert salt_result.summary.finding is CheckFinding.UNKNOWN
        sample = adapter.constituent("sulphate", chemical_form="SO4", reporting_basis="as SO4")
        assert sample.presence is Presence.PRESENT
        assert sample.mass_kg == 3 and sample.concentration_kg_m3 == Fraction(1, 5)
        observed = from_constituent_sample(sample, chemical=sulphate, basis=BASIS)
        result = assess_quality(profile(sample.interval, chemical=sulphate), (observed,))
        assert result.summary.finding is CheckFinding.PASS
        assert result.summary.completeness is Completeness.COMPLETE
