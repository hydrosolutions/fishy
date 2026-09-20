# Swiss permit routes and process evidence

`fishy.swiss_permits` screens supplied abstraction and process inputs. It does
not issue a permit, certify evidence, or derive remediation duties. It runs
without Taqsim, HYDMOD, a simulator, or the Swiss Q347 estimator.

## Prepare scoped evidence

`PermitScope` names a complete `Location`, exact `Interval`, scenario, reference
member, data version, configuration version and optional `ReferenceKind`.
`Location` retains body, reach, section and mapping revisions.

Build the accepted-use scope with
`permit_evidence_scope(scope, PermitEvidencePurpose.<purpose>, subject)`. Supply independent
`EvidenceFindings` and wrap them in `PermitEvidence(scope, findings)`. The scope
binds the full physical and scenario identity. Evidence cannot be rebound to
another section of the same reach, another configuration, or another intended
use. `subject` is the actual immutable `AbstractionContext`, `DownstreamPermanence`,
`AbstractionInventory`, `Article30ReadingSelection`, `AnnualDrinkingAbstraction`,
or `PermitDocument` being reviewed. Its factual fields, including quantities,
classifications, decision status and document contents, form the accepted subject.
Build the record with absent evidence, request its scoped review, then attach
findings with `dataclasses.replace`. Replacing facts without a new review produces
unknown support. An accepted opinion cannot become a federal hearing by changing
its kind. Provenance must match the declared scenario, member, reference kind and
data/configuration versions.

Purposes are `APPLICABILITY`, `DOWNSTREAM_PERMANENCE`,
`NATURE_FISHERIES_MEASURES`, `ABSTRACTION_ENVELOPE`, `ARTICLE_30_READING`,
`ANNUAL_DRINKING_ABSTRACTION`, and `PROCESS_DOCUMENT`.

Numerical values and supplied evidence remain separate. Scientific rejection,
unknown coverage and official admissibility are not interchangeable. An
illustrative result retains illustrative provenance. A passing screen is not an
observed compliance finding or permission. A known required failure survives
other missing evidence. Empty inventories cannot establish a complete pass.

## Select the scope route

`assess_permit_scope(AbstractionContext(...))` distinguishes:

- New/renewed abstractions beyond common use from perennial watercourses:
  Article 30 conditions, with only supported perennial downstream sections
  listed in `article_30_sections`. Nonperennial downstream sections retain
  separately scoped `nature_fisheries_measures` (Guide p. 15).
- Significant effects from lake/groundwater abstraction on a perennial
  watercourse: analogous protection under Article 34. Spring water counts as
  groundwater here (Act 4(b)); its Article 30(c) annual limit stays distinct.
- Nonperennial intake: the separate nature/fisheries protection-measures route,
  even if a downstream section is perennial. Ordinance 33(2) and Guide p. 15
  do not impose the residual-flow permit route on that intake.
- Within-common-use or supported insignificant lake/groundwater effects:
  outside Article 29, not an automatic permission under other law.
- Existing concessions: Arts. 80 ff. remediation derivation remains unsupported.
- An already prescribed duty: use `fishy.duties.assess_duty`. Historical sizing
  and Q347 are not prerequisites. No new Article 31 table value is assigned.

Permanence uses the Act's strict `Q347 > 0`, not the older guide's pragmatic
infiltration convention. Applicability evidence supplies common-use and effect
classifications. An empty affected-section inventory prevents complete coverage
of the Article 30/34 route. This route result is not an assessment of all
Articles 31–35; retain the separate safeguard, exception, balancing, intake and
process results.

## Limited watercourse abstractions

`assess_limited_abstraction(q347, inventory, selection)` returns the combined
abstraction, exact 20% limit, both 1,000 l/s readings, and selected eligibility.
The `selection` argument has no default. Pass `None` to retain unresolved
interpretation and both branch findings.

`AbstractionInventory` declares the complete simultaneous abstraction envelope
at its scope. `AbstractionRate(identifier, upper_rate)` retains each intake.
`AbstractionTimeBasis.INSTANTANEOUS_ENVELOPE` must be backed by evidence over
the whole interval. `INTERVAL_MEAN` cannot establish a passing instantaneous
condition. An excessive mean still establishes a numerical failure.

`Article30ReadingSelection` requires the named reading, `DecisionStatus`, source
and separately scoped interpretation evidence. `HYPOTHETICAL` does not become
`SUPPLIED_AUTHORITY`. Even the latter records a supplied interpretation, not
software authentication of its legal effect.

For Q347 = 7,000 l/s and two simultaneous 700 l/s abstractions:

- Combined abstraction = 1,400 l/s = 20% Q347.
- `AGGREGATE_1000` fails.
- `PER_ABSTRACTION_1000` passes the numerical limits.
- No selection leaves eligibility unresolved.

