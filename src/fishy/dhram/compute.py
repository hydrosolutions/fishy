"""DHRAM computation orchestrator."""

from fishy.dhram._indicators import (
    apply_supplementary,
    classify,
    compute_summary_indicators,
    wfd_label,
)
from fishy.dhram.errors import IncompatibleIHAResultsError, InsufficientYearsError
from fishy.dhram.types import (
    EMPIRICAL_THRESHOLDS,
    SIMPLIFIED_THRESHOLDS,
    DHRAMResult,
    ThresholdVariant,
)
from fishy.iha.types import Col, IHAResult


def compute_dhram(
    natural: IHAResult,
    impacted: IHAResult,
    *,
    threshold_variant: ThresholdVariant = ThresholdVariant.EMPIRICAL,
    flow_cessation: bool = False,
    subdaily_oscillation: bool = False,
    min_years: int = 1,
) -> DHRAMResult:
    """Compute DHRAM classification from natural and impacted IHA results.

    Args:
        natural: IHA result for the un-impacted flow regime.
        impacted: IHA result for the impacted flow regime.
        threshold_variant: Empirical (default) or simplified thresholds.
        flow_cessation: Whether anthropogenic flow cessation is present.
        subdaily_oscillation: Whether sub-daily oscillations exceed threshold.
        min_years: Minimum complete years required in each series.

    Returns:
        DHRAMResult with classification and indicator details.

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

    # Select thresholds
    thresholds = EMPIRICAL_THRESHOLDS if threshold_variant == ThresholdVariant.EMPIRICAL else SIMPLIFIED_THRESHOLDS

    # Compute 10 summary indicators
    indicators = compute_summary_indicators(natural.values, impacted.values, thresholds)

    # Sum points and classify
    total_points = sum(ind.points for ind in indicators)
    preliminary_class = classify(total_points)
    final_class = apply_supplementary(
        preliminary_class,
        flow_cessation=flow_cessation,
        subdaily_oscillation=subdaily_oscillation,
    )

    return DHRAMResult(
        indicators=indicators,
        total_points=total_points,
        preliminary_class=preliminary_class,
        flow_cessation=flow_cessation,
        subdaily_oscillation=subdaily_oscillation,
        final_class=final_class,
        wfd_status=wfd_label(final_class),
        threshold_variant=threshold_variant,
        natural_years=natural_years,
        impacted_years=impacted_years,
    )
