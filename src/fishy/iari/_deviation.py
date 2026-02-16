"""Vectorized math helpers for IARI deviation scoring."""

import logging

import numpy as np
from numpy.typing import NDArray

from fishy.iari.types import EXCELLENT_THRESHOLD, GOOD_THRESHOLD, NaturalBands
from fishy.iha.types import IHAResult

logger = logging.getLogger(__name__)


def bands_from_iha(natural: IHAResult) -> NaturalBands:
    """Compute IQR bands from a natural IHA record.

    Args:
        natural: IHA result computed from the natural flow regime.

    Returns:
        NaturalBands with Q25/Q75 percentiles and pulse thresholds.

    Raises:
        ValueError: If pulse_thresholds is None on the natural record.
    """
    if natural.pulse_thresholds is None:
        raise ValueError("natural IHAResult must have pulse_thresholds; re-run IHA with explicit thresholds")
    q25: NDArray[np.float64] = np.percentile(natural.values, 25, axis=0)
    q75: NDArray[np.float64] = np.percentile(natural.values, 75, axis=0)
    return NaturalBands(
        q25=q25,
        q75=q75,
        pulse_thresholds=natural.pulse_thresholds,
    )


def compute_deviations(
    impacted_values: NDArray[np.float64],
    bands: NaturalBands,
) -> NDArray[np.float64]:
    """Compute per-parameter deviations from natural IQR bands.

    For each parameter i and year row, deviation is 0 when the value falls
    within [Q25, Q75], otherwise it is the distance to the nearest band edge
    normalised by the IQR width (Greco et al., 2021, Eq. 1).

    Args:
        impacted_values: IHA values for the impacted regime, shape (n_years, 33).
        bands: IQR bands derived from the natural record.

    Returns:
        Deviation matrix of shape (n_years, 33), values >= 0.
    """
    below = bands.q25[np.newaxis, :] - impacted_values  # positive when X < Q25
    above = impacted_values - bands.q75[np.newaxis, :]  # positive when X > Q75
    raw = np.maximum(np.maximum(below, above), 0.0)  # distance outside band

    iqr = bands.width[np.newaxis, :]
    has_iqr = iqr > 0
    safe_iqr = np.where(has_iqr, iqr, 1.0)
    normalized = raw / safe_iqr

    # Degenerate bands: any nonzero deviation -> 1.0, zero -> 0.0
    deviations: NDArray[np.float64] = np.where(has_iqr, normalized, np.where(raw > 0, 1.0, 0.0))

    # Log warning for degenerate bands
    degenerate_indices = np.flatnonzero(bands.degenerate_mask)
    if len(degenerate_indices) > 0:
        logger.warning(
            "Degenerate bands (IQR=0) at parameter indices %s; scoring as 0/1",
            degenerate_indices.tolist(),
        )

    return deviations


def classify_iari(value: float) -> str:
    """Classify an IARI score into a qualitative category.

    Args:
        value: Overall IARI score (mean deviation, >= 0).

    Returns:
        One of "Excellent", "Good", or "Poor".
    """
    if value <= EXCELLENT_THRESHOLD:
        return "Excellent"
    if value <= GOOD_THRESHOLD:
        return "Good"
    return "Poor"
