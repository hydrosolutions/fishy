"""Type definitions for the DHRAM module."""

from dataclasses import dataclass
from enum import Enum

DHRAM_GROUP_SIZES: tuple[int, ...] = (12, 10, 2, 4, 3)
"""Parameter counts per IHA group used in DHRAM scoring.

Group 2 uses 10 params (excludes zero_flow_days and BFI from the 12 IHA Group 2 params).
"""

N_INDICATORS: int = 10
MAX_POINTS: int = 30

INDICATOR_NAMES: tuple[str, ...] = (
    "1a",
    "1b",
    "2a",
    "2b",
    "3a",
    "3b",
    "4a",
    "4b",
    "5a",
    "5b",
)

WFD_LABELS: tuple[str, ...] = ("High", "Good", "Moderate", "Poor", "Bad")

CLASS_BOUNDARIES: tuple[int, ...] = (0, 1, 5, 11, 21)
"""Lower bounds (inclusive) for DHRAM classes 1-5."""


class ThresholdVariant(Enum):
    """Which set of scoring thresholds to use."""

    EMPIRICAL = "empirical"
    SIMPLIFIED = "simplified"


@dataclass(frozen=True)
class ScoringThresholds:
    """Three-tier deviation thresholds for scoring a single DHRAM indicator.

    Args:
        lower: Lower threshold (1-point boundary).
        intermediate: Intermediate threshold (2-point boundary).
        upper: Upper threshold (3-point boundary).
    """

    lower: float
    intermediate: float
    upper: float

    def __post_init__(self) -> None:
        if not (0 <= self.lower <= self.intermediate <= self.upper):
            raise ValueError(
                f"Thresholds must satisfy 0 <= lower <= intermediate <= upper, "
                f"got lower={self.lower}, intermediate={self.intermediate}, upper={self.upper}"
            )

    def score(self, value: float) -> int:
        """Score a deviation value against these thresholds.

        Returns:
            0 if value < lower, 1 if lower <= value < intermediate,
            2 if intermediate <= value < upper, 3 if value >= upper.
        """
        if value >= self.upper:
            return 3
        if value >= self.intermediate:
            return 2
        if value >= self.lower:
            return 1
        return 0


EMPIRICAL_THRESHOLDS: tuple[ScoringThresholds, ...] = (
    ScoringThresholds(19.9, 43.7, 67.5),  # 1a
    ScoringThresholds(29.4, 97.6, 165.7),  # 1b
    ScoringThresholds(42.9, 88.2, 133.4),  # 2a
    ScoringThresholds(84.5, 122.7, 160.8),  # 2b
    ScoringThresholds(7.0, 21.2, 35.5),  # 3a
    ScoringThresholds(33.4, 50.3, 67.3),  # 3b
    ScoringThresholds(36.4, 65.1, 93.8),  # 4a
    ScoringThresholds(30.5, 76.1, 121.6),  # 4b
    ScoringThresholds(46.0, 82.7, 119.4),  # 5a
    ScoringThresholds(49.1, 79.9, 110.6),  # 5b
)
"""Empirical thresholds from Black et al. (2005) Table 3."""

SIMPLIFIED_THRESHOLDS: tuple[ScoringThresholds, ...] = tuple(
    ScoringThresholds(10.0, 30.0, 50.0) for _ in range(N_INDICATORS)
)
"""Uniform simplified thresholds (10/30/50%)."""


@dataclass(frozen=True)
class IndicatorDetail:
    """Detail for one of the 10 DHRAM summary indicators."""

    name: str
    group: int
    statistic: str
    value: float
    points: int
    thresholds: ScoringThresholds


@dataclass(frozen=True)
class DHRAMResult:
    """Result of a DHRAM classification.

    Args:
        indicators: The 10 summary indicators (1a through 5b).
        total_points: Sum of indicator points (0-30).
        preliminary_class: Class before supplementary adjustments (1-5).
        flow_cessation: Whether anthropogenic flow cessation was flagged.
        subdaily_oscillation: Whether sub-daily oscillations were flagged.
        final_class: Class after supplementary adjustments (1-5).
        wfd_status: WFD status label (High/Good/Moderate/Poor/Bad).
        threshold_variant: Which threshold set was used.
        natural_years: Number of years in the natural record.
        impacted_years: Number of years in the impacted record.
    """

    indicators: tuple[IndicatorDetail, ...]
    total_points: int
    preliminary_class: int
    flow_cessation: bool
    subdaily_oscillation: bool
    final_class: int
    wfd_status: str
    threshold_variant: ThresholdVariant
    natural_years: int
    impacted_years: int

    def __post_init__(self) -> None:
        if len(self.indicators) != N_INDICATORS:
            raise ValueError(f"Expected {N_INDICATORS} indicators, got {len(self.indicators)}")
        if not 0 <= self.total_points <= MAX_POINTS:
            raise ValueError(f"Total points must be in [0, {MAX_POINTS}], got {self.total_points}")
        if not 1 <= self.preliminary_class <= 5:
            raise ValueError(f"Preliminary class must be in [1, 5], got {self.preliminary_class}")
        if not 1 <= self.final_class <= 5:
            raise ValueError(f"Final class must be in [1, 5], got {self.final_class}")

    def indicator(self, name: str) -> IndicatorDetail:
        """Look up a summary indicator by name (e.g. '1a', '3b')."""
        for ind in self.indicators:
            if ind.name == name:
                return ind
        raise ValueError(f"Indicator '{name}' not found (available: {[i.name for i in self.indicators]})")

    def group_points(self, g: int) -> int:
        """Total points for a given IHA group (1-5)."""
        if not 1 <= g <= 5:
            raise ValueError(f"Group must be in [1, 5], got {g}")
        a_name = f"{g}a"
        b_name = f"{g}b"
        return self.indicator(a_name).points + self.indicator(b_name).points

    def summary(self) -> str:
        """Human-readable summary table."""
        lines = [
            f"DHRAM Classification: Class {self.final_class} ({self.wfd_status})",
            f"Total impact points: {self.total_points}/{MAX_POINTS}",
            f"Threshold variant: {self.threshold_variant.value}",
            f"Years analysed: {self.natural_years} (natural), {self.impacted_years} (impacted)",
            "",
            f"{'Indicator':<12} {'Value (%)':<12} {'Points':<8} {'Thresholds (L/M/U)'}",
            "-" * 60,
        ]
        for ind in self.indicators:
            t = ind.thresholds
            lines.append(
                f"{ind.name:<12} {ind.value:<12.1f} {ind.points:<8} {t.lower:.1f}/{t.intermediate:.1f}/{t.upper:.1f}"
            )
        lines.append("-" * 60)
        lines.append(f"Preliminary class: {self.preliminary_class}")
        flags = []
        if self.flow_cessation:
            flags.append("flow cessation (+1)")
        if self.subdaily_oscillation:
            flags.append("sub-daily oscillation (+1)")
        if flags:
            lines.append(f"Supplementary adjustments: {', '.join(flags)}")
        lines.append(f"Final class: {self.final_class} ({self.wfd_status})")
        return "\n".join(lines)
