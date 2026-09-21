# Scientific use of hydrological products

Use `fishy.scientific_acceptance` to evaluate one supplied study against its frozen acceptance record. Use `fishy.pattern_diagnostics` to calculate diagnostics for individual validation cases. The caller prepares validation studies. Fishy does not run holdout selection, resampling, calibration or a multi-day safeguard.

## Assess a supplied study

```python
from examples.scientific_use import annual_screening_study
from fishy.scientific_acceptance import assess_scientific_use

record, evidence = annual_screening_study()
assessment = assess_scientific_use(record, evidence)
print(assessment.findings.scientific_adequacy.value)
print(assessment.comparisons[0].actual)
```

This synthetic example prints `accepted as indicative` and an annual error of `3.0 m3/s`. Its maximum allowed error is also `3.0 m3/s`. Equality passes because the supplied comparison is `AT_MOST`. The rating-range restriction still prohibits obligation sizing. Official admissibility remains pending. Missing validation produces `not accepted` without deleting the computed annual estimate.

Run the complete example with:

```console
uv run python examples/scientific_use.py
```

For an application, replace the synthetic inputs with these records:

1. **HydrologicalProduct:** exact location, scope, provenance, reference climate, accounting calendar, population, target probability or duration, resolution and units. Retain a versioned full-content identity for both the accepted reference and the result. Scalar annual and minimum products carry their actual `Flow`. An annual estimate's canonical scope identity can be used as its content identity. Do not use a broad method label as a content identity.
2. **AcceptanceRecord:** preparer and independent reviewer, frozen and review dates, mandatory/advisory criteria, applicability, uncertainty, omitted errors, permissions and restrictions. Each criterion declares formula, domain, units, case IDs, error measure, aggregation, limit, justification and equality. Freeze a separate record for a narrower indicative use. Missing criteria do not acquire default tolerances.
3. **ScientificEvidence:** the exact `frozen_record`, product and profile, supplied numerical/disclosure/official findings, sourced specialist evidence, per-case observations and validation metadata. Climate-year clusters, exposed/excluded evidence, shared inputs and donor groups remain explicit. Identical evidence cannot certify a changed acceptance record merely because its version string was reused.

`minimum_evidence(product, derivation)` lists the non-waivable scientific requirements. It does not supply acceptance thresholds. Evidence items are attributable specialist findings, not Fishy's certification of unseen data. Fishy checks their completeness, declared identity and recorded comparisons. Daily shape additionally requires mandatory numerical limits for seasonal shares, timing, duration minima and spells. An advisory criterion linked to a non-waivable requirement still binds.

`ScientificAssessment` retains the record, evidence, comparisons, checks and existing `EvidenceFindings`. `acceptance_for(expected_product)` compares full identity and recomputes the supplied gates. It does not trust a replaced output status. Do not authorize a different result by reading only its `findings` label. Match the expected product independently.

## Interpret results separately

- Annual magnitude, daily pattern, duration minimum, rare-tail applicability and explicitly named coarse products have separate findings.
- Accepted scientific use does not grant official permission.
- Short records can support an explicit indicative use. Record length alone does not impose rejection.
- Outside-rating values cannot size an obligation. An indicative label does not waive that restriction.
- Untreated trend cannot support the declared present-climate estimate.
- Daily disaggregation needs withheld co-located daily low-tail/spell evidence and propagated uncertainty. This also applies when duration minima are reported as an annual population.
- Dekadal products retain their actual intervals and name. They cannot be relabelled Q347 or daily Q95. Supported annual/coarse results remain independent of missing daily evidence.
- A required failed check survives other missing checks. For partially observed maximum-error aggregates, a known violation remains a failure with incomplete coverage. A partial arithmetic mean remains unknown unless another independent required check fails.
- A mean shape improvement, volume closure or downstream safeguard cannot override a failed daily acceptance criterion.

Revisions retain the previous profile, reason and previous result. Their validation identifies previously exposed clusters and reserves new or nested held-out evidence. Withheld climate clusters cannot also occur in training, excluded or previously exposed sets. Daily calendar benchmarks must exclude the same held-out climate clusters and use the same validation cases.

## Calculate diagnostic cases

The diagnostic API consumes `FlowSample` records with complete whole UTC days. Fixed-offset and subdaily diagnostic inputs are unsupported rather than shifted implicitly. Calendar construction has its separate fixed-offset support.

| Operation | Result |
| --- | --- |
| `seasonal_share(samples, year, season)` | Seasonal volume / annual volume, in percent. Compare values to obtain percentage-point errors. |
| `half_volume_timing(samples, year, season)` | First half-volume crossing in elapsed fractional days from year start. Season must not wrap. A plateau uses its first attaining boundary. |
| `duration_minimum(samples, domain, DiagnosticDuration(d), convention)` | Minimum complete d-day mean and earliest attaining window. Annual assignment uses the last daily interval and needs d−1 real predecessor days. Seasonal windows lie wholly within the season. |
| `longest_below_threshold(samples, domain, Flow(q))` | Longest run strictly below q inside the domain. Equality breaks a run; year edges never join. |
| `diagnostic_difference(candidate, reference)` | Signed and absolute errors, plus signed relative error. Zero reference denominators give undefined relative error, not an invented denominator. |

Zero annual/seasonal volume gives undefined share/timing where appropriate. Missing, partial, coarse, overlapping, mixed-identity and excluded-warmup daily inputs are rejected. Daily interpolation for timing is a convention, not an observation of within-day flow.

## Development limitation

All 21 dry held-out cases in the retained two-US-record, 50-year-training comparison overestimated the seven-day minimum. Mean shape error improved against the calendar benchmark in four station–period groups; longer training improved three, not all four. These correlated development cases are not naturalised Uzbek evidence or untouched independent rare-tail validation. They provide no correction factor or universal tolerance. `DESIGN_PATTERN_DEVELOPMENT_LIMITATION` exposes this limitation for the selected conditional-analogue construction's provenance.

See [implementation acceptance and source attribution](scientific_use_acceptance.md) for executed witnesses and the retained source-hash discrepancy.
