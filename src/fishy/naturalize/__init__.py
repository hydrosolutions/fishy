"""Naturalize module - transform water systems to natural flow state."""

from fishy.naturalize.errors import (
    AmbiguousSplitError,
    NaturalizationError,
    NoNaturalPathError,
    TerminalDemandError,
)
from fishy.naturalize.natural_river_splitter import NaturalRiverSplitter
from fishy.naturalize.naturalize import naturalize
from fishy.naturalize.types import NATURAL_TAG, NaturalizeResult

__all__ = [
    "NATURAL_TAG",
    "NaturalizeResult",
    "NaturalizationError",
    "NoNaturalPathError",
    "AmbiguousSplitError",
    "TerminalDemandError",
    "NaturalRiverSplitter",
    "naturalize",
]
