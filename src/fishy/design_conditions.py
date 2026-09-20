"""DesignClass → AnnualExceedanceLabel for four ecological design conditions.

These labels denote annual design years, not daily discharge percentiles.
"""

from enum import IntEnum


class DesignClass(IntEnum):
    WET = 25
    MEDIUM = 50
    MODERATELY_DRY = 75
    DRY = 95
