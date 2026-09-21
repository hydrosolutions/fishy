# Sanitary duties and seasonal profiles

Use Fishy to compare a supplied sanitary duty with deliveries, or to calculate an
explicitly hypothetical seasonal profile. These are separate operations. Neither
requires ecological sizing or a running simulator.

```sh
uv sync --locked
uv run python examples/sanitary_assessment.py
```

The example uses synthetic inputs. It does not reconstruct an issued duty or
establish a national interpretation. See the [acceptance crosswalk](sanitary-acceptance.md)
for source identities, expected values and validation status.

## Assess an existing duty

Use `fishy.sanitary_duties.assess_sanitary_duty` with:

- A `SanitaryDuty` wrapping a `fishy.duties.SuppliedDuty` and `InstrumentEvidence`.
  Keep the instrument identifier, provision, version, applicability and dated
  search record. Authenticity and currency are separate fields.
- The instrument's schedule as `Obligation` records with unit-bearing `Flow`
  values, exact `Interval` timestamps, located `FlowSample` inputs and provenance.
- Matching `Delivery` records and explicit candidate/scenario identifiers.
- A `HydraulicScope` for every required non-discharge component. Supply attributable
  `ImportedHydraulicFinding` records where available; omit unsupported findings.

The result retains the supplied instrument, candidate, scenario and findings.
`flow_and_components.intervals` contains individual numerical comparisons.
`flow_and_components.known_shortfall_volume` is a subtotal, not proof of complete
coverage. Inspect `summary` as well as the number.

For duties `[2, 3]` and daily deliveries `[1.5, 3.5]` m³/s, positive shortfalls
are `[0.5, 0]` m³/s. Their volume is exactly **43,200 m³**. Each shortfall is
`max(duty - delivery, 0)` multiplied by actual elapsed seconds. Later surplus,
shortage or estimated availability cannot lower the original prescription.

When a schedule supplies comparison operands, locations and intervals must match
exactly. Fishy rejects cross-location comparisons and implicit resampling. Present zero differs from missing,
unsupported or outside-horizon evidence. Retain an instrument even if its
schedule is missing or it contains only non-flow clauses. Missing discharge
leaves the flow check pending without erasing supported hydraulic findings.
If delivery observations exist but the magnitude is missing,
`flow_and_components.uncompared_deliveries` retains them without inventing a
comparison or a zero duty. This optional field defaults to an empty tuple.
An empty required set does not establish satisfaction.

`DutyApplicability` keeps four search outcomes distinct: authenticated/applicable,
located/inapplicable, unresolved, and none located after a documented search.
The last outcome is not proof that no duty exists. A secondary copy can be assessed
as `HYPOTHETICAL`; it cannot silently become authenticated binding authority.
Unresolved authority does not erase supplied operands or their physical findings.

## Calculate the hypothetical seasonal profile

Use `fishy.sanitary_profile.annual_sanitary_profile(samples, attribution, windows)`
with `ProfileAttribution` and `SeasonalWindows` containing two `SeasonWindow`
records. It returns a `HypotheticalProfile` with `selected_rank`, `summer`,
`winter`, `presence` and member-level `completeness`. Its `value_on(day)` returns
no value outside the declared seasonal windows. This is a recurring month/day
candidate lookup, not a forecast or an issued schedule for the selected year.
The module implements the report's
annual-selection interpretation, not an authenticated SanPiN estimator. Its result does not replace
an issued duty or activate domestic ecological-entry sizing.

Supply one identified natural-flow reconstruction with its control point,
reference period, provenance and evidence. The empirical annual-selection path
requires complete January–December years of finite nonnegative daily mean flows
in m³/s. Each day is 86,400 seconds in UTC or a declared fixed offset. Keep leap
days. Missing or duplicate days and incomplete years are errors, not invitations
to fill, interpolate or discard data.

Declare separate summer and winter month/day windows. Each is nonempty,
contiguous, inclusive, valid in every input year and within one calendar year.
The windows cannot overlap. There are no inferred national season dates.

