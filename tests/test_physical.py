"""Public live/saved physical exchange witnesses; synthetic values, no policy claims."""

import json
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from fractions import Fraction

import polars as pl
import pytest

pytest.importorskip("taqsim")
from taqsim import ConservationQuantum, IntervalVolume, TimeAxis, WaterSystem
from taqsim.constituents import (
    Composition,
    Concentration,
    ConservativeTransport,
    Constituent,
    ConstituentInput,
    DomainSupport,
    InputMetadata,
    LocationMapping,
    ProcessState,
    RunMetadata,
)
from taqsim.persistence import load_run
from taqsim.physical_results import Balance, PhysicalSample, QualityState, TransportResult

from fishy.evidence import CorrectionState, ProductionMethod, Provenance
from fishy.flows import Presence
from fishy.physical import ExchangeView, PhysicalProjection, TimeInterpretation
from fishy.spatial import CalculationSection, Location, Reach, WaterBody


def location():
    return Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "map-1")


def provenance():
    return Provenance(
        "synthetic inputs",
        "managed",
        None,
        "taqsim-pinned",
        "1",
        "1",
        ProductionMethod.SIMULATED,
        CorrectionState.ORIGINAL,
    )


def projection(result, **kwargs):
    return PhysicalProjection(
        result, location(), "outlet", provenance(), ExchangeView.INCOMING, TimeInterpretation.UTC, **kwargs
    )


def model(volumes=(129600.0, 302400.0), support=DomainSupport.SUPPORTED):
    axis = TimeAxis("2020-02-28", len(volumes))
    model = WaterSystem(time=axis, quantum=ConservationQuantum.LITRE)
    model.source(
        "source",
        IntervalVolume(
            pl.DataFrame(
                {"time": [axis.datetime_at(i).replace(tzinfo=None) for i in range(len(volumes))], "value": volumes}
            ),
            "m3",
            "1d",
            "0.001 m3",
        ),
    )
    model.reach("reach", "source", "outlet")
    model.configure_transport(
        ConservativeTransport(
            (Constituent("salt", "NaCl", "as NaCl"), Constituent("chloride", "Cl-", "as Cl")),
            boundaries={
                "source": tuple(
                    Composition((ConstituentInput("salt", concentration=Concentration("0.5")),)) for _ in volumes
                )
            },
            metadata=RunMetadata(scenario="managed", support=support),
            location_mappings=(LocationMapping("outlet", "river", "section", "map-1"),),
            process_states=(
                ProcessState(
                    "stage",
                    "reach",
                    0,
                    Decimal("-1.25"),
                    "m",
                    "datum-relative",
                    InputMetadata(
                        source="hydraulics", version="1", owner="specialist", support=DomainSupport.SUPPORTED
                    ),
                ),
            ),
        )
    )
    return model.build().run(bytes(16))


def test_live_and_saved_exact_delivery_and_metadata(tmp_path):
    live = model()
    path = tmp_path / "run.json"
    live.save(path)
    for run in (live, load_run(path)):
        adapter = projection(run.physical)
        assert [sample.value.value for sample in adapter.flows()] == [Fraction(3, 2), Fraction(7, 2)]
        assert adapter.flows()[1].interval.start.day == 29
        assert json.loads(adapter.document_json) == live.physical.to_dict()
        state = adapter.result.metadata["inputs"]["process_states"][0]
        assert state["value"] == "-1.25"
        assert state["metadata"]["owner"] == "specialist"
        assert state["metadata"]["support"] == "supported"
        assert adapter.flows()[0].provenance.dependencies[-1].endswith(live.physical.digest)
        assert adapter.result.basin_balances
        salt = adapter.constituent("salt", chemical_form="NaCl", reporting_basis="as NaCl")
        assert salt.mass_kg == 216000
        assert salt.water.value == 432000
        assert salt.concentration_kg_m3 == Fraction(1, 2)
        missing = adapter.constituent("chloride", chemical_form="Cl-", reporting_basis="as Cl")
        assert missing.presence is Presence.MISSING
        assert missing.concentration_kg_m3 is None
        assert adapter.flows()[0].presence is Presence.PRESENT


def test_zero_missing_outside_absent_and_invalid_basis():
    adapter = projection(model((0.0, 86400.0)).physical)
    assert adapter.flows((0,))[0].value.value == 0
    assert adapter.constituent("salt", chemical_form="NaCl", reporting_basis="as NaCl", stop=1).presence is Presence.DRY
    assert adapter.flows((-1, 2))[0].presence is Presence.OUTSIDE_HORIZON
    assert (
        adapter.constituent("unknown", chemical_form="unknown", reporting_basis="unknown").presence is Presence.ABSENT
    )
    with pytest.raises(ValueError, match="basis"):
        adapter.constituent("salt", chemical_form="NaCl", reporting_basis="as Cl")
    with pytest.raises(TypeError, match="ExchangeView"):
        replace(adapter, view="storage")
    with pytest.raises(TypeError, match="UTC"):
        replace(adapter, time_interpretation=None)
    with pytest.raises(ValueError, match="scenario"):
        replace(adapter, provenance=replace(provenance(), scenario="different"))
    with pytest.raises(ValueError, match="mapping"):
        replace(adapter, location=replace(location(), mapping_version="map-2"))
    with pytest.raises(ValueError, match="observations"):
        replace(adapter, provenance=replace(provenance(), production_method=ProductionMethod.OBSERVED))


