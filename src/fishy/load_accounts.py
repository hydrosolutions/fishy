"""assess_load_accounts : LoadAccounts × AccountTransfers → LocalAndBasinClosure.

Exact interval inventories retain unexplained residuals, never balancing sinks.
Source tags describe bookkeeping, not causal or legal responsibility.
"""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import Provenance, warmup_restrictions
from fishy.quality import ChemicalIdentity
from fishy.quantities import Number, Volume, finite_number
from fishy.time import Interval


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("account identity and evidence must be nonempty text")


def _tuple(values: tuple, kind: type) -> None:
    if not isinstance(values, tuple) or any(not isinstance(v, kind) for v in values):
        raise TypeError(f"immutable tuple of {kind.__name__} required")


@dataclass(frozen=True, init=False)
class Mass:
    """Nonnegative constituent inventory or interval transfer, canonically kg."""

    value: Fraction

    def __init__(self, value: Number, unit: str = "kg") -> None:
        if unit not in ("kg", "g"):
            raise ValueError("mass requires kg or g; rates are not interval mass")
        amount = finite_number(value) / (1000 if unit == "g" else 1)
        if amount < 0:
            raise ValueError("constituent mass cannot be negative")
        object.__setattr__(self, "value", amount)


@dataclass(frozen=True)
class AccountingUncertainty:
    """Supplied uncertainty description, not precision or inferred propagation."""

    description: str
    source: str

    def __post_init__(self) -> None:
        _text(self.description)
        _text(self.source)


def _uncertainty(value: AccountingUncertainty | None) -> None:
    if value is not None and not isinstance(value, AccountingUncertainty):
        raise TypeError("accounting uncertainty requires supplied AccountingUncertainty or explicit None")


@dataclass(frozen=True)
class Inventory:
    water: Volume
    mass: Mass
    uncertainty: AccountingUncertainty | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.water, Volume) or not isinstance(self.mass, Mass):
            raise TypeError("inventory requires Volume and Mass")
        _uncertainty(self.uncertainty)


@dataclass(frozen=True)
class SourceTag:
    source: str
    location: str
    interval: Interval
    mass: Mass
    evidence: str
    uncertainty: AccountingUncertainty | None = None

    def __post_init__(self) -> None:
        for value in (self.source, self.location, self.evidence):
            _text(value)
        if not isinstance(self.interval, Interval) or not isinstance(self.mass, Mass):
            raise TypeError("source tag requires Interval and Mass")
        _uncertainty(self.uncertainty)


@dataclass(frozen=True)
class AccountTransfer:
    """One located flux, counted once; None identifies the external boundary.

    Separate loads have zero water. Evaporation has zero dissolved mass.
    Untagged mass remains unallocated, including natural background.
    """

    identifier: str
    origin: str | None
    destination: str | None
    amount: Inventory
    source_tags: tuple[SourceTag, ...] = ()

    def __post_init__(self) -> None:
        _text(self.identifier)
        for endpoint in (self.origin, self.destination):
            if endpoint is not None:
                _text(endpoint)
        if self.origin == self.destination:
            raise ValueError("transfer must connect distinct boundaries")
        if not isinstance(self.amount, Inventory):
            raise TypeError("transfer requires Inventory")
        _tuple(self.source_tags, SourceTag)
        if sum((tag.mass.value for tag in self.source_tags), Fraction()) > self.amount.mass.value:
            raise ValueError("source-tag mass exceeds physical transfer mass")

    @property
    def unallocated_mass(self) -> Mass:
        return Mass(self.amount.mass.value - sum((tag.mass.value for tag in self.source_tags), Fraction()))


@dataclass(frozen=True)
class AccountProcess:
    """Explicit signed interval changes, not an inferred balancing term."""

    identifier: str
    water_change_m3: Fraction
    mass_change_kg: Fraction
    evidence: str

    def __post_init__(self) -> None:
        _text(self.identifier)
        _text(self.evidence)
        if not isinstance(self.water_change_m3, Fraction) or not isinstance(self.mass_change_kg, Fraction):
            raise TypeError("process changes require exact signed Fractions")