If both readings fail, missing selection does not conceal their common failure.
These limits do not depend on missing Article 31 safeguard sizing evidence.

## Annual drinking-water abstraction

`assess_drinking_abstraction(AnnualDrinkingAbstraction(...))` consumes a complete
annual `Volume`, not an instantaneous rate. The caller supplies a complete UTC
calendar-year interval and the aggregate abstraction from the identified source.
The exact annual mean is volume divided by the year's actual elapsed seconds.
Leap years retain 366 days.

Only `DRINKING_WATER` purpose qualifies. Spring and groundwater limits are
respectively 80 and 100 l/s, inclusive. Lake or other purpose inputs fail this
specific route. Monthly, seasonal and partial-year intervals are refused, not
silently annualised. The UTC convention is an explicit supported implementation
boundary, not a statutory timezone rule.

## Consultations and documents

`assess_permit_process(PermitProcess(...))` always requires specialist
consultation. The supplied inventory names interested specialists; the
consultation document lists those actually consulted. A missing named specialist
fails, even if another required document is missing.

For `HYDROPOWER`, a `GrossHydropower` strictly above 300 kW also requires a
federal hearing. Exactly 300 kW does not. Missing gross power leaves the
conditional hearing requirement unresolved. Power accepts exact kW or MW.

- `EnvironmentalReview.EIA`: the residual-water report must be included in the
  environmental impact report.
- `NON_EIA` with required federal hearing: either the cantonal opinion or its
  revised draft must be available to FOEN. A supported alternative is sufficient;
  both supplied documents remain in the result.
- Unknown EIA applicability remains unknown.

`PermitDocument` retains kind, issuer, reference and scoped evidence. Process
coverage does not establish a favourable authority decision.

## Complete numerical example

This is synthetic scenario evidence, not a source authentication.

```python
from dataclasses import replace
from datetime import UTC, datetime
from fishy.evidence import (
    Computability, CorrectionState, Disclosure, EvidenceFindings,
    NumericalValidity, OfficialAdmissibility, ProductionMethod, Provenance,
    ScientificAdequacy,
)
from fishy.quantities import Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval
from fishy.swiss_permits import (
    AbstractionInventory, AbstractionRate, AbstractionTimeBasis,
    Article30Reading, Article30ReadingSelection, DecisionStatus,
    PermitEvidence, PermitEvidencePurpose, PermitScope,
    assess_limited_abstraction, permit_evidence_scope,
)

location = Location(
    Reach("river-reach", "1", WaterBody("river", "1")),
    CalculationSection("intake", "1"), "mapping-1",
)
period = Interval(
    datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC),
)
scope = PermitScope(location, period, "synthetic", "reference-A", "data-1", "config-1")
provenance = Provenance(
    "own synthetic input", "synthetic", "reference-A", "example-1",
    "data-1", "config-1", ProductionMethod.ILLUSTRATIVE, CorrectionState.ORIGINAL,
)

def supported(purpose, subject):
    return PermitEvidence(scope, EvidenceFindings(
        permit_evidence_scope(scope, purpose, subject), provenance,
        Computability.COMPUTABLE, NumericalValidity.VALID, Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED, OfficialAdmissibility.PENDING,
        ("synthetic scenario only",),
    ))

inventory = AbstractionInventory(
    scope,
    (AbstractionRate("A", Flow(700, "l/s")), AbstractionRate("B", Flow(700, "l/s"))),
    AbstractionTimeBasis.INSTANTANEOUS_ENVELOPE,
    None,
)
inventory = replace(inventory, evidence=supported(PermitEvidencePurpose.ABSTRACTION_ENVELOPE, inventory))
choice = Article30ReadingSelection(
    Article30Reading.PER_ABSTRACTION_1000, DecisionStatus.HYPOTHETICAL,
    "FOEN 2000 pp. 20, 23; explicit scenario interpretation",
    None,
)
choice = replace(choice, evidence=supported(PermitEvidencePurpose.ARTICLE_30_READING, choice))
result = assess_limited_abstraction(Flow(7000, "l/s"), inventory, choice)
assert result.combined_abstraction == Flow(1400, "l/s")
assert result.eligibility.finding.value == "pass"
assert result.selection.status is DecisionStatus.HYPOTHETICAL
```

## Source and test crosswalk