def exact_result(samples, balances=()):
    return TransportResult(
        TimeAxis("2020-01-01", len(samples)),
        Decimal("0.001"),
        (Constituent("salt", "NaCl", "as NaCl", Decimal("0.001")),),
        {"outlet": samples},
        {"outlet": samples},
        {},
        (),
        balances,
        (),
        {},
    )


def test_balance_failure_keeps_numeric_water_without_quality_pass():
    samples = (PhysicalSample("outlet", 0, 10000, {"salt": 5000}, {"salt": QualityState.SUPPORTED}, {}),)
    water_failed = projection(exact_result(samples, (Balance("outlet", 0, "water", 0, 0, 10, 9),)))
    assert water_failed.flows()[0].presence is Presence.UNSUPPORTED
    assert water_failed.flows()[0].value.value == Fraction(10, 86400)
    assert water_failed.flows()[0].reasons
    assert (
        water_failed.constituent("salt", chemical_form="NaCl", reporting_basis="as NaCl").presence
        is Presence.UNSUPPORTED
    )
    salt_failed = projection(exact_result(samples, (Balance("outlet", 0, "salt", 0, 0, 10, 9),)))
    assert salt_failed.flows()[0].presence is Presence.PRESENT
    assert salt_failed.constituent("salt", chemical_form="NaCl", reporting_basis="as NaCl").concentration_kg_m3 is None


def test_mass_water_aggregation_not_mean_concentration_and_huge_counts():
    samples = tuple(
        PhysicalSample("outlet", i, water, {"salt": mass}, {"salt": QualityState.SUPPORTED}, {})
        for i, (water, mass) in enumerate(((10000, 8000), (5000, 1000)))
    )
    aggregate = projection(exact_result(samples)).constituent("salt", chemical_form="NaCl", reporting_basis="as NaCl")
    assert aggregate.concentration_kg_m3 == Fraction(3, 5)
    huge = 10**50 + 3
    sample = PhysicalSample("outlet", 0, huge, {"salt": 1}, {"salt": QualityState.SUPPORTED}, {})
    assert projection(exact_result((sample,))).flows()[0].value.value == Fraction(huge, 86400000)
    missing = replace(sample, water_count=None, water_quality=QualityState.MISSING, water_reason="missing input")
    assert projection(exact_result((missing,))).flows()[0].presence is Presence.MISSING


def test_base_and_physical_module_import_without_simulator():
    import subprocess
    import sys

    script = """
import sys
class RefuseSimulator:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('taqsim', 'incidence'):
            raise ImportError('simulator deliberately unavailable')
sys.meta_path.insert(0, RefuseSimulator())
import fishy
import fishy.physical
import fishy.duties
assert 'taqsim' not in sys.modules
"""
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr


def test_independent_constituent_survives_failed_imported_account(tmp_path):
    from taqsim.constituents import ProcessAccount

    axis = TimeAxis("2020-01-01", 1)
    system = WaterSystem(time=axis, quantum=ConservationQuantum.LITRE)
    system.source(
        "source",
        IntervalVolume(pl.DataFrame({"time": [datetime(2020, 1, 1)], "value": [10.0]}), "m3", "1d", "0.001 m3"),
    )
    system.reach("reach", "source", "outlet")
    system.configure_transport(
        ConservativeTransport(
            (Constituent("salt", "NaCl", "as NaCl"), Constituent("sulphate", "SO4", "as SO4")),
            boundaries={
                "source": (
                    Composition(
                        (
                            ConstituentInput("salt", concentration=Concentration("0.5")),
                            ConstituentInput("sulphate", concentration=Concentration("0.2")),
                        )
                    ),
                )
            },
            metadata=RunMetadata(scenario="managed"),
            process_accounts=(
                ProcessAccount(
                    "specialist",
                    "reach",
                    0,
                    "salt",
                    1,
                    0,
                    0,
                    0,
                    InputMetadata(source="import", version="1", owner="specialist"),
                ),
            ),
        )
    )
    run = system.build().run(bytes(16))
    path = tmp_path / "independent.json"
    run.save(path)
    for result in (run.physical, load_run(path).physical):
        adapter = projection(result)
        assert adapter.flows()[0].presence is Presence.PRESENT
        assert (
            adapter.constituent("salt", chemical_form="NaCl", reporting_basis="as NaCl").presence
            is Presence.UNSUPPORTED
        )
        sulphate = adapter.constituent("sulphate", chemical_form="SO4", reporting_basis="as SO4")
        assert sulphate.presence is Presence.PRESENT
        assert sulphate.concentration_kg_m3 == Fraction(1, 5)
        assert adapter.result.process_balances[0].residual == 1