@dataclass(frozen=True)
class LoadAccount:
    location: str
    constituent: ChemicalIdentity
    interval: Interval
    scenario: str
    initial: Inventory
    final: Inventory
    provenance: Provenance
    processes: tuple[AccountProcess, ...] = ()
    precision_disclosures: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.location)
        _text(self.scenario)
        if not isinstance(self.provenance, Provenance) or self.provenance.scenario != self.scenario:
            raise ValueError("account requires provenance matching its scenario")
        if not isinstance(self.constituent, ChemicalIdentity) or not isinstance(self.interval, Interval):
            raise TypeError("account requires constituent identity and Interval")
        if not isinstance(self.initial, Inventory) or not isinstance(self.final, Inventory):
            raise TypeError("account requires initial and final Inventory")
        _tuple(self.processes, AccountProcess)
        _tuple(self.precision_disclosures, str)
        for disclosure in self.precision_disclosures:
            _text(disclosure)
        if len({p.identifier for p in self.processes}) != len(self.processes):
            raise ValueError("duplicate process identifier")


class ConservationState(StrEnum):
    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True)
class AccountResidual:
    location: str
    water_m3: Fraction
    mass_kg: Fraction

    @property
    def state(self) -> ConservationState:
        return ConservationState.INVALID if self.water_m3 or self.mass_kg else ConservationState.VALID


@dataclass(frozen=True)
class AccountAssessment:
    accounts: tuple[LoadAccount, ...]
    transfers: tuple[AccountTransfer, ...]
    local: tuple[AccountResidual, ...]
    basin: AccountResidual
    internal_transfer_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        expected = _derive_accounts(self.accounts, self.transfers)
        if (self.local, self.basin, self.internal_transfer_ids) != expected:
            raise ValueError("account residuals and internal transfers must equal their derived source relationships")

    @property
    def state(self) -> ConservationState:
        # Opposite local errors cannot cancel into a valid basin assessment.
        if any(r.state is ConservationState.INVALID for r in (*self.local, self.basin)):
            return ConservationState.INVALID
        return ConservationState.VALID

    @property
    def uncertainty_limitations(self) -> tuple[str, ...]:
        missing = []
        for account in self.accounts:
            for label, inventory in (("initial", account.initial), ("final", account.final)):
                if inventory.uncertainty is None:
                    missing.append(f"{account.location}: {label} inventory uncertainty not supplied")
        for transfer in self.transfers:
            if transfer.amount.uncertainty is None:
                missing.append(f"{transfer.identifier}: transfer uncertainty not supplied")
            for tag in transfer.source_tags:
                if tag.uncertainty is None:
                    missing.append(f"{transfer.identifier}/{tag.source}: source-tag uncertainty not supplied")
        return tuple(missing)

    def require_valid(self) -> None:
        """Invalidate dependent assessment, rather than downgrade closure to a warning."""
        if self.state is ConservationState.INVALID:
            raise ValueError("conservation failure invalidates the affected quality assessment")
        restrictions = tuple(
            reason for account in self.accounts for reason in warmup_restrictions(account.provenance, account.interval)
        )
        if restrictions:
            raise ValueError("; ".join(restrictions))


