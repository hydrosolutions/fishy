# Quality acceptance crosswalk

## Scope and reproducibility

This return distinguishes source arithmetic, executed software behavior, scientific
adequacy and official authority. Every original case has a reviewed supported
expectation and a current public behavioral test. No original case is unresolved or
excluded from software acceptance. Existing source-policy ambiguities remain
explicit configured or unresolved outcomes, not adopted interpretations.

Run from the repository root:

```sh
uv sync --locked --extra taqsim
uv run --all-extras pytest
uv run --all-extras ruff format --check
uv run --all-extras ruff check
uv run --all-extras ty check
uv run python examples/imported_quality.py
uv run --extra taqsim python examples/taqsim_quality.py --save mixed.taqsim
```

The physical example refuses to overwrite an existing destination. A saved physical
document is not a restart checkpoint. The imported example is also executed with
imports of Taqsim and Incidence deliberately refused.

### Executed validation

Validated on 2026-09-20 with the locked optional simulator environment:

| Command | Actual result |
|---|---|
| `uv run --all-extras pytest -q` | **504 passed in 23.88s** |
| `uv run --all-extras ruff check` | All checks passed |
| `uv run --all-extras ruff format --check` | 51 files already formatted |
| `uv run --all-extras ty check` | All checks passed |
| `uv build` | Wheel and source distribution built; wheel includes all intended catalogue files |

The original seed CSV retains its CRLF bytes and original SHA-256. Diff whitespace
validation uses `git -c core.whitespace=cr-at-eol diff --check` rather than modifying
source bytes. The local uv-cache build warning was checked: neither the wheel nor
source distribution includes `.uv-cache` or local validation records.

Activation bugs found during implementation received failing real-path tests
before repair: unrelated empty accounts could certify a loaded wet boundary, and
an account mapping could ignore a changed prepared location version. The same tests
now refuse both paths. Independent review then found stale account residual caches and
ignored warm-up exclusions. Real-path red tests preceded those repairs. Construction
now verifies account caches against their source ledger. Exclusions now restrict
individual/group/relative observations, mixing, drain control and account activation.
A full observation-kind/production-method matrix prevents synthetic observations
from claiming observed provenance. Regression receipts are retained locally with the delivery
validation record; no physical numbers or policy thresholds were changed.

### Exact compatible source revisions

| Component | Revision and evidence |
|---|---|
| Fishy foundation | `53cf80f3e46257bc0b9be883bc772b6b941dc2b3`; 264 foundation tests passed before implementation |
| Fishy quality | This PR's exact reviewed head identifies the implementation and this crosswalk; validation receipts are in the PR |
| Taqsim dependency | `396ad093c2b6f240e702a3b05aee1fb96a69b3f7` in `pyproject.toml` and `uv.lock` |
| Taqsim current main inspected | `306de27c68438ce160363fe58328399f0b0cdbf3`; `src`, `tests`, `pyproject.toml`, `uv.lock` are unchanged from the pinned revision; intervening commits publish visions only |
| Incidence dependency | `665da4e0d81ab28921b8d5d2edbb9be27f4ec612`, Python binding subdirectory |

### Numerical precision

Production quality, load and flow calculations use exact `Fraction` values. Decimal
inputs are parsed from their displayed decimal form. Strict policy boundaries are
never relaxed. Most tests use exact equality, with **zero numerical tolerance**.
Three repeating source-decimal expectations also receive an absolute `1e-14`
comparison after their exact rational answer is asserted: capacity concentration
`17/30`, lower bound `20/7`, and strict-case concentration `22/45`. This tolerance
only checks rounded source presentation; it does not change a feasible endpoint.
Taqsim's declared litre water quantum and constituent quantum remain physical
accounting metadata, not an uncertainty distribution.

## All 26 original cases

Inputs remain in `tests/data/quality_fixtures.json`, copied byte-for-byte from the
accepted bundle's `report_snapshot/quality_support/quality_fixtures.json`.
Fixture SHA-256: `a65d18cf5074c15ae6366af2faf50c91dfb5af1b62deb578fb663d0d141513fe`.
`tests/test_quality_acceptance.py::test_supplied_quality_case[ID]` executes each row
below using that original ID and input. Values in the final column are both the
reviewed expected outputs and the actual asserted outputs. All 26 tests passed.
Rates are m³/s, loads kg/s and concentrations kg/m³ unless noted.

