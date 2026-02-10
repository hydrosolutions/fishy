"""Naturalize module - transform water systems to natural flow state."""

from fishy.naturalize.errors import (
    AmbiguousSplitError,
    InvalidNaturalSplitRatiosError,
    NaturalizationError,
    NoNaturalPathError,
    NoNaturalReachError,
    TerminalDemandError,
)
from fishy.naturalize.natural_river_splitter import NaturalRiverSplitter
from fishy.naturalize.naturalize import naturalize
from fishy.naturalize.types import NATURAL_SPLIT_RATIOS, NATURAL_TAG, NaturalizeResult

__all__ = [
    "NATURAL_SPLIT_RATIOS",
    "NATURAL_TAG",
    "AmbiguousSplitError",
    "InvalidNaturalSplitRatiosError",
    "NaturalizationError",
    "NaturalRiverSplitter",
    "NaturalizeResult",
    "NoNaturalPathError",
    "NoNaturalReachError",
    "TerminalDemandError",
    "naturalize",
]