For each year, the calculation takes the arithmetic mean of daily flows. It ranks
years by descending annual mean, averaging the occupied ranks of ties. With `n`
years and rank `r`, the plotting position is exactly `r / (n + 1)`.

The fixed target `19/20` must lie inside the actual plotting-position range before
selection. An unsupported range is not rounded into support. Among supported
positions, selection minimizes the distance to the target. Equal distances favor
the larger probability; equal probabilities favor the earliest year. The result
retains tied candidates, actual selected probability and annual mean. It then
returns separate seasonal daily minima and their dates. It supplies no values
outside the two windows.

The synthetic witness uses 2001–2018 constant daily flows of `2021 - year`.
In 2019 the January 1 flow is `3/5`, July 1 is `9/10`, and the other 363 days
are `1457/726` m³/s. The annual mean is exactly `2`. For January–February and
July–August windows, the selected year is 2019 at `19/20`, with winter `3/5`
and summer `9/10` m³/s. Removing 2019 gives maximum support `18/19 < 19/20`.
These windows are synthetic inputs, not national defaults.

Nineteen distinct annual ranks first reach the target. Ties can reduce support.
This is a rank-support property, not a universal record-length rule or proof of
scientific adequacy. Preserve rating-range, reconstruction, dependence, climate
relevance and intended-use restrictions. No silent detrending is performed.

`nominated_sanitary_profile(samples, attribution, year, windows, interpretation)`
produces a separately identified nominated year's hypothetical seasonal minima
without claiming successful empirical selection. It requires the nominated
seasonal days, not a complete annual record.
`imported_sanitary_profile(attribution, method_description, windows, summer, winter)`
keeps imported `SeasonalMinimum` estimates with their own method, evidence and windows.

For example, after preparing `daily_samples` and the matching `ProfileAttribution`
record `attribution`, nominate a year without requesting empirical selection:

```python
from fishy.sanitary_profile import (
    SeasonalWindows,
    SeasonWindow,
    nominated_sanitary_profile,
)

windows = SeasonalWindows(
    summer=SeasonWindow((7, 1), (7, 3)),
    winter=SeasonWindow((1, 1), (1, 3)),
)
profile = nominated_sanitary_profile(
    daily_samples,
    attribution,
    year=2019,
    windows=windows,
    interpretation="independent hypothetical nomination, study-1",
)
print(profile.summer, profile.winter, profile.presence)
```

Here `daily_samples` must cover those six dated days in 2019 with complete daily
means. They may carry summer `[4, 2, 5]` and winter `[6, 3, 7]` m³/s to obtain
separate minima `2` and `3`. The short windows are illustrative, not prescribed
national seasons.
 Neither path imposes the empirical record gate
on an independently supplied duty. Missing interpretation or windows leaves that
derivation pending, not the duty assessment.

Run alternative reconstructions separately and retain each member's identity,
selection and failures. A caller-reported min/max range is sensitivity, not an
inferred confidence interval. Failed members mean incomplete coverage.

## Assess hydraulic components

The source clauses refer to different conditions:

| Source clause | Component to retain | What discharge alone cannot establish |
|---|---|---|
| SanPiN 3907-85 §4.2 | Minimum flow associated with seasonal minimum mean-daily flow in a 95%-assurance year under the source regime wording | Authority for the report's particular annual-selection interpretation |
| §4.3 | In cascades, §4.2 plus pre-impoundment minimum velocity and continued downstream hydropower current | Local velocity or current continuity |
| §4.4 | Maximal possible release uniformity and no abrupt within-day downstream level/velocity changes | A numerical ramp limit or within-day behavior from daily means |

The **0.5 m/hour** provision in §3.7.3 concerns beach siting. It is not a sanitary
ramp default. Order 179-specific hydraulic rules are not sanitary defaults either.