Public sources: [German GSchG, consolidation 2025-08-01](https://www.fedlex.admin.ch/eli/cc/1992/1860_1860_1860/de),
[German GSchV, consolidation 2025-12-01](https://www.fedlex.admin.ch/eli/cc/1998/2863_2863_2863/de),
and [FOEN 2000 guide](https://www.bafu.admin.ch/dam/de/sd-web/DURPl8AmZvgE/angemessene_restwassermengenwiekoennensiebestimmtwerdenwegleitun.pdf).
Guide citations use printed pages, not PDF page indices. The older guide supports
its named per-abstraction reading; it cannot override amended law. These links
identify sources, not a new legal-currency certification.

All tests below are in `tests/test_swiss_permits.py`. Arithmetic comparisons use
exact `Fraction` values with zero tolerance. No restricted handover content or
application data is needed to execute them.

| Clause | Operation/input | Expected and actual witness | Test |
|---|---|---|---|
| Act 4(i),29; Ordinance33(1) | `assess_permit_scope` | positive intake Q347 and mixed 50/0 downstream: only perennial section receives Art30 scope | `test_perennial_intake_and_mixed_downstream` |
| Act29 common use | context classification/evidence | within common use outside Art29; missing evidence unresolved | `test_common_use_and_missing_applicability` |
| Act4(b),29(b),34 | lake/groundwater/spring effect classification | significant: analogous protection; insignificant: outside Art29; unknown: unresolved; spring retains groundwater applicability | `test_lake_groundwater_effect_routes`, `test_spring_is_groundwater_for_significant_effect_applicability` |
| Ordinance33(2); Guide p15 | nonperennial intake measures | q=0 without measures unknown; supported measures pass that process screen, not permission; perennial downstream does not create an Art30 intake route | `test_nonperennial_intake_requires_nature_fisheries_evidence`, `test_nonperennial_intake_does_not_create_art30_from_perennial_downstream` |
| Ordinance33(1); Guide p15 | perennial intake, nonperennial downstream | missing nature/fisheries measures at dry section prevents a complete scope screen | `test_nonperennial_downstream_section_keeps_nature_fisheries_protection` |
| Arts80ff; separate supplied duty | concession route | remediation derivation unknown; supplied duty route needs no Q347/table sizing | `test_existing_concession_and_supplied_duty_do_not_assign_table` |
| Act30(b); Guide pp20,23 | two named readings | two 700 l/s intakes, q=7000: aggregate fail, per-intake pass, no-selection unknown | `test_two_700_intakes_both_readings_and_no_default` |
| Act30(b) | exact thresholds | q5000/intake1000 passes; 1000.001 or q4999 fails; q0 excluded | `test_article_30_b_exact_thresholds` |
| Guide p23 | instantaneous vs mean | passing interval mean remains unknown | `test_daily_mean_is_not_instantaneous_evidence` |
| Act30(c) | annual volume and purpose/source | spring80 and groundwater100 pass; +0.001 fails; lake/other-purpose fails; leap year seconds retained | `test_drinking_annual_source_thresholds_and_leap_duration`, `test_annual_means_need_complete_year_and_drinking_purpose` |
| Act35(3) | specialist names and gross power | 299.999/300 do not require federal hearing; 300.001 does; omitted specialist fails despite missing hearing | `test_federal_hearing_threshold_is_strict`, `test_specialist_names_drive_failure_despite_missing_hearing` |
| Ordinance35(1) | EIA report inclusion | residual report and federal hearing separately required | `test_eia_residual_report_and_federal_hearing_are_separate` |
| Ordinance35(2) | FOEN document alternatives | supported opinion OR revised draft passes; unrelated/rejected evidence cannot pass | `test_non_eia_federal_route_requires_foen_opinion_or_revised_draft`, `test_valid_foen_draft_is_not_discarded_for_rejected_opinion` |
| Evidence isolation | expected-use and full-subject binding | wrong use unknown; rebinding section/config/reference-kind rejected; failure survives missing | `test_unrelated_accepted_use_cannot_establish_limited_abstraction`, `test_evidence_cannot_be_rebound_to_another_section_in_same_reach`, `test_evidence_cannot_change_configuration_version`, `test_evidence_cannot_silently_change_reference_kind`, `test_failure_survives_missing_selection_and_inventory_evidence` |

Content-rebinding regressions cover opinion-to-hearing relabelling, document
issuer/reference/consulted-list changes, reading/status changes, intake rate and
annual-volume changes, and applicability/permanence reclassification. Each stale
review returns unknown, while freshly reviewed records retain successful paths.
See `test_reviewed_document_content_cannot_be_replaced`,
`test_reviewed_reading_and_status_cannot_be_replaced`,
`test_reviewed_inventory_rates_cannot_be_replaced`,
`test_reviewed_annual_volume_cannot_be_replaced`, and
`test_reviewed_applicability_and_permanence_cannot_be_replaced`.

Run `uv run pytest -q tests/test_swiss_permits.py`. The implementation evidence
crosswalk records the integrated revision and executed repository-wide checks.
