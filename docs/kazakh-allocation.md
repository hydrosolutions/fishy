# Kazakh annual allocations and seasonal reports

Run `uv run python examples/kazakh_allocation.py`. The example uses supplied synthetic
natural annual volumes and monthly shapes. It needs no Uzbek inputs, actual-year
selection or simulator. Its annual totals for design 25/50/75/95 are 100/80/60/40
million m³. The median-normalised coefficients are 1/0.8/0.6/0.4. They reproduce
these initial volumes, not reduce them a second time.

## Inputs and independent operations

- `fishy.design_conditions.DesignClass` identifies the four annual design years.
  Higher exceedance is drier. These labels are not daily percentiles.
- `NaturalAnnualReference` contains versioned `Location`, historical reference
  `period`, natural quantiles, observation route, `Provenance` and scoped
  `EvidenceFindings`. Its P50 is a median, not an arithmetic mean.
- `initial_allocation(reference, design, route)` supports probability shift and the
  explicitly selected median-normalised initial interpretation. `route=None`
  preserves the reference but leaves the operation unresolved. A zero denominator
  makes the coefficient undefined. An independently supported zero remains usable
  through probability shift.
- Insufficient observations require imported annual/monthly reconstruction and
  naturalisation evidence. Fishy does not reconstruct a series or judge record
  sufficiency by length. The `annual_monthly_reconstruction` finding identifies
  the preparation evidence; monthly distribution still needs its own shape.
- Absent observations use `transfer_allocation`. Supply a `PreparedTopology`,
  recipient `River`, `DonorRelation`, `InitialCoefficient` and explicit
  `DonorChoice.RECEIVING_PARENT`. The actual receiving parent must own the donor
  section. Missing relation, coefficient, acceptance or choice yields further study,
  never a guessed zero or nearest gauge. Coefficients need initial-stage derivation
  evidence; a post-adjustment coefficient cannot use that product identity.
- `seasonal_schedule(initial, year, choice, shape)` consumes a supported imported
  `SeasonalShape` and explicitly selects design-class or shifted-class shape. The
  receiving calendar is separate from the historical reference period. Shapes must
  be nonnegative, contiguous and have exact duration-weighted mean one. Use exact
  `Fraction` ordinates for normalised imported patterns. No silent renormalisation
  or mandatory Uzbek shape algorithm is applied.
- The result's `samples` are native `FlowSample` records. Corrections can consume
  them directly. Pass a corrected schedule to `appendix1_report` with explicit
  `ScheduleStage.CORRECTED`; it recomputes volumes without rescaling to the initial
  allocation. It does not certify that corrections are ecologically or legally valid.

### Exact evidence products

All scopes also require the exact reach identifier, reference member and period.
The product provenance must match the reference or shape provenance.

| Product | Intended use | Period |
|---|---|---|
| `natural_annual_reference` | `initial_allocation` | Historical reference |
| `annual_monthly_reconstruction` | `initial_allocation` | Historical reference |
| `receiving_parent_transfer` | `initial_allocation` | Recipient historical reference |
| `initial_coefficient_P25` (also P50/P75/P95) | `initial_allocation_transfer` | Supported donor derivation period |
| `seasonal_shape_P50` (selected natural exceedance) | `seasonal_allocation` | Receiving calendar year |

Scientific acceptance for the stated use may be indicative. Official admissibility
is retained separately and never promoted by arithmetic. Prohibited uses, wrong
scope, missing acceptance or excluded warm-up periods prevent dependent supported
allocations. All evidence remains in results, including transferred coefficient
findings. A result is not a water source, consumptive demand, issued duty or delivery.

## Appendix 1 values

`appendix1_report(initial, year, samples, stage, identity)` returns twelve monthly
cells and an annual cell. `ReportingIdentity` retains the basin, river, physical
location and water-management section code. Omitted reporting identity is an
explicit report limitation, not an inferred basin.

Each cell supplies typed mean discharge (m³/s), volume (m³), exact `million_m3`
and annual share in percent. Actual interval durations retain leap days. A zero
annual volume has undefined shares (`None`), not zero percentages. Unavailable,
unsupported and outside-horizon schedules stay distinct. Partial monthly volumes
remain useful when an annual total is unavailable, but their annual shares are
undefined. Annual-only and quarterly means do not manufacture monthly values.
The supported initial allocation remains on `report.initial` even with no schedule.

[Prepared basin topology](basin.md) covers river/section context, sequencing and
attributed tributary accounting. [Review and operational evidence](kazakh-review.md)
covers temporal applicability, change triggers and supplied current-year adjustment.

## Executable source crosswalk

Governing source: Order 179-НҚ, 23 July 2025, held Ministry PDF. The equations on
PDF pages 7–8 were visually checked; their inconsistent printed denominator remains
an interpretation, not an official correction. Detailed candidate definitions are
attributed to the accepted source-interpretation register. No source copy is published.

| Source | Operation | Executed discriminator (`tests/test_kazakh_allocation.py`) |
|---|---|---|
| 15–16, 21 | reference + reconstruction evidence | `test_observation_routes_and_exact_evidence_scope` |
| 17(1), 18–20, Appendix 2 | initial allocation | `test_both_initial_routes_not_second_reduction`: exact 100/80/60/40; alpha 1/.8/.6/.4 |
| 20 denominator interpretation | median-normalised / shift | `test_zero_ratio_unidentified_but_independent_shift_survives` |
| 22 | receiving-parent transfer | `test_receiving_parent_transfer_success_missing_and_incompatible`: 100 × .8 = 80 million m³; missing/stage mismatch further study |
| 7, 19(6) | seasonal schedule | `test_explicit_shape_operators`: [16,12,8,4] vs [4,8,12,16] m³/s, same exact annual volume |
| 19(6), scientific support | shape choice/evidence | `test_missing_choice_pattern_and_unsupported_pattern_keep_annual` |
| 11, Appendix 1 | corrected schedule report | `test_appendix1_leap_months_corrected_volume_no_renormalisation`: February 29 × 86400 × 10 m³ |
| Appendix 1 partial reporting | report cells | `test_zero_missing_unsupported_outside_and_partial_are_distinct`, `test_reporting_identities_and_meaningful_annual_only_result` |
| Common C2/C5 | identity/finite/duplicate support | `test_invalid_inputs_identity_immutability_warmup`, `test_single_design_class_carrier_and_invalid_domain` |

`test_scaled_observed_pattern_cannot_become_observed_discharge` first demonstrated
an observed-pattern provenance error on the real seasonal path, then passed after
repair. Calculated schedules are never labelled observed readings. Generated
provenance retains attributed scientific/official statuses, reasons, prohibited uses
and input limitations. The complete pattern evidence also remains in the seasonal
result.

All numerical expectations use exact rational arithmetic, with no tolerance. The
example formats only displayed percentages. This capability does not by itself
implement ecological bounds, spawning, quality or complete source replication.
Those assessments consume the attributed schedule and their own supplied evidence.