| Original ID | Current public operation | Expected = actual observable |
|---|---|---|
| `ordinary_dilution` | `solve_mixing` | q=15/2; total=35/2; C=1/2 |
| `ecological_total_no_double_count` | `solve_mixing + FlowConstraints` | q=10; total=20; C=9/20 |
| `already_compliant` | `solve_mixing` | q=0; total=10; C=2/5 |
| `background_not_new_legal_floor` | `solve_mixing` | q=0; total=10; no issued floor/obligation |
| `source_equals_limit` | `solve_mixing` | empty; source-water-infeasible; 0q≤−3 |
| `capacity_limited` | `solve_mixing / capacity_check` | quality q≥15/2; capacity 5 empty; C(5)=17/30 |
| `dirty_source_upper_bound` | `solve_mixing` | quality [0,8] |
| `ecological_quality_conflict` | `solve_mixing / recheck_mixing` | quality [0,8]; ecology q≥10; known conflict; q=10 fails |
| `dry_channel_open_interval` | `solve_mixing / recheck_mixing` | (0,∞); infimum 0 unattained; zero concentration undefined |
| `grouped_upper` | `solve_mixing` | qmin=4; original group sum=1 |
| `lower_and_upper` | `solve_mixing` | [20/7,8] |
| `tds_standalone` | `solve_mixing / GroupTarget` | qmin=2; TDS separate; attempted ionic-group inclusion refused |
| `missing_group_member` | `assess_quality` | UNKNOWN / INCOMPLETE |
| `censored_upper` | `assess_quality` | [0,600] mg/l vs 500: UNKNOWN |
| `unit_conversion` | `QualityValue / Flow / LoadRate` | 500 mg/l=1/2 kg/m³; 10 m³/s gives 5 kg/s |
| `single_load_control` | `screen_single_load` | allowance=2 kg/s; reduction=2 kg/s |
| `conservation` | `recheck_mixing / assess_load_accounts` | in=out=35/4 kg/s; local/basin residual=0 |
| `inactive_quality` | `apply_quality_component` | base 10 retained; quality total20 advisory |
| `invalid_group_limit` | `GroupMember` | zero denominator refused |
| `negative_load` | `LoadRate` | −1 kg/s refused |
| `strict_upper_open_minimum` | `solve_mixing / recheck_mixing` | (15/2,∞); 15/2 fails; C(8)=22/45 passes; capacity15/2 fails |
| `strict_equality_zero_coefficient` | `solve_mixing` | 0q<0; empty source-water-infeasible |
| `group_equality_interpretations` | `assess_quality` | sum1: inclusive PASS; strict FAIL; unresolved UNKNOWN |
| `nitrite_reporting_basis_unresolved` | `assess_quality` | equal units do not resolve NO2 vs N: UNKNOWN |
| `source_range_not_automatically_interval` | `UnresolvedTarget / assess_quality` | raw 0,3–3,0 retained: UNKNOWN |
| `missing_group_member_preserves_individual_failure` | `assess_quality` | individual FAIL; group UNKNOWN; FAIL / INCOMPLETE |

The inactive fixture supplies component totals rather than a physical boundary.
Its adapter explicitly declares synthetic `Qb=10`, `B=10`, `Cs=0`, `T=0.5`, giving
quality total20. The behavior-only individual-failure fixture supplies no magnitude;
its adapter declares synthetic `120>100`. These completions are identified in test
comments. They do not change the governing expected behavior or infer source policy.
Historical JSON names and Boolean shorthand stay in fixture traceability only;
production uses current domain records and explicit state enums.

## Required supplements beyond the fixture file

Test paths below are executable witnesses. All supplied scientific support,
profile applicability and hypothetical approvals in these tests are illustrations.

