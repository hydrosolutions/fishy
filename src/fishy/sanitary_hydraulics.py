"""sanitary_hydraulics : HydraulicScope × AttributedHydraulicEvidence → Check (pure).

Compatibility imports for sanitary clients. Shared operators live in hydraulics;
no numerical criterion is inferred from sanitary wording.
"""

from fishy.hydraulics import (
    BoundState as BoundState,
)
from fishy.hydraulics import (
    Comparison as Comparison,
)
from fishy.hydraulics import (
    CriterionApplicability as CriterionApplicability,
)
from fishy.hydraulics import (
    CriterionStatus as CriterionStatus,
)
from fishy.hydraulics import (
    HydraulicRelationEvidence as HydraulicRelationEvidence,
)
from fishy.hydraulics import (
    HydraulicScope as HydraulicScope,
)
from fishy.hydraulics import (
    HydraulicTransition as HydraulicTransition,
)
from fishy.hydraulics import (
    HydraulicVariable as HydraulicVariable,
)
from fishy.hydraulics import (
    ImportedHydraulicFinding as ImportedHydraulicFinding,
)
from fishy.hydraulics import (
    RateAssessment as RateAssessment,
)
from fishy.hydraulics import (
    RateBound as RateBound,
)
from fishy.hydraulics import (
    RateCriterion as RateCriterion,
)
from fishy.hydraulics import (
    RelationDomain as RelationDomain,
)
from fishy.hydraulics import (
    StateBounds as StateBounds,
)
from fishy.hydraulics import (
    TemporalSupport as TemporalSupport,
)
from fishy.hydraulics import (
    TransitionCoverage as TransitionCoverage,
)
from fishy.hydraulics import assess_discrete_rate
from fishy.hydraulics import (
    assess_imported_hydraulics as assess_imported_hydraulics,
)
from fishy.hydraulics import (
    rate_check as rate_check,
)

assess_sanitary_rate = assess_discrete_rate
