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
class NoCommonEdgesError(DHRAMError):
    """Raised when natural and impacted systems share no natural-tagged edges."""

    natural_edge_ids: frozenset[str]
    impacted_edge_ids: frozenset[str]

    def __str__(self) -> str:
        return (
            f"No common natural-tagged edges between systems. "
            f"Natural edges: {sorted(self.natural_edge_ids)}, "
            f"impacted edges: {sorted(self.impacted_edge_ids)}."
        )


@dataclass
class EdgeEvaluationError(DHRAMError):
    """Raised when all edges fail during DHRAM evaluation."""

    edge_errors: dict[str, Exception]

    def __str__(self) -> str:
        details = "; ".join(f"{eid}: {err}" for eid, err in sorted(self.edge_errors.items()))
        return f"All {len(self.edge_errors)} edge(s) failed DHRAM evaluation: {details}"
