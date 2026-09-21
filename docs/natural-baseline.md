# Natural baseline families

`fishy.natural_baseline.baseline_family` computes the proposed Uzbek four-class
**pre-quality ecological candidate**. It does not issue a duty or validate a river.

## Supply accepted hydrology

Prepare `DailyPattern` products at annual exceedances .50, .75, .90, .97 and .99.
Use `construct_pattern` or `import_pattern` from `fishy.daily_patterns`.
Each product needs its own exact annual-magnitude and daily-shape scientific
assessment with `UsePurpose.SIZING`. Screening-only acceptance retains exploratory
diagnostics but cannot produce a sizing candidate. The products must share a present-climate natural reference, member,
location, intended use and complete receiving accounting calendar.

Supply `RecordedMinimum` with that same annual reference and **every accepted
complete daily reference year**, missing-data treatment and uncertainty meaning.
`recorded_minimum_product` exposes its exact scientific subject for review. Attach
the evaluated assessment to the record. This is one scalar: the lowest daily
value across the accepted record. All attaining dates remain available through
`record.days`. Zero stays zero. Explicit annual exclusions remain on the reference;
missing days cannot be silently omitted or filled.

```python
result = baseline_family(
    patterns,
    recorded_minimum,
    provenance=run_provenance,
    profile_version="my-explicit-study-v1",
)

if result.candidate is None:
    print(result.checks)
else:
    for regime in result.candidate.classes:
        print(regime.design, regime.samples)
```

Run `uv run python examples/natural_baseline.py` for a complete leap-year scenario
with exact accepted synthetic products and a separate missing-evidence result.
Its supplied scientific findings are hypothetical assumptions, not site validation.

## What is calculated

Classes 25/50/75/95 use magnitude **and shape** at .50/.75/.90/.97. The natural99
and natural50 operands use their own probabilities. Scaling already performed by
the pattern operator is not repeated. Each day first tests
`max(class_flow, natural99, recorded_minimum, applicable_winter) > natural50`.
Any strict crossing declines the entire family. No tolerance, clipping repair or
partial class family is supplied. Only a passing family reaches the class-only
median cap, which is inert under this strict rule.

`result.diagnostics` retains the class flow, each bound, lower value, date and
crossing finding. Known numerical crossings remain visible when separate
scientific evidence is missing. Missing numerical operands leave the candidate
unavailable rather than inventing values.

A supplied `ReachCoefficients` replaces annual magnitude with
`alpha[class] * natural_mean(.50)` and keeps the shifted shape. It does not
multiply the shifted annual magnitude. Supply exact scoped findings from
`coefficient_scope`. An unsupported alternative retains its diagnostics and uses
the standard route. No coefficient is required for that route.

`WinterProvision` needs an explicit adoption/scenario basis, reference, share and
exact scoped findings from `winter_scope`. It enters only November–December on a
regulated natural river. Unsupported reference evidence leaves it inactive.
`result.optional_evidence` explains these optional-component decisions. Changing
coefficient values, reference flow, calendar, member or derivation invalidates
previous findings.

`AdvisorySpawning` carries a complete coefficient calendar and supplied biological
and coefficient provenance, plus exact scoped findings from `spawning_scope`. Its correction is reported only for classes75/95.
It never enters `candidate.classes`, repairs a crossing or sizes an issued duty.
Missing spawning inputs leave the binding candidate unchanged.

## Actual-year selection and downstream gates

`select_actual_year` is separate. Supply a versioned `ActualYearConvention` with
four non-overlapping intervals covering [0,1], exact endpoint ownership, tie
basis, accounting year and accepted reference identity. Supply the exact accepted
natural-reference pattern too; a reference label alone cannot permit selection.
The caller supplies the exceedance on that reference. Missing convention or
accepted reference leaves selection pending. Forecast issue date and assumptions
remain separate from later completed-year classification. This function changes
no issued record.

`EcologicalMemberCandidate` is a complete numerical pre-quality schedule, not an
acceptance certificate. Its constructor checks all class/day/location/member
identities. Preserve `BaselineResult` alongside it. Local quality/receptors,
provisional and final duration safeguards, external structural selection, final
physical checks and floor/issuance follow separately. A later active uplift may
repair a duration failure; advisory spawning cannot. It cannot repair inconsistent
natural bounds or failed scientific shape acceptance.

## Source limits

These operators implement Appendix A step7 of the owner-selected proposed Uzbek
method, with separate hydrological acceptance. They are not adopted Uzbek policy
or a replacement for Kazakhstan's independent method. The documented 21/21 dry
held-out seven-day-minimum overestimation limitation remains on the input pattern
assessments. It supplies no correction factor or acceptance tolerance.
