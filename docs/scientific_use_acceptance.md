# Scientific-use implementation acceptance

Effort: https://github.com/hydrosolutions/taqsim/issues/29

This is software acceptance for U10 and common C2/C3/C5/C6, derived from D.8, D.7, D.6 and Appendix A step 5. It is not scientific certification or adoption of tolerances. The daily diagnostic module uses the independently delivered calendar primitive. Annual estimates, Swiss Q347, the hypothetical sanitary method and Kazakh allocation retain their separate methods.

## Actual-versus-expected crosswalk

The tests use explicit hypothetical study settings. Fractions and integer counts are compared exactly unless stated otherwise. `tests/test_scientific_acceptance.py` is abbreviated SA; `tests/test_pattern_diagnostics.py` is PD.

| Requirement / operation | Actual = expected; declared tolerance | Executed witness |
| --- | --- | --- |
| D.8 equality; `assess_scientific_use` | Absolute errors `3,3`; limit `<=3 days`: accepted; official pending; exact | SA `test_equal_maximum_passes_and_official_pending_is_independent` |
| D.8 stricter equality; `compare_criterion` | Error 3; limit `<3`: fail; exact | SA `test_strict_equality_is_configured_not_rounded` |
| C3 failure plus incomplete | Known error 4 > 3; second case missing: FAIL + INCOMPLETE | SA `test_failure_survives_missing_other_case` |
| C3 partial aggregate bounds | MAX with known 4 > 3: FAIL + INCOMPLETE; symmetric MIN and strict equality also fail; unresolved mean stays unknown | SA `test_partial_aggregate_only_claims_mathematically_proven_failure` |
| U10 missing criteria | Numerical candidate retained; acceptance `not accepted`, reason `acceptance basis missing` | SA `test_missing_acceptance_basis_preserves_exploratory_number` |
| U10 short-record/rating screen | Supported limited use: indicative; sizing prohibition retained; no record-length default | SA `test_short_record_indicative_no_length_gate_and_rating_restriction_survives` |
| U10 rating sizing prohibition | Same restriction prevents sizing even with indicative label | SA `test_rating_cannot_size_even_with_indicative_label` |
| U10 trend/restrictions | Untreated trend: FAIL; independently inherited prohibition survives | SA `test_untreated_trend_and_inherited_restrictions_bind` |
| C2 full identity isolation | Changed target, method identity, calendar, provenance, full Location, climate, population, reference/result content identity or scalar: no acceptance transfer | SA `test_no_acceptance_transfer_when_scope_string_coincides`, `test_full_physical_climate_population_and_value_identity` |
| C2 frozen input record | Same-version relaxed limit cannot reuse prior evidence; forged output acceptance cannot promote failed inputs | SA `test_frozen_criteria_cannot_change_without_new_validation_profile`, `test_forged_assessment_cannot_promote_failed_evidence` |
| D.8 withholding | Training/exposed/excluded cluster overlap, shared case, validation before freeze or empty withheld set: failure | SA `test_withholding_cannot_be_claimed_over_contaminated_or_absent_evidence` |
| D.8 tuning disclosure | Missing revision metadata refused; exposed validation cannot be recycled; declared nested new withheld evidence passes | SA `test_revisions_need_new_version_old_result_and_reserved_validation` |
| U10 separate rare tail | Accepted annual P50 does not accept P99; missing independent rare-tail evidence stays unknown/not accepted | SA `test_rare_tail_separate_from_less_extreme_holdouts_and_annual_acceptance` |
| U10 daily minimum evidence | Four distinct mandatory metric limits produce successful daily scientific use; string-only annual/shape assertions do not | SA `test_daily_success_requires_distinct_quantitative_diagnostic_limits`, `test_daily_shape_cannot_pass_on_annual_or_string_only_evidence` |
| U10 minimum error | Signed minimum error +2 exceeds +1 m3/s despite other passing shape metrics; not accepted | SA `test_failed_signed_minimum_does_not_disappear_in_other_good_shape_metrics` |
| U10 non-waivable advisory conditions | Failed target transfer remains required; favorable-case subset cannot bypass full withheld coverage | SA `test_advisory_required_applicability_failure_cannot_be_waived`, `test_nonwaivable_advisory_cannot_select_favourable_validation_subset` |
| U10 disaggregation | Missing co-located low-tail/spell/propagated uncertainty checks block daily and annual-resolution duration-minimum products | SA `test_daily_disaggregation_requires_colocated_tail_spells_and_propagation`, `test_disaggregated_duration_minimum_cannot_avoid_daily_evidence_by_annual_resolution` |
| U10 coarse independence | Explicit dekadal statistic accepted independently; February final dekad retains 8 days; Q347/daily Q95 renaming refused | SA `test_dekadal_actual_intervals_and_name_preserved_without_daily_equivalence` |
| D.8 seasonal share | Leap-Feb constant-flow share `2900/366 percent`; percentage-point error retained, exact Fraction | PD `test_seasonal_share_actual_leap_year_and_percentage_point_errors` |
| D.8 half volume | Plateau first marker day31; fractional marker `94/3 days`; wrapping season refused; exact Fraction | PD `test_first_half_volume_plateau_fractional_day_and_nonwrap` |
| D.8 minimum diagnostic | Three-day annual minimum Q2 with two actual zero predecessor days vs seasonal Q6; no wrapping/fill | PD `test_annual_minimum_requires_real_predecessor_and_differs_from_seasonal` |
| D.8 signed/absolute error | Positive duration error +4, absolute4, relative1; reverse -4, absolute4, relative-1/2 | PD `test_seasonal_minimum_and_signed_error_preserve_overestimation` |
| D.8 strictly-below spells | Equality breaks runs; opposite year-edge runs never join | PD `test_strict_below_spells_do_not_join_year_edges` |
| C5 zero versus missing | Zero annual/seasonal volume: undefined share/marker; zero reference with absolute error3 retains relative None | PD `test_zero_volume_undefined_share_and_marker`, `test_zero_reference_retains_absolute_errors_and_undefined_relative` |
| C5 invalid support | Gaps/partial/coarse/overlap/mixed identity/excluded warmup refused; row order independent | PD `test_public_daily_boundary_refuses_invalid_support`, `test_row_order_independent_and_incomplete_year_refused` |
| C6 executable annual-only example | Indicative; actual3 <= limit3 m3/s; official pending; rating restricted; absent validation not accepted | SA `test_runnable_annual_screening_example`; `uv run python examples/scientific_use.py` |
| U10 development limitation | 160 source rows; 21/21 dry minimum overestimates; benchmark4/4; longer training3/4; arithmetic tolerance1e-12 | `scripts/check_pattern_development.py` against held authoritative CSV/JSON |