| Requirement / source | Public input → observable result | Executed witness |
|---|---|---|
| Upper/lower/range and strict endpoints; quality parameters | Whole bounds tested; both range sides retained; equality follows configured operator | `test_quality.py::test_whole_interval_and_strict_endpoints`, `test_individual_range_retains_both_bounds`, `test_groups_intervals_lower_and_range` |
| Relative reference; ACCEPTANCE §5 | Supplied temperature minus scoped historical reference; 23−20=3 inclusive passes, strict fails; wrong reference interval unknown | `test_quality.py::test_relative_temperature_uses_explicit_supported_reference_and_uncertainty`, `test_relative_reference_rejects_unrelated_interval` |
| Override/version/C2 | 8 passes10, fails scenario5; original profile/result unchanged; mismatched scenario unknown | `test_quality.py::test_profile_override_version_isolation`, `test_quality_scenarios.py::test_scoped_scenarios_do_not_rewrite_imports_or_previous_results` |
| Required membership/C3 | Empty set refused; omitted required tests unknown; failure persists with incomplete coverage | `test_quality.py::test_required_failure_survives_missing_member_and_omitted_target`, `test_units_nonfinite_negatives_and_immutable_collections` |
| Censoring and uncertainty | Non-detect interval not zero; unknown reporting limit missing; group interval bounds preserved | `test_quality.py::test_non_detect_interval_not_zero_and_unknown_reporting_limit`, `test_groups_intervals_lower_and_range` |
| Observation admission | Publisher/URL/dates/location/depth/form/unit/sampling/method/limit/flags/licence/transformations retained; omissions explicit | `test_quality.py::test_observation_admission_preserves_missing_fields_and_original_identity` |
| Chemical and sampling support | NO2/N and averaging mismatches unknown; only explicit supported conversion applied with provenance | `test_quality.py::test_chemical_basis_and_sampling_identity_are_not_inferred`, `test_supplied_supported_conversion_is_explicit_scoped_and_attributable` |
| Fixed-boundary complete interval | Every sign and zero coefficient; strict singleton empty; inclusive singleton attained; operational limits retained | `test_mixing.py::test_all_coefficient_signs_and_strictness`, `test_inclusive_singleton_and_strict_upper_at_same_bounds` |
| Carrier/background accounting | All carrier water/loads and separate loads enter once; q excluded; changed Qb5 with B8 requires q=55/4 | `test_mixing.py::test_carrier_water_load_and_separate_load_counted_once`, `test_changed_background_recalculation_and_conservation` |
| Final uplift rechecks | Dirty-source quality [0,8]; uplift q10 fails original C=11/20>1/2; no maximum hides it | `test_mixing.py::test_dirty_source_upper_bound_and_original_uplift_recheck`, `test_quality_activation.py::test_dirty_source_ecological_uplift_cannot_bypass_original_upper_test` |
| Fixed single-load control | Allowance2/reduction2; background6 vs capacity5 fails without negative permission | `test_source_control.py` single-load cases |
| Common drain factor | Fixed-water factor interval [1/4,1/2]; independent group tightens upper to3/8; original factor rechecks | `test_source_control.py` drain-factor individual/range/group cases |
| Local/basin closure | Internal transfers cancel; storage, external flux, separate loads and explicit process retained; local errors cannot cancel into validity | `test_load_accounts.py::test_local_and_basin_internal_cancellation_and_source_tags`, `test_storage_separate_load_and_export_enter_once`, `test_local_failure_does_not_cancel_into_basin_pass_or_precision_warning` |
| Matched account boundary | Account mapping classifies every incoming carrier once; exact Qb/B/Cs and full location/snapshot match; empty or unrelated accounts refused | `test_quality_activation.py` background-account and provenance regression cases |
| Source tags and residuals | Untagged mass remains unallocated; supplied uncertainty retained separately from precision and exact residual; no legal attribution | `test_load_accounts.py::test_unallocated_mass_is_not_a_conservation_residual`, `test_source_tags_do_not_silently_overallocate_or_change_interval` |
| Source control precedes residual dilution | Outstanding/unknown controls or controllable/point-source residuals refuse actual activation path before solving | `test_quality_activation.py::test_source_controls_gate_actual_sizing_before_any_calculation`, `test_load_accounts.py::test_prior_controls_and_diffuse_only` |
| Five activation conditions | Remove each condition: base retained/advisory. All-five feasible can bind; hypothetical mode remains labelled | `test_quality_activation.py::test_each_of_five_conditions_is_necessary`, `test_feasible_report_retains_base_quality_and_combined`, `test_hypothetical_activation_and_floor_only` |
| Activation feasibility and floor-only | Capacity/source/known conflict/missing support never binds; floor-only has no requirement/obligation/verdict; dry/open needs real candidate | `test_quality_activation.py::test_all_five_cannot_activate_impossible_or_incomplete_screens`, `test_open_endpoint_requires_actual_candidate_not_epsilon`, `test_dry_quality_without_standalone_minimum_can_bind_positive_base` |
| Process support | Supported signed pH/temperature/oxygen/nutrients assessed; unsupported outputs unknown; no conservative corrective prediction | `test_quality.py::test_supplied_supported_and_unsupported_process_states`, `test_mixing.py::test_unsupported_process_has_no_conservative_prediction` |
| Organoleptic sensitivity/C6 | Caller compares common ratios0.6+0.6: FAIL1.2; qualifier groups eachPASS0.6; interpretations separate | `test_quality_scenarios.py::test_external_organoleptic_qualifier_sensitivity` |
| DP-QUAL-1 working reading | Category0.5 sizes q7.5; C0.5 passes category and fails separate general0.4; no stricter substitution | `test_quality_scenarios.py::test_assigned_category_sizes_flow_while_stricter_general_constraint_stays_failed` |
| Catalogue | 456 records, eight separate disabled seeds; 409 scalars/15 uninterpreted pairs/23 text/9 missing; original raw semantics retained | `test_catalogue.py`; [publication provenance](catalogue.md) |

