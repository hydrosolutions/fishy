"""physical_projection : TransportResult × Location × ExchangeView → AttributedFlowSamples.

The optional simulator is imported only when a projection is constructed. The
complete immutable source result retains precision, balances and specialist states.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import UTC
from enum import StrEnum
from fractions import Fraction
from typing import TYPE_CHECKING

from fishy.evidence import ProductionMethod, Provenance
from fishy.flows import FlowSample, Presence
from fishy.quantities import Volume, mean_discharge
from fishy.spatial import Location
from fishy.time import Interval

if TYPE_CHECKING:
    from taqsim.physical_results import TransportResult


class ExchangeView(StrEnum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class TimeInterpretation(StrEnum):
    UTC = "UTC"


@dataclass(frozen=True)
class ConstituentSample:
    """Exact aggregate mass/water and independent aqueous support, not a quality verdict."""

    constituent: str
    chemical_form: str
    reporting_basis: str
    interval: Interval
    location: Location
    mass_kg: Fraction | None
    water: Volume | None
    concentration_kg_m3: Fraction | None
    presence: Presence
    provenance: Provenance
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for value in (self.constituent, self.chemical_form, self.reporting_basis):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("constituent identity and chemical basis must be explicit")
        for value, kind in (
            (self.interval, Interval),
            (self.location, Location),
            (self.provenance, Provenance),
            (self.presence, Presence),
        ):
            if not isinstance(value, kind):
                raise TypeError("constituent evidence requires typed interval, location, provenance and presence")
        if self.water is not None and not isinstance(self.water, Volume):
            raise TypeError("constituent carrier requires Volume")
        for value in (self.mass_kg, self.concentration_kg_m3):
            if value is not None and (not isinstance(value, Fraction) or value < 0):
                raise ValueError("mass and concentration require nonnegative exact fractions")
        if not isinstance(self.reasons, tuple) or any(not isinstance(r, str) or not r for r in self.reasons):
            raise TypeError("reasons require an immutable tuple of nonempty text")
        if self.presence is Presence.PRESENT:
            if self.mass_kg is None or self.water is None or self.water.value == 0:
                raise ValueError("supported concentration requires positive water and known mass")
            if self.concentration_kg_m3 != self.mass_kg / self.water.value:
                raise ValueError("concentration must equal exact summed mass divided by water")
        elif self.concentration_kg_m3 is not None or not self.reasons:
            raise ValueError("unavailable concentration requires reasons, not a numeric ratio")


def _presence(state: str) -> Presence:
    return {
        "supported": Presence.PRESENT,
        "dry": Presence.DRY,
        "missing": Presence.MISSING,
        "absent": Presence.ABSENT,
        "outside_horizon": Presence.OUTSIDE_HORIZON,
        "unsupported": Presence.UNSUPPORTED,
    }[state]


@dataclass(frozen=True)
class PhysicalProjection:
    """Bind an immutable live or saved physical result to one prepared location.

    Keep this object with the returned samples: ``result`` is the complete source
    evidence and ``document_json`` is its durable output document, not a checkpoint.
    No supplied source identity is replaced by an assessment scenario.
    """

    result: TransportResult
    location: Location
    model_location: str
    provenance: Provenance
    view: ExchangeView
    time_interpretation: TimeInterpretation
    attributed_provenance: Provenance = field(init=False)

    def __post_init__(self) -> None:
        from taqsim.physical_results import TransportResult

        if not isinstance(self.result, TransportResult):
            raise TypeError("physical projection requires TransportResult")
        if not isinstance(self.location, Location) or not isinstance(self.provenance, Provenance):
            raise TypeError("prepared Location and Provenance required")
        if not isinstance(self.view, ExchangeView):
            raise TypeError("explicit incoming/outgoing ExchangeView required; storage is not flow")
        if not isinstance(self.time_interpretation, TimeInterpretation):
            raise TypeError("explicit UTC interpretation required for simulator time")
        if self.provenance.production_method not in (ProductionMethod.SIMULATED, ProductionMethod.RECONSTRUCTED):
            raise ValueError("simulator results cannot become observations")
        self.result.sample(self.model_location, 0, view=self.view.value)
        metadata = self.result.metadata
        run_metadata = metadata["inputs"]["metadata"] if "inputs" in metadata else metadata
        for source, target in (
            ("scenario", "scenario"),
            ("reference", "reference_member"),
            ("version", "configuration_version"),
            ("source", "source"),
            ("data_version", "data_version"),
            ("software_version", "software_version"),
        ):
            if (
                source in run_metadata
                and run_metadata[source] is not None
                and run_metadata[source] != getattr(self.provenance, target)
            ):
                raise ValueError(f"physical metadata conflicts with {target}")
        if "inputs" in metadata:
            for mapping in metadata["inputs"]["location_mappings"]:
                if mapping["location"] == self.model_location and (
                    mapping["physical_water_body"] != self.location.reach.water_body.identifier
                    or mapping["calculation_point"] != self.location.section.identifier
                    or mapping["mapping_version"] != self.location.mapping_version
                ):
                    raise ValueError("physical location mapping conflicts with prepared Location")
        object.__setattr__(
            self,
            "attributed_provenance",
            replace(
                self.provenance,
                dependencies=(*self.provenance.dependencies, f"taqsim-physical-sha256:{self.result.digest}"),
            ),
        )

    @property
    def document_json(self) -> str:
        """Full source evidence, including signed process/predecessor states and owners."""
        return json.dumps(self.result.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    def interval(self, step: int) -> Interval:
        if type(step) is not int:
            raise TypeError("step must be an integer model interval")
        start = self.result.time.datetime_at(step)
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        return Interval(start, start + self.result.time.timestep)

    def flows(self, steps: tuple[int, ...] | None = None) -> tuple[FlowSample, ...]:
        """Convert authoritative interval counts to discharge using exact elapsed time."""
        selected = tuple(range(self.result.time.steps)) if steps is None else steps
        if not isinstance(selected, tuple) or len(set(selected)) != len(selected):
            raise ValueError("steps require an immutable tuple without duplicates")
        output = []
        for step in selected:
            sample = self.result.sample(self.model_location, step, view=self.view.value)
            interval = self.interval(step)
            presence = _presence(sample.water_quality)
            if presence is Presence.DRY:
                presence = Presence.PRESENT
            amount = (
                None if sample.water_count is None else Volume(sample.water_count * Fraction(self.result.water_quantum))
            )
            if presence is Presence.PRESENT and amount is None:
                presence = Presence.MISSING
            reasons = () if sample.water_reason is None else (sample.water_reason,)
            if presence is not Presence.PRESENT and not reasons:
                reasons = (f"physical water {presence.value}",)
            value = None if amount is None else mean_discharge(amount, interval)
            output.append(
                FlowSample(self.location, interval, value, presence, self.attributed_provenance, reasons=reasons)
            )
        return tuple(output)

    def constituent(
        self, identifier: str, *, chemical_form: str, reporting_basis: str, start: int = 0, stop: int | None = None
    ) -> ConstituentSample:
        """Sum mass and water before division; never promote quality from available water."""
        stop = self.result.time.steps if stop is None else stop
        if type(start) is not int or type(stop) is not int or start >= stop:
            raise ValueError("constituent query requires a nonempty whole-interval range")
        interval = Interval(self.interval(start).start, self.interval(stop - 1).end)
        definition = next((c for c in self.result.constituents if c.id == identifier), None)
        if definition is None:
            return ConstituentSample(
                identifier,
                chemical_form,
                reporting_basis,
                interval,
                self.location,
                None,
                None,
                None,
                Presence.ABSENT,
                self.attributed_provenance,
                ("constituent absent from registry",),
            )
        if definition.chemical_form != chemical_form or definition.reporting_basis != reporting_basis:
            raise ValueError("constituent chemical form or reporting basis mismatch")
        if start < 0 or stop > self.result.time.steps:
            return ConstituentSample(
                identifier,
                chemical_form,
                reporting_basis,
                interval,
                self.location,
                None,
                None,
                None,
                Presence.OUTSIDE_HORIZON,
                self.attributed_provenance,
                ("outside model horizon",),
            )
        sample = self.result.aggregate(self.model_location, start, stop, view=self.view.value)
        presence = _presence(sample.quality[identifier])
        count = sample.mass_counts[identifier]
        mass = None if count is None else count * Fraction(definition.quantum_kg)
        water = None if sample.water_count is None else Volume(sample.water_count * Fraction(self.result.water_quantum))
        concentration = self.result.sample_concentration(sample, identifier)
        reasons = tuple(dict.fromkeys(filter(None, (sample.reasons.get(identifier), sample.water_reason))))
        if presence is Presence.PRESENT and concentration is None:
            presence = Presence.DRY if water is not None and water.value == 0 else Presence.UNSUPPORTED
        if presence is not Presence.PRESENT and not reasons:
            reasons = (f"physical constituent {presence.value}",)
        if any(
            interval.start < period.end and period.start < interval.end for period in self.provenance.excluded_warmup
        ):
            presence = Presence.UNSUPPORTED
            concentration = None
            reasons += ("requested interval includes excluded warm-up",)
        if stop - start > 1:
            reasons += ("aggregate loses within-interval resolution",)
        return ConstituentSample(
            identifier,
            chemical_form,
            reporting_basis,
            interval,
            self.location,
            mass,
            water,
            concentration,
            presence,
            self.attributed_provenance,
            reasons,
        )
