# Order 111 water classification

`fishy.water_classification` evaluates a selected set of source rows against all six classes. It does not select an overall national class. It does not import Uzbek activation conditions or use categories.

Run the supplied example:

```sh
uv run python examples/water_classification.py
```

The synthetic saprobity values 0.5, 1.25, 2, 3, 3.75 and 4.1 match selected-row classes 1 through 6. The example selects closed range endpoints explicitly. This one-row result is not a complete water-body classification.

## Inputs and results

1. Select physical row IDs from `water_classification_catalogue.SOURCE_ROWS`.
2. Construct `Order111Profile` with exact location, interval, scenario, sampling basis, scope and calculation date. `required_rows` must be nonempty and unique.
3. Supply `ClassificationObservation` records. `SourceValue` holds exact rational observation bounds, the printed source unit and the exact determinand name. Keep total/dissolved and ion/element reporting forms separate. No chemical or unit conversion occurs. Empty unit text records an empty source field, not an inferred concentration unit.
4. Supply attributable `CellInterpretation` records where needed.
5. Call `assess_order111(profile, observations)`.

`ClassMatches.classes` retains each raw source row, raw cell, observation, interpretation and `CheckSummary`. `supported_matches` contains every class whose selected required cells pass. `unknown_classes` contains classes not resolved by those cells. A known failure survives other missing checks with incomplete coverage. A printed overlap can return multiple supported matches. A printed gap can return no matches. There is no best-match, nearest-class, worst-row or smoothing algorithm.

Use `ClassAssessment.summary` as a selected-profile numerical check in a wider assessment. Keep the profile, limitations and source identity attached. Numerical success does not establish scientific adequacy or official admissibility. Use the existing evidence operations for separately scoped scientific/official findings.

### Source-cell interpretations

- Explicit `<`, `>`, `≤` and `≥` retain their strictness. Observation bounds that straddle a threshold remain unknown.
- A bare number has no automatic upper-limit meaning. Select `bare_operator` with evidence for that physical row and class.
- A range with an unstated endpoint needs explicit `RangeMeaning.CLOSED` or `OPEN`. Printed inequalities still control their own endpoints. Gaps are not filled.
- The pH class-6 compound cell requires the explicit `OUTSIDE` disjunction. Equality at 6 or 9 is outside neither strict branch.
- Calcium class 6 requires industrial 150 versus other-use 180 selection. Phosphate class 3 requires Astana 3.5 versus outside-Astana 0.7 selection. Their bare operators remain separate choices.
- Suspended matter classes 1–5 require a same-scope supported background in the observation and an explicit bare-number operator for the printed increment. Class 6 omits the arithmetic plus sign; it stays unresolved.
- Row 70 stays unresolved without `RatioTypography`. The PDF visibly prints baseline `103` and `102`. Literal-digit and powers-of-ten choices are labelled candidates, not authenticated transcription repairs. The reversed class-3 range additionally needs `CLOSED_SORTED` to evaluate; ordinary `CLOSED` does not reorder it. Raw cells never change.
- Merged summer/winter temperature cells, missing dissolved-arsenic units, bacterial-count unit/exponent ambiguity (rows 68–69), absence/traces and macro-benthos absence remain unassessed. No qualitative value becomes zero. No temperature or oxygen process is simulated.

Source notes remain attached even when numerical arithmetic can run. Unexplained markers do not become invented footnotes. Unknown meanings prevent a claim of full source replication.

## Scope and commencement

The source numerical table covers rivers, canals and in-channel reservoirs. `WaterScope` explicitly excludes lakes and seas, including the Caspian Sea, Aral Sea and Lake Balkhash. Other or unknown scope cannot pass. A terminal receptor can still require a separate ecological assessment.

The held Order states commencement on **10 June 2025**. A calculation date or observation interval before this date cannot produce applicable source matches. This date check is not a current-law or repeal search.

## Use mapping and treatment

`assess_order111_use(WaterClass, WaterUse, interpretation)` maps a supplied class. It does not numerically infer the class or authorise a dated activity. `WaterUse` retains all 13 Table-2 category/treatment rows. Both attributed table findings remain in every result.

For class-4 intensive drinking use:

