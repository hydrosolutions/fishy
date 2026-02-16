"""Type definitions for the IARI module."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from fishy.iha.types import PulseThresholds

# Classification thresholds (from Greco et al., 2021)
EXCELLENT_THRESHOLD: float = 0.05
GOOD_THRESHOLD: float = 0.15

CLASSIFICATION_LABELS: tuple[str, ...] = ("Excellent", "Good", "Poor")


@dataclass(frozen=True)
class NaturalBands:
    """IQR bands derived from the natural IHA record.

    Args:
        q25: 25th percentile for each of the 33 IHA parameters.
        q75: 75th percentile for each of the 33 IHA parameters.
        pulse_thresholds: Pulse thresholds from the natural record, for reuse.
    """

    q25: NDArray[np.float64]
    q75: NDArray[np.float64]
    pulse_thresholds: PulseThresholds

    def __post_init__(self) -> None:
        if self.q25.shape != (33,):
            raise ValueError(f"q25 must have shape (33,), got {self.q25.shape}")
        if self.q75.shape != (33,):
            raise ValueError(f"q75 must have shape (33,), got {self.q75.shape}")
        if not np.all(self.q25 <= self.q75):
            violations = np.flatnonzero(self.q25 > self.q75)
            raise ValueError(f"q25 must be <= q75 for all parameters, violated at indices {violations.tolist()}")

    @property
    def width(self) -> NDArray[np.float64]:
        """IQR width for each parameter."""
        return self.q75 - self.q25

    @property
    def degenerate_mask(self) -> NDArray[np.bool_]:
        """Boolean mask where IQR == 0 (degenerate bands)."""
        return self.width == 0.0


@dataclass(frozen=True)
class IARIResult:
    """Result of an IARI computation.

    Args:
        deviations: Per-parameter deviations, shape (n_years, 33).
        years: Year labels, shape (n_years,).
        per_year: Mean deviation per year, shape (n_years,).
        overall: Grand mean of per_year values.
        classification: "Excellent", "Good", or "Poor".
        bands: The NaturalBands used for scoring.
        degenerate_params: Column indices where IQR == 0.
        natural_years: Number of years in the natural record.
        impacted_years: Number of years in the impacted record.
    """

    deviations: NDArray[np.float64]
    years: NDArray[np.intp]
    per_year: NDArray[np.float64]
    overall: float
    classification: str
    bands: NaturalBands
    degenerate_params: frozenset[int]
    natural_years: int
    impacted_years: int

    def __post_init__(self) -> None:
        n_years = self.deviations.shape[0]
        if self.deviations.ndim != 2 or self.deviations.shape[1] != 33:
            raise ValueError(f"deviations must have shape (n_years, 33), got {self.deviations.shape}")
        if self.years.shape != (n_years,):
            raise ValueError(f"years must have shape ({n_years},), got {self.years.shape}")
        if self.per_year.shape != (n_years,):
            raise ValueError(f"per_year must have shape ({n_years},), got {self.per_year.shape}")
        if self.classification not in CLASSIFICATION_LABELS:
            raise ValueError(f"classification must be one of {CLASSIFICATION_LABELS}, got '{self.classification}'")
        if self.overall < 0:
            raise ValueError(f"overall must be >= 0, got {self.overall}")

    def year_row(self, year: int) -> NDArray[np.float64]:
        """Return all 33 deviations for a single year.

        Args:
            year: The year to retrieve.

        Returns:
            Array of shape (33,).

        Raises:
            ValueError: If year is not present.
        """
        mask = self.years == year
        if not np.any(mask):
            raise ValueError(f"year {year} not found in results (available: {self.years.tolist()})")
        return self.deviations[mask][0]

    def param_deviation(self, col: int) -> NDArray[np.float64]:
        """Return deviation for a single parameter across all years.

        Args:
            col: Column index, 0 through 32.

        Returns:
            Array of shape (n_years,).

        Raises:
            ValueError: If col is not in [0, 32].
        """
        if col < 0 or col > 32:
            raise ValueError(f"col must be between 0 and 32, got {col}")
        return self.deviations[:, col]

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"IARI Score: {self.overall:.4f} ({self.classification})",
            f"Years analysed: {self.natural_years} (natural), {self.impacted_years} (impacted)",
            f"Degenerate parameters: {sorted(self.degenerate_params) if self.degenerate_params else 'none'}",
            "",
            f"{'Year':<8} {'IARI':<10}",
            "-" * 20,
        ]
        for year, score in zip(self.years, self.per_year, strict=True):
            lines.append(f"{year:<8} {score:<10.4f}")
        lines.append("-" * 20)
        lines.append(f"Overall: {self.overall:.4f} ({self.classification})")
        return "\n".join(lines)
