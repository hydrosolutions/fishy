# Prepared basin accounting

`fishy.basin` consumes a prepared river/section topology. It orders sections from
mouth to source, verifies a receiving-parent donor relation, and calculates an
attributed main-river tributary sum. It does not reconstruct a basin, infer a donor,
estimate a transfer coefficient, or route releases.

## Identity and context

- `Basin(identifier, version)` and `River(identifier, version, order)` are distinct
  from `WaterBody`, `Reach`, and `CalculationSection` in `fishy.spatial`.
- `PreparedTopology` contains one basin revision, explicit `RiverConnection`
  records, and the complete `SectionContext` set. Each section has its own
  `Location`, downstream `Location`, river type, and supplied context findings.
- River order is source metadata. Main-river order zero is checked, but numerical
  order does not create connectivity. `Reach.predecessors` remains revision
  history, not upstream connectivity.
- `ContextEvidence` retains scoped findings for channel, floodplain, delta,
  terminal water, hydrological phases, climate, biology, water use, operations,
  transboundary conditions, and river type. An empty evidence tuple means no
  supplied findings, not an accepted or inapplicable condition. These records do
  not assess physical or biological criteria.
- One topology has one connected outlet. Separate outlets require separate
  prepared basin configurations. Cycles, missing sections, mixed revisions and
  inconsistent river/section connections are invalid inputs.

`mouth_to_source(topology)` returns each section after its downstream section.
Receiving rivers precede their tributaries. Input order breaks ties between
independent branches; it cannot override connectivity.

## Receiving-parent donor interpretation

`receiving_parent(topology, river)` follows the actual connection. It returns
`None` for the main river. It does not use nearest-gauge distance or choose the
numerically higher-order tributary.

Call `verify_donor_relation(topology, recipient, relation, scope)` only under the
explicitly selected receiving-parent interpretation. `DonorRelation` stores the
recipient, donor and `EvidenceFindings`. Verification requires the actual parent
and accepted evidence for the exact requested product, recipient reach, member,
period and use. Unknown support or missing topology/relation remains unknown and
requires further study. Wrong connectivity or prohibited use fails. Excluded
warm-up periods cannot qualify. Coefficient evidence is a separate annual-route
input: a successful relation check does not establish any coefficient.

Order 179 paragraph 22 conflicts with the numerical-order wording in paragraph
2(6). This operation implements the named connectivity interpretation, not an
official resolution. Official admissibility remains in the supplied evidence.

## Attributed tributary sum

`tributary_sum(topology, receiving, location, scope, accounts, evidence)` implements
the attributed main-river relation in Order 179 paragraph 5. `scope.product` must
identify the supplied quantitative product, including design condition and
calculation stage. Scope fixes the period, reference member and intended use.

Each `TributaryAccount` supplies one direct tributary, its selected section,
`Volume`, explicit disjoint `water_accounts`, and scoped evidence. The accounting
relation itself also needs evidence. Water-account identifiers refer to caller-
prepared parcels of the water account, not additional water sources. Their
scientific support is supplied, not established by string labels or topology.

The sum requires all direct tributaries exactly once. It rejects repeated
sections of the same river, nested tributaries already included in a parent's
account, and overlapping water-account parcels. It also rejects mixed scenarios,
configuration versions and reference members. A supported zero remains zero.
A missing quantity, unsupported relation, incomplete tributary set or absent
mapping yields `volume=None`, with attributable checks and the original accounts.
A known failed check survives other missing inputs.

The result retains the topology revision, river, location, scope, accounts,
evidence and source attribution. It is **not** a consumptive demand, available
water, deliverable water, a routed release, or an issued obligation. Successive
non-consumptive main-river section requirements are not summed. There is no
universal sum or maximum when the prepared accounting relation is absent.

## Supplied synthetic example

This example supports a scenario calculation, not official basin certification.
Two disjoint direct tributaries contribute 30 and 20 m³ over the same year.