| Selection | Finding |
|---|---|
| No selection | Unresolved |
| `UseMapping.DESCRIPTIVE` with evidence | Conditional on intensive/deep treatment at intakes |
| `UseMapping.MATRIX` with evidence | Not permitted by that mapping |

Other wording differences remain visible too, including not-recommended versus negative mapping. The class-5 sentence has ambiguous settling-qualification scope for industrial uses; its descriptive finding remains unresolved while the matrix plus is retained. Class-3 drinking conditions require more effective purification, not permission for simple-treatment-only. Table-1 preparation conditions survive a matrix selection. A matrix plus is only a category/type-of-treatment entry, never a claim that treatment worked. Class-6 special processes retain the condition that they do not require water-quality standards.

Separate sanitary references to **ҚР ДСМ-138** and **ҚР ДСМ-44** are returned for their drinking and irrigation scopes. Their limits are not silently merged into this table. The irrigation sanitary note is retained separately from the matrix's plus for untreated class-4 irrigation. No output proves sanitary compliance, treatment adequacy, permitting or legal certification.

## Provenance and supported coverage

The catalogue is a derived transcription of the held 12-page CAWater replica of Order **111-НҚ, 4 June 2025**, retrieved 17 September 2026. Source URL: <https://cawater-info.net/bk/water_law/pdf/kz-p111-2025.pdf>. SHA-256: `c8e0aa22c3c2eb35269e858120ffda7d61de409b3c7e702cb2cb9b9f2c126d38`.

It contains **84 physical rows and 504 cells** from PDF pages 2–8. Layout-only whitespace is collapsed. Chemical forms, missing units, duplicate printed row 41, absent row 42, qualified cells and source notes remain distinct. The temperature row's two merged cells are repeated only to retain column coverage, with an explicit layout note. Source text for Tables 1–2 is represented as attributed use findings, not reproduced as the full private report or PDF.

PDF pages 8–11 were visually inspected for row-70 typography, exclusions and the class-4 conflict. The secondary HTML is not authoritative: it corrupts row70 and has an unfilled approval header. Publisher-direct authentication and source currency remain unresolved. A former zan.gov.kz address does not authenticate this copy.

## Executed acceptance crosswalk

Tests use exact `Fraction` arithmetic; no floating-point tolerance is required. Test file: `tests/test_water_classification.py`.

| Source / requirement | Public operation / input | Observable test |
|---|---|---|
| Numerical table pp2–8, six classes | `assess_order111`, source row63 | `test_numerical_match_each_class_without_false_unique_algorithm` |
| Printed gaps / overlaps / bare limits | all-class selected-row evaluation | `test_printed_gap_not_smoothed`, `test_duplicate_limits_preserve_multiple_matches`, `test_bare_values_require_explicit_direction_and_keep_raw` |
| Strict signs, ranges, pH | `CellInterpretation`, interval comparisons | `test_printed_operators_and_open_ranges`, `test_range_choices_and_ph_disjunction` |
| Notes *** / ****, forms and units | qualified calcium/phosphate choices, exact `SourceValue` | `test_calcium_qualification`, `test_astana_phosphate_qualification_and_no_ion_conversion` |
| Row12 background and omitted plus | supplied background; class6 unresolved | `test_background_preserved_and_missing_class6_plus_not_repaired` |
| Row70 PDF typography | explicit candidates; unresolved default | `test_row70_typography_never_silently_repaired` |
| Raw source anomalies and unsupported cells | `SOURCE_ROWS`, unknown outcomes | `test_unresolved_cells_and_raw_catalogue_identity` |
| Note *, commencement clause5 | `WaterScope`, dated profile | `test_applicability`, `test_commencement_and_exact_identity_support` |
| Tables1/2 all category rows, class4 conflict | `assess_order111_use` | `test_every_matrix_row_and_class`, `test_class4_drinking_conflict_all_branches`, `test_descriptive_conditions_and_separate_sanitary_notes` |
| Missing/unsupported/invalid; C2/C3/C5 | immutable profile and typed observations | `test_known_failure_survives_missing_required_cell`, `test_invalid_domain_inputs_and_immutable_scenarios` |

Supported cell computation, explicit candidate interpretation, and unresolved source meaning are different coverage states. This module does not claim full legal replication.