def _derive_accounts(
    accounts: tuple[LoadAccount, ...], transfers: tuple[AccountTransfer, ...]
) -> tuple[tuple[AccountResidual, ...], AccountResidual, tuple[str, ...]]:
    """Derive validated local/basin residuals and internal-transfer identity."""
    _tuple(accounts, LoadAccount)
    _tuple(transfers, AccountTransfer)
    if not accounts:
        raise ValueError("a basin account requires local inventories")
    locations = {a.location for a in accounts}
    if len(locations) != len(accounts):
        raise ValueError("duplicate account location")
    if len({t.identifier for t in transfers}) != len(transfers):
        raise ValueError("duplicate physical transfer")
    if (
        len(
            {
                (
                    a.constituent,
                    a.interval,
                    a.scenario,
                    a.provenance.data_version,
                    a.provenance.configuration_version,
                    a.provenance.reference_member,
                )
                for a in accounts
            }
        )
        != 1
    ):
        raise ValueError("accounts must share chemical basis, interval and scenario")
    for transfer in transfers:
        for endpoint in (transfer.origin, transfer.destination):
            if endpoint is not None and endpoint not in locations:
                raise ValueError("transfer endpoint has no inventory account")
        if any(tag.interval != accounts[0].interval for tag in transfer.source_tags):
            raise ValueError("source tag interval does not match accounting interval")
    residuals = []
    for account in accounts:
        water = account.final.water.value - account.initial.water.value
        mass = account.final.mass.value - account.initial.mass.value
        for transfer in transfers:
            sign = int(transfer.origin == account.location) - int(transfer.destination == account.location)
            water += sign * transfer.amount.water.value
            mass += sign * transfer.amount.mass.value
        water -= sum((p.water_change_m3 for p in account.processes), Fraction())
        mass -= sum((p.mass_change_kg for p in account.processes), Fraction())
        residuals.append(AccountResidual(account.location, water, mass))
    basin = AccountResidual(
        "basin", sum((r.water_m3 for r in residuals), Fraction()), sum((r.mass_kg for r in residuals), Fraction())
    )
    return (
        tuple(residuals),
        basin,
        tuple(t.identifier for t in transfers if t.origin is not None and t.destination is not None),
    )


def assess_load_accounts(
    accounts: tuple[LoadAccount, ...], transfers: tuple[AccountTransfer, ...]
) -> AccountAssessment:
    """Check one constituent, scenario and interval; independent constituents run separately."""
    local, basin, internal = _derive_accounts(accounts, transfers)
    return AccountAssessment(accounts, transfers, local, basin, internal)


class ControlState(StrEnum):
    EXHAUSTED = "exhausted"
    OUTSTANDING = "outstanding"
    UNKNOWN = "unknown"


class ResidualSourceKind(StrEnum):
    UNCONTROLLABLE_DIFFUSE = "uncontrollable_diffuse"
    CONTROLLABLE = "controllable"
    POINT_SOURCE = "point_source"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SourceControlEvidence:
    """Prepared inventory of duties and residual sources for one declared boundary."""

    scenario: str
    location: str
    interval: Interval
    discharge_control: ControlState
    residual_sources: tuple[tuple[str, ResidualSourceKind], ...]
    evidence: str

    def __post_init__(self) -> None:
        for value in (self.scenario, self.location, self.evidence):
            _text(value)
        if not isinstance(self.interval, Interval) or not isinstance(self.discharge_control, ControlState):
            raise TypeError("source-control evidence requires interval and ControlState")
        if not isinstance(self.residual_sources, tuple):
            raise TypeError("residual sources must be immutable")
        for source in self.residual_sources:
            if not isinstance(source, tuple) or len(source) != 2 or not isinstance(source[1], ResidualSourceKind):
                raise TypeError("residual source requires identity and ResidualSourceKind")
            _text(source[0])
        if len({s[0] for s in self.residual_sources}) != len(self.residual_sources):
            raise ValueError("duplicate residual source")

    def require_residual_dilution(self) -> None:
        if self.discharge_control is not ControlState.EXHAUSTED:
            raise ValueError("discharge control must be exhausted before residual dilution")
        if not self.residual_sources or any(
            kind is not ResidualSourceKind.UNCONTROLLABLE_DIFFUSE for _, kind in self.residual_sources
        ):
            raise ValueError("residual dilution serves only documented uncontrollable diffuse loads")
