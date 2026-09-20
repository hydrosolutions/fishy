# Kazakh source applicability and review

`fishy.kazakh_review` assesses supplied review and operational evidence. It does
not select a design class, forecast hydrology, or issue a delivery duty.

## Temporal applicability

Call `order179_applicability(calculated_on, paragraph, source, publication)`.
`source` is immutable `Provenance`. An optional `FirstPublication` supplies the
first official publication date and its evidence. An upload, signature or
registration date is not a substitute.

Order 179 enactment clause 4 defers methodology paragraph 11 until 2027-01-01.
Other paragraphs become effective the day after the supplied first publication.
Without that evidence their applicability is `UNKNOWN`, even after 2027.
The calculation date does not authenticate the held source or establish currency.

## Study review

Call `assess_review(applicability, last_study, basin_conditions, new_evidence)`
with paragraph 23 applicability. Supply a dated `StudyReview` and two separate
`BasinChange` inventories. A known changed/unchanged finding needs provenance.
Missing inventories use `ChangeState.UNKNOWN`.

A review becomes due at the fifth calendar anniversary of the previous
study-based review. The explicit conservative convention for February 29 is
February 28 five years later. Changed hydrological, economic or ecological basin
conditions, or new evidence, independently trigger revision. A known trigger
survives missing study evidence. No known trigger plus missing evidence gives an
unknown result, not `NOT_DUE`. A future study cannot reset the clock.

The trigger inventory and source applicability remain separate. `REQUIRED`
means the supplied history triggers the source's review rule; it is not an
assertion of an enforceable historical duty when applicability is unknown or
not yet in force. Review and change records are caller-supplied study findings,
not an automated scientific acceptance or legal certification.

## Actual-year adjustment

`assess_actual_year_adjustment(applicability, baseline, adjusted, scope, evidence)`
assesses one supplied operational interval under paragraph 9. Both flows are
`FlowSample` records. They must have the same physical location, mapping,
interval, scenario and reference identity. Their data/configuration versions
may differ. The caller supplies the adjusted flow; no universal coefficient is
invented from a forecast.

`ActualYearEvidence` keeps a decision issue date, immutable decision provenance,
and separate forecast/current-condition `EvidenceFindings`. The adjusted sample
must carry the decision provenance. Evidence must be issued by the calculation
date and match the requested `EvidenceScope` and scenario. Evidence provenance
must also identify the requested reference member and must not exclude the
requested period as warm-up. A matching scope label cannot override unsupported
provenance. Existing
`permitted_use` checks preserve restrictions and scientific adequacy. Official
admissibility remains an independent supplied finding, never inferred from a
successful numerical or scientific assessment.

Supported interval volumes and their signed difference are computed exactly.
For February 2028, 10 → 8 m³/s gives 25,056,000 → 20,044,800 m³, a change of
−5,011,200 m³. A later issue supplying 9 m³/s gives 22,550,400 m³ and leaves the
previous result unchanged. No design allocation is modified. Zero remains zero;
missing, unsupported, partial or excluded warm-up input does not become zero.
Supported arithmetic remains visible when forecast evidence is missing, but
that evidence assessment cannot pass. A known prohibited use remains a failure
when the other required evidence is missing.

A passing operational evidence check does not establish all ecological conditions,
full daily coverage, source compliance or successful delivery. Temporal
applicability stays separate, permitting explicit hypothetical calculations.

## Executable crosswalk

Run `uv run pytest tests/test_kazakh_review.py -q`.

| Source / behavior | Public operation | Executed tests |
|---|---|---|
| Enactment clause 4; methodology 11 | `order179_applicability` | `test_deferred_paragraph_11_without_publication`, `test_other_provisions_require_publication_and_start_after_its_day` |
| Paragraph 23, five-year study cycle | `assess_review` | `test_five_calendar_year_deadline_inclusive`, `test_missing_review_cannot_pass_and_leap_anniversary_is_explicit` |
| Paragraph 23, changed basin/new data | `assess_review` | `test_known_basin_trigger_survives_missing_study_and_new_evidence_inventory`, `test_new_evidence_triggers_even_when_recent_study` |
| Paragraph 9, supported operational decision | `assess_actual_year_adjustment` | `test_successful_supplied_actual_year_decision_exact_leap_month_volumes` |
| Paragraph 9, missing and prohibited evidence | same | `test_missing_operational_evidence_keeps_arithmetic_but_not_pass`, `test_known_evidence_restriction_survives_missing_forecast`, `test_unmatched_or_unaccepted_evidence_cannot_pass` |
| C2/C5, issue and physical identity | same | `test_wrong_identity_future_issue_or_unversioned_decision_rejected`, `test_operational_change_cannot_mix_reference_or_scenario` |
| C3/C5, presence and support | same | `test_absence_is_not_zero`, `test_present_zero_partial_and_warmup_support` |

These synthetic examples use exact rational arithmetic, with zero numerical
tolerance. The publication date in the tests is hypothetical, not a verified
first-publication claim. Source pointers: held Ministry Order 179 Russian PDF,
enactment clause 4 on page 1; methodology paragraph 9 on page 4; paragraph 23.
This component does not implement other paragraphs or authenticate sources.