`fishy.sanitary_hydraulics.assess_imported_hydraulics` consumes a specialist finding
with a study and criterion source, component, candidate/scenario, exact period,
location/domain, variable, reference, units and evidence. A generic pass flag is
not enough. Keep stage datum, depth bed reference, directional velocity and speed
magnitude distinct. The boundary requires exact scope; it does not extrapolate,
infer missing states or solve hydraulics. Supplied study evidence must retain any
relation's geometry/version, boundary conditions, supported domain, interpolation,
uncertainty and intended-use limitations. Use optional `HydraulicRelationEvidence`
metadata on relation-derived imports or transitions. `RelationDomain.UNSUPPORTED`
leaves the check unknown rather than extrapolating.

For a supplied discrete rate, use `assess_sanitary_rate(RateCriterion,
HydraulicTransition)`. State and rate bounds use exact `Fraction` values. Declare
separate nonnegative rise/fall magnitudes, strict or inclusive comparisons, and
whether an absent bound is intentional or required-but-missing. If both bounds
are intentionally absent, the check remains unknown rather than manufacturing
satisfaction without a criterion. Rate units are
the declared variable units per hour. The actual transition interval supplies the
elapsed time.

For stage `1.00 → 1.12 m` over half an hour, the rate is `6/25 = 0.24 m/hour`.
It fails a hypothetical inclusive rise limit `1/5 = 0.20`. The reverse rate is
`-6/25` and passes a separate fall limit `3/10 = 0.30`. These limits are supplied
synthetic criteria, not source-law thresholds.

A `RateAssessment` retains each required direction in `directional_checks` and
reports coverage through `completeness`. A supported failure against one supplied
bound remains `FAIL` when the opposite bound is missing, with `INCOMPLETE`
coverage. With no known failure, a missing bound remains unknown. Supported
change bounds, elapsed time and rate bounds remain available in both cases.
Inspect these fields together: the aggregate `check` and `rate_check` projection
alone cannot encode incomplete directional coverage.

For state bounds `[l0, u0]` and `[l1, u1]`, conservative rate bounds are
`[(l1-u0)/dt, (u1-l0)/dt]`. Supported tighter joint evidence may narrow them.
Containment passes; disjointness fails; overlap is indeterminate, with strict
endpoints preserved. These bounds are not confidence intervals.

Missing predecessors, expected-sample gaps and unresolved season-boundary
criteria stay unassessed. No gap bridging or invented intermediate states occurs.
Endpoint differences concern discrete transitions, not unseen instantaneous peaks.
Differences of interval means concern those means. Daily means cannot certify
within-day conditions. Use a separately supported specialist finding for such
conditions. Unsupported qualitative conditions remain unassessed.

## Keep requirements and conclusions separate

`CombinedAssessment` retains sanitary assessments and optional
`EcologicalRequirementAssessment` records side by side. Add identified
`RequirementConflict` records where conflicts are known. Keep control points,
issued versions and source methods. The container does not choose legal precedence,
take a universal maximum, sum downstream non-consumptive duties, or create simulator
demands. Changing a hypothetical profile does not rewrite another requirement.

A supported failure survives unknown components as failure with incomplete
coverage. With no known failure, a missing required component prevents complete
pass. A flow pass is not a whole-duty pass when hydraulics remain unknown.

Keep three questions separate:

1. **Numerical support:** Are the operands supported on the assessed domain, and
   what does the calculation show?
2. **Scientific adequacy:** Is the evidence accepted for this particular use,
   including its reconstruction and uncertainty limitations?
3. **Authority and admissibility:** Is the instrument authentic, current and
   applicable, and is the evidence officially admissible?

Observed comparisons differ from modelled predictions. Neither determines legal
compliance, liability or attribution. Synthetic test success certifies software
behavior only on the tested domain.

## Source authority limits

The approved handover remains named `fishy_taqsim_handover_candidate_2026-09-19`.
Its candidate label does not authorize use of older handovers as extra requirements.
The held 3907-85 text is a secondary reproduction, not an authenticated governing
original. Its present force and object-specific applicability in Uzbekistan remain
unresolved. The government-hosted SanPiN 0315-14 copy is marked unofficial
translation. Its register entry and reference to 3907-85 do not authenticate the
inherited sizing rule. Water Code Article 122 provides a framework, not a numerical
estimator. The repository includes no private originals or copied report chapters.