```python
from datetime import UTC, datetime

from fishy.basin import (
    Basin, PreparedTopology, River, RiverConnection, SectionContext,
    TributaryAccount, mouth_to_source, tributary_sum,
)
from fishy.evidence import (
    Computability, CorrectionState, Disclosure, EvidenceFindings, EvidenceScope,
    NumericalValidity, OfficialAdmissibility, ProductionMethod, Provenance,
    ScientificAdequacy,
)
from fishy.quantities import Volume
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

period = Interval(datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC))
provenance = Provenance(
    "synthetic accounting study", "scenario-A", "natural-A", "software-1",
    "data-1", "configuration-1", ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
)


def location(name):
    return Location(
        Reach(name, "1", WaterBody(name, "1")),
        CalculationSection(name, "1"), "mapping-1",
    )


def findings(loc):
    return EvidenceFindings(
        EvidenceScope("design25/initial-volume", loc.reach.identifier,
                      "natural-A", period, "scenario calculation"),
        provenance, Computability.COMPUTABLE, NumericalValidity.VALID,
        Disclosure.COMPLETE, ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING, (),
    )


main, left, right = River("main", "1", 0), River("left", "1", 1), River("right", "1", 1)
mouth, a, b = location("mouth"), location("a"), location("b")
topology = PreparedTopology(
    Basin("basin", "1"), "topology-1", (main, left, right),
    (RiverConnection(left, main), RiverConnection(right, main)),
    (SectionContext(left, a, mouth), SectionContext(right, b, mouth),
     SectionContext(main, mouth, None)),
)
accounts = (
    TributaryAccount(left, a, Volume(30), ("left-account",), findings(a)),
    TributaryAccount(right, b, Volume(20), ("right-account",), findings(b)),
)
support = findings(mouth)
result = tributary_sum(topology, main, mouth, support.scope, accounts, support)
assert result.volume == Volume(50)
assert mouth_to_source(topology)[0].location == mouth
assert result.evidence.official_admissibility is OfficialAdmissibility.PENDING
```

## Source and test crosswalk

Source: Order 179-НҚ, 23 July 2025, held official Ministry PDF, methodology
paragraphs below. The supplied report's D.3 receiving-parent interpretation
provides the explicitly named candidate reading. Source copies are not distributed
with this module.

| Source contract | Public operation/input | Observable test in `tests/test_basin.py` |
| --- | --- | --- |
| 2(6), 5: basin identity, sequence and tributaries | `PreparedTopology`, `mouth_to_source` | `test_mouth_to_source_sections_and_receiving_rivers_before_tributaries`; `test_source_order_labels_do_not_create_or_override_connectivity` |
| 4, 6, 8–10, 12–14: section and environmental context | `SectionContext`, `ContextEvidence` | `test_context_evidence_preserves_every_supplied_kind_and_scope` (evidence carriage, not ecological assessment) |
| 5: main-river tributary relation | `tributary_sum` | `test_supported_paragraph5_sum_preserves_source_and_exact_attribution`: 30 + 20 = 50 m³, exactly |
| 5: unsupported accounting | `TributaryAccount`, scoped evidence | `test_missing_accounting_evidence_never_becomes_a_sum_or_maximum`; `test_double_counting_and_mixed_support_cannot_produce_result` |
| 22: receiving-parent interpretation | `receiving_parent`, `verify_donor_relation` | `test_receiving_parent_not_higher_order_child_or_unconnected_gauge`; `test_donor_missing_or_unsupported_evidence_remains_further_study` |
| Versioned evidence and incomplete coverage | `TributarySum`, `CheckSummary` | `test_revision_identity_cannot_select_old_donor_or_rewrite_result`; `test_known_failure_survives_other_missing_account` |

All numerical assertions use exact `Fraction`-backed `Volume`, with no tolerance.
Run the focused suite with `uv run pytest tests/test_basin.py`.
This module covers prepared topology and accounting only. Annual arithmetic,
coefficient establishment, biological/hydraulic assessments, operational changes,
and five-year reviews belong to their separate operations and supplied studies.
