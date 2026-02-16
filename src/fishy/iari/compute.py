"""IARI computation orchestrator."""

import numpy as np

from fishy.iari._deviation import bands_from_iha, classify_iari, compute_deviations
from fishy.iari.errors import IncompatibleIHAResultsError, InsufficientYearsError
from fishy.iari.types import IARIResult
from fishy.iha.types import Col, IHAResult


def compute_iari(
    natural: IHAResult,
    impacted: IHAResult,
    *,
    min_years: int = 1,
) -> IARIResult:
    """Compute IARI from natural and impacted IHA results.

    Args:
        natural: IHA result for the un-impacted flow regime.
        impacted: IHA result for the impacted flow regime.
        min_years: Minimum complete years required in each series.

    Returns:
        IARIResult with per-parameter deviations and classification.

    Raises:
        IncompatibleIHAResultsError: If IHA results don't have 33 params.
        InsufficientYearsError: If either series has too few years.
    """
    # Validate shapes
    if natural.values.shape[1] != Col.N_PARAMS:
        raise IncompatibleIHAResultsError(
            natural_n_params=natural.values.shape[1],
            impacted_n_params=impacted.values.shape[1],
        )
    if impacted.values.shape[1] != Col.N_PARAMS:
        raise IncompatibleIHAResultsError(
            natural_n_params=natural.values.shape[1],
            impacted_n_params=impacted.values.shape[1],
        )

    # Validate year counts
    natural_years = len(natural.years)
    impacted_years = len(impacted.years)
    if natural_years < min_years:
        raise InsufficientYearsError(
            series_label="natural",
            n_years=natural_years,
            min_years=min_years,
        )
    if impacted_years < min_years:
        raise InsufficientYearsError(
            series_label="impacted",
            n_years=impacted_years,
            min_years=min_years,
        )

    # Compute IQR bands from the natural record
    bands = bands_from_iha(natural)

    # Compute per-parameter deviations for impacted years
    deviations = compute_deviations(impacted.values, bands)

    # Per-year aggregation: mean deviation across 33 parameters
    per_year: np.ndarray = np.mean(deviations, axis=1)

    # Overall IARI score: mean across all impacted years
    overall = float(np.mean(per_year))

    # Classification based on overall score
    classification = classify_iari(overall)

    # Identify degenerate parameters (IQR == 0)
    degenerate_params = frozenset(int(i) for i in np.flatnonzero(bands.degenerate_mask))

    return IARIResult(
        deviations=deviations,
        years=impacted.years,
        per_year=per_year,
        overall=overall,
        classification=classification,
        bands=bands,
        degenerate_params=degenerate_params,
        natural_years=natural_years,
        impacted_years=impacted_years,
    )
