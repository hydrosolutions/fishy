"""Real live/saved interval water projects into complete-year IHA."""

from datetime import datetime

import polars as pl
import pytest
from polars.testing import assert_frame_equal

pytest.importorskip("taqsim")
from taqsim import ConservationQuantum, IntervalVolume, TimeAxis, WaterSystem
from taqsim.constituents import (
    Composition,
    Concentration,
    ConservativeTransport,
    Constituent,
    ConstituentInput,
    LocationMapping,
    RunMetadata,
)
from taqsim.persistence import load_run

from fishy.diagnostics.iha import CentralStatistic, IHAProfile, PulseThresholds, RateBoundary
from fishy.diagnostics.records import flow_indicators
from fishy.evidence import CorrectionState, ProductionMethod, Provenance
from fishy.physical import ExchangeView, PhysicalProjection, TimeInterpretation
from fishy.quantities import Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody


def test_live_saved_calendar_year_physical_path(tmp_path):
    axis = TimeAxis("2020-01-01", 366)
    # Explicit366 daily interval volumes at constant2m3/s. Leap day remains.
    system = WaterSystem(time=axis, quantum=ConservationQuantum.LITRE)
    system.source(
        "source",
        IntervalVolume(
            pl.DataFrame(
                {"time": [axis.datetime_at(i).replace(tzinfo=None) for i in range(366)], "value": [172800.0] * 366}
            ),
            "m3",
            "1d",
            "0.001 m3",
        ),
    )
    system.reach("reach", "source", "outlet")
    system.configure_transport(
        ConservativeTransport(
            (Constituent("salt", "NaCl", "as NaCl"),),
            boundaries={
                "source": tuple(
                    Composition((ConstituentInput("salt", concentration=Concentration("0.5")),)) for _ in range(366)
                )
            },
            metadata=RunMetadata(scenario="managed"),
            location_mappings=(LocationMapping("outlet", "river", "section", "map-1"),),
        )
    )
    live = system.build().run(bytes(16))
    path = tmp_path / "year.json"
    live.save(path)
    location = Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "map-1")
    provenance = Provenance(
        "synthetic inputs",
        "managed",
        None,
        "taqsim-pinned",
        "1",
        "1",
        ProductionMethod.SIMULATED,
        CorrectionState.ORIGINAL,
    )
    profile = IHAProfile(CentralStatistic.MEAN, PulseThresholds(Flow(2), Flow(2)), RateBoundary.WITHIN_YEAR)
    outputs = []
    for run in (live, load_run(path)):
        projection = PhysicalProjection(
            run.physical, location, "outlet", provenance, ExchangeView.INCOMING, TimeInterpretation.UTC
        )
        record = flow_indicators(projection.flows(), profile)
        outputs.append(record.annual)
        assert record.source_samples[59].interval.start.date() == datetime(2020, 2, 29).date()
        assert record.annual.filter(pl.col("parameter") == "monthly_flow_01")["value"].item() == 2
        assert record.annual.filter(pl.col("parameter") == "base_flow_index")["value"].item() == 1
        assert record.annual.filter(pl.col("parameter") == "zero_flow_days")["value"].item() == 0
        assert record.annual.filter(pl.col("parameter") == "rise_rate")["value"].item() is None
        assert record.provenance.production_method is ProductionMethod.SIMULATED
        assert record.provenance.dependencies[-1].endswith(live.physical.digest)
    assert_frame_equal(outputs[0], outputs[1])
