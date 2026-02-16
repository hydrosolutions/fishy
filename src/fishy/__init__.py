"""Fishy - e-flows intelligence layer for taqsim."""

from fishy.dhram import evaluate_dhram
from fishy.docs import get_docs_path
from fishy.naturalize import NATURAL_SPLIT_RATIOS, NATURAL_TAG, NaturalRiverSplitter, naturalize

__all__ = [
    "NATURAL_SPLIT_RATIOS",
    "NATURAL_TAG",
    "NaturalRiverSplitter",
    "__version__",
    "evaluate_dhram",
    "get_docs_path",
    "naturalize",
]

__version__ = "0.1.1"
