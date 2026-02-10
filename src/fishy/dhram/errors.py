"""Error types for DHRAM computation failures."""

from dataclasses import dataclass


class DHRAMError(Exception):
    """Base error for DHRAM computation failures."""


@dataclass
class IncompatibleIHAResultsError(DHRAMError):
    """Raised when natural and impacted IHA results have incompatible shapes."""

    natural_n_params: int
    impacted_n_params: int

    def __str__(self) -> str:
        return (
            f"Incompatible IHA results: natural has {self.natural_n_params} parameters "
            f"per year, impacted has {self.impacted_n_params}. Both must have 33."
        )


@dataclass
class InsufficientYearsError(DHRAMError):
    """Raised when a flow series has too few complete years."""

    series_label: str
    n_years: int
    min_years: int

    def __str__(self) -> str:
        return (
            f"Insufficient years in {self.series_label} series: found {self.n_years}, need at least {self.min_years}."
        )


@dataclass
class NoCommonReachesError(DHRAMError):
    """Raised when natural and impacted systems share no natural Reach nodes."""

    natural_reach_ids: frozenset[str]
    impacted_reach_ids: frozenset[str]

    def __str__(self) -> str:
        return (
            f"No common natural Reach nodes between systems. "
            f"Natural reaches: {sorted(self.natural_reach_ids)}, "
            f"impacted reaches: {sorted(self.impacted_reach_ids)}."
        )


@dataclass
class ReachEvaluationError(DHRAMError):
    """Raised when all Reach nodes fail during DHRAM evaluation."""

    reach_errors: dict[str, Exception]

    def __str__(self) -> str:
        details = "; ".join(f"{rid}: {err}" for rid, err in sorted(self.reach_errors.items()))
        return f"All {len(self.reach_errors)} reach(es) failed DHRAM evaluation: {details}"
