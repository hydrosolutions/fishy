"""Fishy - e-flows intelligence layer for taqsim."""

from fishy.dhram import evaluate_dhram
from fishy.docs import get_docs_path
from fishy.iari import composite_iari_objective, evaluate_iari, iari_objective
from fishy.naturalize import NATURAL_SPLIT_RATIOS, NATURAL_TAG, NaturalRiverSplitter, naturalize

__all__ = [
    "NATURAL_SPLIT_RATIOS",
    "NATURAL_TAG",
    "NaturalRiverSplitter",
    "__version__",
    "composite_iari_objective",
    "evaluate_dhram",
    "evaluate_iari",
    "get_docs_path",
    "iari_objective",
    "naturalize",
]

__version__ = "0.1.3"
