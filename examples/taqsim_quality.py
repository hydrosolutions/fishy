"""main : SyntheticMixingInputs → LiveAndSavedQualityFindings.

Run: uv run --extra taqsim python examples/taqsim_quality.py --save mixed.taqsim
The saved physical document is optional and is not a restart checkpoint.
"""

import argparse
from pathlib import Path

import polars as pl
from taqsim import ConservationQuantum, IntervalVolume, TimeAxis, WaterSystem
from taqsim.constituents import (
    Composition,
    Concentration,
    ConservativeTransport,
    Constituent,
    ConstituentInput,
    RunMetadata,
)
from taqsim.persistence import load_run

from fishy.evidence import CorrectionState, ProductionMethod, Provenance
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


def main():
    parser = argparse.ArgumentParser(description="Synthetic physical-to-quality exchange")
    parser.add_argument("--save", type=Path, help="optional destination for the full saved physical run")
    args = parser.parse_args()
    axis = TimeAxis("2020-02-29", 1, "1h")
    model = WaterSystem(time=axis, quantum=ConservationQuantum.LITRE)
    for name, volume in (("background", 10.0), ("arrival", 5.0)):
        frame = pl.DataFrame({"time": [axis.datetime_at(0).replace(tzinfo=None)], "value": [volume]})
        model.source(name, IntervalVolume(frame, "m3", "1h", "0.001 m3"))
        model.reach(name + "-reach", name, "mix")
    model.reach("mix", "background-reach", "outlet")
    model.configure_transport(
        ConservativeTransport(
            (Constituent("salt", "NaCl", "as NaCl"),),
            boundaries={
                name: (Composition((ConstituentInput("salt", concentration=Concentration(value)),)),)
                for name, value in (("background", "0.8"), ("arrival", "0.2"))
            },
            metadata=RunMetadata(scenario="illustration"),
        )
    )
    live = model.build().run(bytes(16))
    runs = [("live", live)]
    if args.save is not None:
        if args.save.exists():
            raise FileExistsError("refusing to overwrite an existing saved run")
        live.save(args.save)
        runs.append(("saved", load_run(args.save)))
    location = Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("mixed-section", "1"), "map-1")
    provenance = Provenance(
        "synthetic boundary inputs",
        "illustration",
        None,
        "taqsim-396ad09",
        "1",
        "1",
        ProductionMethod.SIMULATED,
        CorrectionState.ORIGINAL,
    )
    chemical = ChemicalIdentity("salt", "NaCl", "as NaCl", "dissolved", ChemicalBehavior.CONSERVATIVE)
    basis = "interval volume-weighted transfer concentration"
    target = QualityTarget(
        "salt-upper", chemical, Comparison.LE, QualityValue(500, "mg/l"), basis, "synthetic upper limit"
    )
    digest = live.physical.digest
    for label, run in runs:
        adapter = PhysicalProjection(
            run.physical, location, "outlet", provenance, ExchangeView.INCOMING, TimeInterpretation.UTC
        )
        sample = adapter.constituent("salt", chemical_form="NaCl", reporting_basis="as NaCl")
        profile = QualityProfile(
            "physical-example",
            "1",
            "synthetic",
            "illustration",
            "1",
            "example",
            "quality screen",
            location,
            sample.interval,
            "illustration",
            ProfileStatus.SCENARIO,
            (target.identifier,),
            (target,),
            "only this section and hour",
            "exact counts; no uncertainty claim",
            "explicit inclusive scenario",
        )
        observation = from_constituent_sample(sample, chemical=chemical, basis=basis)
        result = assess_quality(profile, (observation,))
        assert run.physical.digest == digest
        assert sample.water is not None and sample.concentration_kg_m3 is not None
        flow = adapter.flows()[0].value
        assert flow is not None
        print(
            f"{label}: water={sample.water.value} m3; mass={sample.mass_kg} kg; concentration={sample.concentration_kg_m3 * 1000} mg/l"
        )
        print(
            f"{label}: duration={sample.interval.seconds} s; mean flow={flow.value} m3/s; 500 mg/l upper: {result.summary.finding.value}"
        )
    print("Physical source unchanged. Synthetic configured screen, not official compliance.")


if __name__ == "__main__":
    main()
