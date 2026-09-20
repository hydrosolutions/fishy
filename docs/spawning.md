# Spawning corrections

`fishy.spawning.spawning_schedule` constructs explicitly timed coefficients for
Order 179-НҚ (2025), paragraphs 25–27. It does not calculate hydraulics or resolve
conflicting source bounds. Pass its `TimedCoefficient` records to the selected
bounds/correction operator. Missing records are not neutral coefficients.

Choose percentage wording (`c <= 75`) or dry-year wording (`c >= 75`). Both include
75. An absent choice leaves correction eligibility unresolved. Parse the four
classes with `fishy.design_conditions.DesignClass`.

Supply a named species, biological water-temperature onset and threshold, three
positive stage durations, and exact scoped timing evidence. The annual onset
shift is limited to ±15 whole days. It moves the complete season without
shortening any stage. Appendix 4 dates are retained as source metadata, never
used to infer biological onset.

The biological evidence also needs an explicit **single-cycle applicability**
interval and matching `applicability_findings`. The interval must contain the
complete shifted season and every requested coefficient interval. It is at most
366 elapsed days, the longest Gregorian annual cycle. It can cross 31 December;
no calendar-year equality test is used. It is not a recurring seasonal template.
A multi-year run supplies separate annual biological cycles rather than extending
one dated season across later years. A neutral `K=1` outside the season is supported
only within that explicitly evidenced applicability, never from non-overlap alone.

### Supplying applicability to an existing timing record

Calls without the new fields return unsupported coefficients. No compatibility
rule invents temporal support. Supply the receiving cycle and evidence explicitly:

```python
applicability = Interval(cycle_start, cycle_end)
applicability_scope = EvidenceScope(
    "spawning_timing_applicability",
    location.reach.identifier,
    provenance.reference_member,
    applicability,
    "spawning_correction",
)
# Caller supplies actual findings for this exact scope and provenance.
timing = replace(
    timing,
    applicability=applicability,
    applicability_findings=accepted_applicability_findings,
)
```

The findings must match `applicability_scope`; simply changing their period is not
scientific acceptance of another cycle. The complete executable construction is
in `examples/spawning.py`. For a December–January season, explicitly supply a
single-cycle interval covering the whole shifted season and requested months.

* Daily-stage requests need complete daily observations (`ProductionMethod.OBSERVED`) at the same location,
  scenario and reference. Each day must fit one biological stage.
* Monthly requests use the printed seasonal coefficient for each complete
  calendar month that intersects the biological season. They establish no daily
  conditions. Outside the season the function emits explicit `K=1` records for
  requested intervals only. No omitted intervals are filled.

Select `CoefficientInterpretation.LISTED_VALUE` and a published `basin_row`, or
select `WEIGHTED_STUDY` and supply `WeightedStudy`. A weighted study identifies
three stage values, nonnegative weights with positive total, the covered period,
and separate evidence. Its average is not relabelled a printed Appendix 4 value.
Daily stages cannot be replaced by a study average.

`APPENDIX3` retains all recommended ranges. `APPENDIX4` retains all eight rows,
including basin names, waters, species, phases, approximate dates, published
coefficients and averages. Values are exact fractions. The Aral–Syrdarya
migration value remains 1.20 despite the generic 1.10–1.15 recommendation. Printed
averages are neither recomputed nor clamped. Row 2's repeated syllable in the
printed reservoir name is retained. Source PDF pages 12–13 were visually checked.
The two starred headings have no explanatory bodies in the held source.
`StarRelevance.AFFECTS_ELIGIBILITY` therefore leaves the result unresolved;
`NOT_RELIED_UPON` is an explicit scenario choice, not an invented footnote.

## Evidence and results

Use `coefficient_scope(location, interval, provenance)` for each output interval.
Timing evidence uses product `spawning_timing`; study evidence uses product
`spawning_weighted_average`. Both carry a typed `Location` that must match every physical identity and revision.
Both scopes use the full biological period, reach identifier,
reference member and intended use `spawning_correction`. Evidence must have exactly the supplied provenance, including source, scenario,
reference, data, configuration and software versions. Unsupported, restricted, missing or warm-up evidence
cannot support applying a correction. Scientific permission uses Fishy's existing
`permitted_use`; official admissibility remains independent and is not promoted.

Outputs preserve coefficient evidence, supporting study evidence, source, selected
interpretations, species, onset, duration, shift and study weights. Unsupported
outputs retain `value=None`, `Presence.UNSUPPORTED` and reasons. Published raw
values and `WeightedStudy.average` remain inspectable independently. No result
certifies complete national compliance.

See `examples/spawning.py` for a synthetic supported monthly calculation.

## Source-to-test crosswalk

| Clause | Public operation | Test |
|---|---|---|
| 27(1) | `spawning_eligibility` | `test_eligibility_both_readings_equality` |
| 25–26, Appendix 3–4 | `APPENDIX3`, `APPENDIX4`, listed schedule | `test_all_published_values_not_reaveraged_or_clamped` |
| 27(2),(5) | `BiologicalTiming` | `test_shift_preserves_duration_and_requires_annual_evidence` |
| 27(3) | daily-stage schedule | `test_daily_stages_and_explicit_neutral_outside_season` |
| 27(4) | monthly/study average | `test_study_average_separate_weights_and_period` |
| Missing source meaning/support | scoped schedule evidence | `test_missing_and_unresolved`, `test_scoped_support_not_generic_check_passthrough` |

All numerical tests use exact fractions. Inputs are synthetic, not calibrated
basin studies. Tests using `OBSERVED` emulate the observation route; that label
does not claim field authenticity for their generated fixtures. Floodplain hydraulic corrections (paragraph 28) are a separate
supplied-relation operation and cannot be inferred from these coefficients.

### Daily observation trace

`TimedCoefficient.supporting_observations` retains the immutable `FlowSample` records used to
assess each active daily stage. Source, data version, coverage, presence and
warm-up exclusions remain inspectable. Equal coefficient values produced from
different observation versions remain distinct results. Failed or duplicate
matching observations remain attached for diagnostics. Monthly and neutral
outside-season coefficients have no daily observation dependencies.

`required_support` preserves the exact timing and weighted-study evidence scopes
required by construction. Consumers can detect missing required studies even if
supporting findings are later removed. The expected timing scope remains the
full biological period, including for neutral coefficients outside that period.
