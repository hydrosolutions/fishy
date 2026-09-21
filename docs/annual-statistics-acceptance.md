# Annual statistics: source and executed acceptance

Effort: https://github.com/hydrosolutions/taqsim/issues/29

This is implementation evidence for the selected proposed Uzbek operator, not
scientific certification, national policy, a WMO-mandated family or an adopted
standard. Synthetic tolerances below only test floating-point arithmetic.
The private authoritative bundle is `fishy_taqsim_handover_candidate_2026-09-19`.
No bundle/report/reference material is distributed here.

## Source identities

D.7 (`sec-statistical-estimation`) rules 1–5 control these operators.
D.8 (`sec-scientific-acceptance`) controls separation of annual use, daily use,
tail applicability and official permission. The brief F2/section 4(1–2) and
acceptance U1/U10, C2/C3/C5/C6 identify the required behavior. WMO 1029 §§7.3–7.9
supports plotting positions, dependence, zero treatment and family sensitivity;
chapters 3, 9 and 10 support data appraisal and application context. The labelled
USGS summary explains annual-minimum return periods, which this annual-mean
module does not relabel as daily probabilities. Knoben et al. (2019),
DOI `10.5194/hess-23-4323-2019`, supports purpose-specific benchmarks, not a
universal threshold.

| Local source path | SHA-256 |
|---|---|
| `IMPLEMENTATION_BRIEF.md` | `0ad077a69f27af74dd6cf340830438576d020d66b9bf5a8d568bb84eb5c757c8` |
| `ACCEPTANCE.md` | `851fc64c35e827fa3a072750f760108ddd5f445684ba65f85bb4037758b047ba` |
| `SHA256SUMS.txt` | `7dcf598b23a282a88a12af6ca2aee89795df27a119842ed17603403398dc97f0` |
| `report_snapshot/part4_statistical_estimation.qmd` | `10bb9e8feaaab5199575d1dbf0c2fd2a50c5867b5a55a92806294853c821a5df` |
| `report_snapshot/part4_scientific_acceptance.qmd` | `c09d0d3afbb1766638c93951432ba09408f28135d5e2765d5579fb81079c3bd6` |
| `references/supporting_methods/meth_wmo_1029_low_flow_2008_en.txt` | `f6edeb7c41c7ef44f2f007ecc5c16c772ec0282530dd365d529721b0a228513f` |
| `references/supporting_methods/usgs_lowflow_frequency_2025_summary.txt` | `55eea73d9dea805d7b2119797e37f999f76bdf605c43cda8ad74fb94de9589db` |
| `references/supporting_methods/knoben_benchmarks_2019.xml` | `b92516c06688cf9a18b6e93a4984d42780429da398f13c38c6de03b4cda248d0` |

## Executed requirement crosswalk

Test names below are in `tests/test_annual_statistics.py` (annual) or
`tests/test_sampling_uncertainty.py` (sampling). Every listed result is asserted
against the real public operation. Exact means rational equality; all tolerances
are synthetic numerical test tolerances, never scientific acceptance criteria.