## A13: current physical-to-quality integration

`tests/test_physical_quality.py::test_a13_realised_mixing_live_saved_quality_failure`
runs an actual Taqsim `WaterSystem`, not a mocked projection or supplied arithmetic:

- Two sources provide 10 m³ at0.8 and 5 m³ at0.2 kg/m³ to one mixing reach.
- Realised outlet amounts are15 m³ and9 kg. Exact concentration is3/5 kg/m³,
  or600 mg/l, and the configured500 mg/l upper test returnsFAIL.
- Live and `load_run` saved paths agree. The full physical document and digest do
  not change during Fishy assessment. Source digest remains in result provenance.
- One-hour, one-day and two-day intervals start on leap day. Mean flow is15 divided
  by actual seconds, not a guessed daily rate. Incoming/outgoing views are explicit.
- Water and salt local/basin accounts close exactly. Deliberately missing chloride
  accounts remain unknown, not falsely claimed closed.

Additional executed integration tests in the same file cover known saltFAIL plus
missing chloride with INCOMPLETE coverage, unsupported model support, a failed
specialist account with independently supported sulphate preserved, delayed aggregate concentration from summed mass/water rather
than mean concentration, dry/absent/outside-horizon chemistry, and transferred0.5
versus final-storage1.0 kg/m³ after evaporation. `test_quality_examples.py` executes
both documented examples, including live/saved output and no-simulator imports.

Actual example output:

```text
Imported concentration: 600 mg/l; upper limit: 500 mg/l; finding: fail
Quality-only arrival minimum: 15/2 m3/s; conditional total: 35/2 m3/s
Combined arrival: 10 m3/s; total: 20 m3/s
Combined concentration: 450 mg/l; screen only, no activated requirement or permit
live: water=15 m3; mass=9 kg; concentration=600 mg/l
live: duration=3600 s; mean flow=1/240 m3/s; 500 mg/l upper: fail
saved: water=15 m3; mass=9 kg; concentration=600 mg/l
saved: duration=3600 s; mean flow=1/240 m3/s; 500 mg/l upper: fail
```

## Applicable C semantics and scope limits

C1: quality category never chooses physical origin/designation or track; existing
`test_spatial.py` regression tests remain. C2: profiles, scenarios and source
versions stay isolated. C3: no empty/missing set manufactures satisfaction. C4:
quality cannot rewrite an issued duty or create one on a floor-only route; full
10/6/5 issuance belongs to assembly, while existing duty regressions remain. C5:
units, signed states, time, presence, chemical basis and partial coverage remain
explicit. C6: callers compare supplied scenarios; Fishy executes one profile.
An annual aggregate cannot become daily evidence by changing its name.

These tests establish software behavior only. No basin observations, calibrated
mixing/transport, scientifically accepted targets or official approvals are
invented. SanPiN §22 equality and §§5/22 versus draft§35 applicability remain
separate. Cross-source harmfulness mapping and qualifier groups remain provisional.
DP-QUAL-1 official applicability, source range meanings and chemical identities
remain application choices or unresolved evidence. No national category ordering,
seed I/II mapping, permitting, receptor solver or complete Uzbek assembly is claimed.

## Source identities and publication safety

The accepted local bundle's identities were checked before use:

- IMPLEMENTATION_BRIEF: `0ad077a69f27af74dd6cf340830438576d020d66b9bf5a8d568bb84eb5c757c8`
- ACCEPTANCE: `851fc64c35e827fa3a072750f760108ddd5f445684ba65f85bb4037758b047ba`
- SHA256SUMS: `7dcf598b23a282a88a12af6ca2aee89795df27a119842ed17603403398dc97f0`

Only the intended inactive source-table data and synthetic quality fixture are
published. Sanitized table derivatives omit private paths, embedded original DOCX
and unrelated auxiliary OOXML, with explicit transformation/hash manifest. Raw
cells, formula runs, substantive notes and merged relationships remain. No full
report, restricted paper, full handover or original binary is redistributed.
See `src/fishy/data/publication_manifest.json` for original and derivative hashes.