No production module or API is named after the delivery ticket. No unrelated production components were changed. Existing source profiles are not renamed, and no new scientific threshold is a package default.

## Executed commands

```console
uv run pytest tests/test_scientific_acceptance.py tests/test_pattern_diagnostics.py -q
uv run python examples/scientific_use.py
uv run pytest -q
uv run ruff format --check
uv run ruff check
uv run ty check
```

Run the private-source arithmetic check from the repository root with the two explicit held file paths:

```console
uv run python scripts/check_pattern_development.py /path/to/bundle/report_snapshot/method_development_support/primary_case_metrics.csv /path/to/bundle/report_snapshot/method_development_support/RECOMPUTED_SUMMARY.json --expected-csv-sha256 cc31698c21bf03bf87dbaf5de851351b5be19be5044908c77916da9fe661f864
```

The check reads caller-supplied files only. It neither bundles the original cases nor conducts a validation study. Its arithmetic tolerance is 1e-12, not an application tolerance. Source hash disagreement is separately visible from numerical agreement. Exact final HEAD and gate counts are recorded in the PR and delivery evidence because they cannot self-reference inside the same commit. Dependencies remain locked by `uv.lock`.

## Authoritative source identity

Only the held `fishy_taqsim_handover_candidate_2026-09-19` bundle supplies this proposed method. Its candidate label is historical; the accepted vision selects it as authoritative. No private chapters, raw development CSV/JSON or primary reference originals were copied into Git. The following hashes identify the sections used to derive the contracts:

| Bundle-relative source | SHA-256 |
| --- | --- |
| `IMPLEMENTATION_BRIEF.md` | `0ad077a69f27af74dd6cf340830438576d020d66b9bf5a8d568bb84eb5c757c8` |
| `ACCEPTANCE.md` | `851fc64c35e827fa3a072750f760108ddd5f445684ba65f85bb4037758b047ba` |
| `SHA256SUMS.txt` | `7dcf598b23a282a88a12af6ca2aee89795df27a119842ed17603403398dc97f0` |
| `report_snapshot/part4_scientific_acceptance.qmd` | `c09d0d3afbb1766638c93951432ba09408f28135d5e2765d5579fb81079c3bd6` |
| `report_snapshot/part4_statistical_estimation.qmd` | `10bb9e8feaaab5199575d1dbf0c2fd2a50c5867b5a55a92806294853c821a5df` |
| `report_snapshot/part4_design_patterns.qmd` | `b95f62ed797f174df926462a154834077126dfd65e995f445b608ef1426ba56e` |
| `report_snapshot/appendices.qmd` | `e520499b91cc72d25dbec430a266d672331c1e732c284129b4d125db1ea9eb76` |
| `references/supporting_methods/meth_wmo_1029_low_flow_2008_en.txt` | `f6edeb7c41c7ef44f2f007ecc5c16c772ec0282530dd365d529721b0a228513f` |
| `references/supporting_methods/meth_wmo_1029_low_flow_2008_en.pdf` | `1421a099bf73144be11945e6eeab8cd4daf9f6bb6f42547ebcda59a6d078a40b` |
| `references/supporting_methods/knoben_benchmarks_2019.xml` | `b92516c06688cf9a18b6e93a4984d42780429da398f13c38c6de03b4cda248d0` |
| `references/supporting_methods/usgs_lowflow_frequency_2025_summary.txt` | `55eea73d9dea805d7b2119797e37f999f76bdf605c43cda8ad74fb94de9589db` |

D.8 supplies the proposed acceptance procedure and statuses. D.7 supplies statistical distinctions and climate restrictions. D.6 supplies conditional-pattern method boundaries and development limitations. Appendix A step5 supplies rating and actual coarse-interval restrictions. WMO1029 §§7.3–7.9 and chapters3/9/10 support purpose-specific data, dependence and applicability appraisal; they supply no universal limits here. Knoben2019 supports purpose-dependent metrics and explicit benchmarks. The USGS2025 text is a labelled authored summary, not the full primary webpage, and supplies no ecological defaults.

### Retained source-attribution discrepancy

- Actual/package-listed CSV hash: `cc31698c21bf03bf87dbaf5de851351b5be19be5044908c77916da9fe661f864`.
- Actual/package-listed summary JSON hash: `466b874876a11de8c14944fe4fba5a4d3edcaff136aaa543f3a63c8760fca4c3`.
- Summary's embedded `source_cases_sha256`: `5371339d4266c19f2a7266f56e39bbebb33f6ce22de64316428cffb79af0b66f`.

The embedded value does **not** identify the supplied CSV. The arithmetic check reports `embedded_source_hash_check: fail: stale source attribution`. The actual package hashes match the authoritative files. Reaggregation matches every group count and reported metric within 1e-12, including 21/21, 4/4 and 3/4. The supplied originals were not modified. Numeric agreement is not a claim that the stale embedded attribution was verified.