| Requirement | Public operation/input | Actual = expected; tolerance | Executed test |
|---|---|---|---|
| U1 rank | `empirical_estimate`, 40/30/20/10 | P50=25; P40=30; P99/P01 unavailable; exact | `test_weibull_interpolation_support_exact_neighbours` |
| U1 ties | `empirical_membership`, 40/20/20/10 | .2/.5/.5/.8, four observations; exact | `test_ties_remain_repeated_and_order_does_not_change_membership` |
| U1 fitted | `fit_zero_mixture` and `fitted_estimate`, 0/e⁻¹/1/e | pi0=.25, mu=0, variance=2/3, P.375=1, P.75=0; abs 1e-14 for float values | `test_zero_mixture_parameters_quantiles_and_atom_membership` |
| U1 failed fit | all zero/constant positive/one positive | no fit even on zero atom; empirical retained; exact state | `test_invalid_positive_fit_even_at_zero_atom` |
| U1 diagnostic | tied 1/2/2/2; CDF jump at 2 | both sides checked; left error exceeds right; exact float expressions | `test_distribution_diagnostic_evaluates_left_and_right_of_tied_jumps` |
| U1 annual mean | two actual calendar intervals at 2 and 4 | (2×31+4×335)/366, not 3; exact | `test_complete_volume_weighted_annual_means_and_leap_duration` |
| C5 duration | 8 m³/s in 365/366-day years | 252288000/252979200 m³; exact | same annual-mean test |
| C2/C5 identities | missing, partial, overlap, member mismatch, undeclared omitted year | refused or unsupported value=None; explicit exclusion retained | `test_missing_overlap_partial_and_identity_are_not_annual_observations` |
| C5 calendar | October year at UTC+05 | complete year works, wrong offset/partial year refused | `test_fixed_offset_accounting_year_and_unresolved_partial_year` |
| U10 trend | untreated genuine trend, computed P50=25 | number retained, use FAIL; unassessed trend UNKNOWN | `test_trend_and_rating_restrictions_bind_without_destroying_numbers` |
| U10 independent use | indicative annual finding; rating restriction; official pending | annual PASS, restricted use FAIL; no daily requirement | same trend/restriction test; `test_supported_annual_example` |
| U1/U10 import | stationary/nonstationary derivation, no raw calibration values | value/provenance retained; incomplete equation/covariates refused | `test_supported_import_and_missing_nonstationary_derivation`; `test_supported_import_without_raw_calibration_values` |
| U1 sampling failure | real fitted replicate with one distinct positive | one failed fit, interval=None; no survivor interval | `test_real_fitted_replicate_failure_prevents_external_sampling_interval` |
| U1 sampling endpoints | external 10/30/20 at alpha=.2 | [12,28], confidence .8; exact | `test_type7_flow_endpoints_and_attribution` |
| U1 sampling profile | chronology, L/B, generator/version, seed, uniform method, dependence | invalid schedules and missing declarations refused | `test_plan_rejects_broken_contract`; `test_l1_requires_independence_but_not_block_diagnostics` |
| U1 related series | different replicate indices/estimator/version/count | refused; all failure reasons retained | `test_related_quantities_use_identical_indices`; `test_external_estimator_and_complete_coverage`; `test_all_failures_retained_no_survivor_interval` |
| U1 covariance | c=(1,-2), Sigma=((4,1),(1,9)) | cᵀSigma c=36 (m³/s)²; exact, including unit conversion | `test_exact_covariance_with_signed_coefficients_and_unit_conversion` |
| U1 covariance failure | asymmetric, indefinite, nonfinite, wrong shape/unit | refused; singular PSD accepted | covariance parameterized tests |
| C2/C3 scope | altered climate/location/value/population | no acceptance transfer; native value/route recomputed | `test_scientific_scope_binds_complete_reference_and_product_identity`; `test_native_estimate_carrier_recomputes_value_and_route` |
| U10 import bypass | direct dataclass replacement as nonstationary without derivation | refused at public constructor | `test_direct_estimate_record_cannot_bypass_nonstationary_derivation_gate` |
| U1 numerical tails | 99 ties and one distinct source year | positive tail or distance from 1 = 1.2625088312e-23; rel 1e-11/1e-12 | two `test_fitted_membership_preserves_*` tests |
| U1 numerical tails | P=1e-23 fitted quantile | finite positive estimate, not unavailable from 1-P cancellation | `test_fitted_quantile_preserves_representable_small_exceedance` |

Known scientific failures survive missing checks through `CheckSummary` and
`permitted_use`. No record-length default, diagnostic tolerance or tail acceptance
threshold is introduced. External resampling/model studies remain caller-owned.
Native estimates are checked against their actual reference at construction;
imports retain their own derivation. Scope fingerprints include canonical full
reference/result identity, with reference-population ordering normalized.

## Reproduction environment

Base Fishy: `986acdc62a7984ff9b3629044e0b628f4ef508ff`. Dependencies are unchanged
and pinned by `uv.lock`. Python 3.13.8; Polars 1.44.2; pytest 9.0.2; Ruff 0.15.0;
ty 0.0.66. Optional integration uses Taqsim
`396ad093c2b6f240e702a3b05aee1fb96a69b3f7` and Incidence
`665da4e0d81ab28921b8d5d2edbb9be27f4ec612`.

```sh
uv sync --locked
uv run --locked pytest tests/test_annual_statistics.py tests/test_sampling_uncertainty.py
uv run --locked python examples/annual_estimation.py
uv sync --locked --extra taqsim
uv run --locked --extra taqsim pytest
uv run --locked --extra taqsim ruff format --check
uv run --locked --extra taqsim ruff check
uv run --locked --extra taqsim ty check src tests examples
```

The focused suite has 76 passing cases. Without the optional extra, a whole-tree
type check cannot resolve existing Taqsim examples/adapters; the annual modules
remain independently runnable. No source files from the private bundle are needed
to execute these tests.