def test_projection_hashes_complete_physical_document_once(monkeypatch):
    original = TransportResult.digest.fget
    calls = []

    def counted_digest(result):
        calls.append(result)
        return original(result)

    monkeypatch.setattr(TransportResult, "digest", property(counted_digest))
    physical = model().physical
    adapter = projection(physical)
    first = adapter.flows()
    second = adapter.flows()
    assert first == second
    assert [sample.value.value for sample in first] == [Fraction(3, 2), Fraction(7, 2)]
    assert len(calls) <= 1
    assert all(result is physical for result in calls)


def assess_samples(samples, targets):
    from fishy.duties import Delivery, DutyApplicability, Obligation, SuppliedDuty, assess_duty
    from fishy.flows import FlowSample
    from fishy.quantities import Flow

    duty = SuppliedDuty(
        "supplied",
        "1",
        "synthetic independent schedule",
        DutyApplicability.HYPOTHETICAL,
        tuple(
            Obligation(FlowSample(sample.location, sample.interval, Flow(target), Presence.PRESENT, provenance()), "1")
            for sample, target in zip(samples, targets, strict=True)
        ),
        "synthetic fixture",
    )
    return assess_duty(duty, tuple(Delivery(sample, "1") for sample in samples))


def test_live_saved_supplied_duty_shortfalls(tmp_path):
    from fishy.evidence import CheckFinding, Completeness

    live = model()
    path = tmp_path / "duty.json"
    live.save(path)
    for run in (live, load_run(path)):
        result = assess_samples(projection(run.physical).flows(), (2, 3))
        assert [row.shortfall.value for row in result.intervals] == [Fraction(1, 2), 0]
        assert result.known_shortfall_volume.value == 43200
        assert result.summary.finding is CheckFinding.FAIL
        assert result.summary.completeness is Completeness.COMPLETE


def test_unavailable_physical_delivery_cannot_pass_supplied_duty():
    from fishy.evidence import CheckFinding, Completeness

    run = model((0.0, 86400.0))
    physical = replace(
        run.physical, basin_balances=(*run.physical.basin_balances, Balance("basin", 1, "water", 0, 0, 2, 1))
    )
    samples = projection(physical).flows((0, 1, 2))
    assert samples[0].presence is Presence.PRESENT
    assert samples[0].value.value == 0
    assert samples[1].presence is Presence.UNSUPPORTED
    assert samples[1].value.value == 1
    assert samples[2].presence is Presence.OUTSIDE_HORIZON
    result = assess_samples(samples, (2, 0, 0))
    assert [row.numerical.finding for row in result.intervals] == [
        CheckFinding.FAIL,
        CheckFinding.UNKNOWN,
        CheckFinding.UNKNOWN,
    ]
    assert result.known_shortfall_volume.value == 172800
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    unavailable = assess_samples(samples[1:], (0, 0))
    assert unavailable.summary.finding is CheckFinding.UNKNOWN


def test_global_physical_domain_support_cannot_pass_duty(tmp_path):
    from fishy.evidence import CheckFinding, Completeness

    live = model(support=DomainSupport.UNSUPPORTED)
    path = tmp_path / "unsupported.json"
    live.save(path)
    for run in (live, load_run(path)):
        samples = projection(run.physical).flows()
        assert all(sample.presence is Presence.UNSUPPORTED for sample in samples)
        assert [sample.value.value for sample in samples] == [Fraction(3, 2), Fraction(7, 2)]
        result = assess_samples(samples, (0, 0))
        assert result.summary.finding is CheckFinding.UNKNOWN
        assert result.summary.completeness is Completeness.INCOMPLETE


def test_simulation_aggregation_cannot_become_observed_even_through_imported_aggregate():
    from fishy.flows import aggregate_flow

    simulated = projection(model().physical).flows()
    observed_provenance = replace(simulated[0].provenance, production_method=ProductionMethod.OBSERVED)
    with pytest.raises(ValueError, match="non-observed contributors"):
        aggregate_flow(simulated, provenance=observed_provenance)
    imported = aggregate_flow(
        simulated, provenance=replace(simulated[0].provenance, production_method=ProductionMethod.IMPORTED)
    )
    with pytest.raises(ValueError, match="non-observed contributors"):
        aggregate_flow((imported,), provenance=observed_provenance)
    with pytest.raises(ValueError, match="non-observed contributors"):
        replace(imported, provenance=observed_provenance)


def test_excluded_warmup_constituent_retains_amounts_but_cannot_be_supported():
    adapter = projection(model().physical)
    adapter = replace(adapter, provenance=replace(adapter.provenance, excluded_warmup=(adapter.interval(0),)))
    salt = adapter.constituent("salt", chemical_form="NaCl", reporting_basis="as NaCl")
    assert salt.presence is Presence.UNSUPPORTED
    assert salt.concentration_kg_m3 is None
    assert salt.mass_kg == 216000
    assert salt.water is not None and salt.water.value == 432000
    assert salt.interval.start == adapter.interval(0).start
    assert salt.interval.end == adapter.interval(1).end
    assert "warm-up" in " ".join(salt.reasons)
    later = adapter.constituent("salt", chemical_form="NaCl", reporting_basis="as NaCl", start=1)
    assert later.presence is Presence.PRESENT
    assert later.concentration_kg_m3 == Fraction(1, 2)
