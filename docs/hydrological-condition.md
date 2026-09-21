# Hydrological condition (HYDMOD-F)

Fishy computes the nine hydrological indicators in the 2011 BAFU HYDMOD-F
manual. It inventories interventions, screens their significance, calculates
point indicators, transfers them to reaches, and derives the overall hydrology
class. It needs no simulator or HYDMOD-FIT installation.

This is hydrological screening. A class does not prescribe a release, establish
biological condition, or certify legal compliance. The independent
[Swiss prescribed-flow workflow](swiss-workflow.md) is unchanged.

## Run a complete and partial assessment

```sh
uv sync --locked
uv run python examples/hydrological_condition.py
```

The synthetic example computes, rather than supplies, all nine classes:

```text
Point classes: [2, 1, 1, 3, 1, 2, 2, 2, 2]
Point overall: 3 points: 17
Downstream overall: 2 coverage: complete
Missing stage rate: None coverage: incomplete
```

It uses an explicit Swiss reference type, an intervention inventory, monthly
reference estimates, an instantaneous event catalogue, daily low-flow spells,
operating pulse estimates and prepared catchment relations. The affected
catchment is 50 km². Another 50 km² is surveyed as unaffected intermediate area.
Each indicator is weighted separately before the overall class is calculated.

The partial path removes the hydropeaking stage-rise evidence. Mean-flow,
low-flow and other supported results stay available. The missing pulse class
prevents a complete overall assessment; daily discharge does not fill the gap.
All example inputs are synthetic, not site evidence or national defaults.

## Choose an operation

| Public module | Responsibility |
|---|---|
| `fishy.flow_interventions` | Reference applicability; Table 8 magnitude/significance and cumulative groups; Table 9 indicative selection; concession and actual-operation daily estimates. |
| `fishy.flow_regime` | Monthly/annual/raster/Pardé reference estimates; pooled Q347 and annual CV; mean-flow, low-flow magnitude/duration and circular seasonality. |
| `fishy.flow_events` | Independent instantaneous flood events, daily-maximum reference MHQ, additional stormwater events and supplied rainfall-frequency estimates. |
| `fishy.flow_pulses` | Hydropeaking and flushing observations/operating estimates; stage and catchment corrections; supported graphical classes. |
| `fishy.hydrological_transfer` | Appendix A4 transfer of characteristic quantities between qualified catchments. |
| `fishy.catchment_conditions` | Prepared drainage topology, reach changes and nearest-intervention area propagation. |
| `fishy.hydrological_condition` | Shared result contracts and Figure 33 overall-class aggregation. |
| `fishy.hydrological_assessment` | One reference/inventory/calculation assessment, including a positively surveyed empty inventory. |

`AssessmentContext` holds the physical location, actual period, source/member/
scenario/version and scoped evidence. Each `IndicatorResult` retains its raw
metrics, method source, original route inputs, class and coverage. Scientific
adequacy and official admissibility remain separate supplied findings.

Use `assess_river_hydrology` to combine reference applicability, an
`InventorySurvey`, optional attributed site selections and calculated indicators.
Canals, drains and lakes do not acquire a natural-river class through this path.
Structural naturalisation alone does not establish a suitable near-natural
reference under current landscape conditions. The reference profile distinguishes
the Swiss source from an explicit local adaptation; no Uzbek regime is inferred.

A reference with a distinct historical source period or identity uses an
explicit `ReferenceApplication`. Build its scoped finding with
`reference_application_scope(source, source_period, target_context)`. The
relation retains the original source and binds scientific permission to that
exact source and target. A changed source/target needs its own finding; copying
an accepted finding does not approve another reference. Missing or failed
application evidence leaves the reference-dependent result undetermined.

For already qualified point/reach results, `assess_hydrology` implements the
nine-position Figure 33 matrix. It is not a replacement for reference preparation
or inventory. Omitted indicators become explicit unknown entries. Two known
class-5 indicators establish overall class 5 despite incomplete coverage.

## Supply the right time and quantity

- `Flow` is an interval-mean discharge. `InstantaneousDischarge` represents a
  point-in-time reading or peak. They are not interchangeable.
- `FlowSample` retains present zero, missing, unsupported and outside-horizon
  states. Event and pulse records retain their own support and presence evidence.
- The reference flood magnitude is the mean of annual maximum **daily means**.
  Event crossings against `0.6 MHQr` use instantaneous readings, with source
  separation rules and the flushing/ecological-flood distinction.
- Monthly means use complete months. Annual means and source Q347 use complete
  calendar years. Q347 is the pooled 5% quantile; the coefficient of variation
  deliberately uses separate annual Q347 values. This is not an implicit import
  of the statutory Swiss Q347 estimator.
- Low-flow duration averages annual **longest consecutive** spells at
  `Q ≤ Q347r`. A cross-year spell remains whole and belongs to its starting year.
  A censored spell needs predecessor/successor evidence.
- Hydropeaking observation sampling needs ten calendar weeks in each of five
  operating-representative years. Supply low-flow selection, timezone, cadence,
  instantaneous flows and stage observations, including required predecessors.
  The 80th percentile of daily ratios is not a ratio of separate quantiles.
- `StageRate` is in cm/min. Discharge change cannot stand in for stage change.
  Endpoint changes only describe the supplied observation support.
- Complete instantaneous event support may be a specialist-prepared crossing
  catalogue. Sparse samples alone do not establish completeness.

Record-length recommendations do not automatically reject an indicative
calculation. Selected/excluded periods and limited coverage stay visible.
Quantile interpolation, calendar conventions and numerical tolerances are
specified in the [acceptance crosswalk](hydrological-condition-acceptance.md).

## Graphs, screening and source limits

Figures 25 and 27 are transcribed as finite supported graphical regions. Their
native-raster precision is ±2 pixels in each axis. Shared edges, ambiguity at that
precision and values outside the plotted domain return no invented class. Ordinary
results retain the raw stress/intensity/frequency and the reason. Defined interiors
compute all five classes.

A flushing frequency of 60/year or more retains the source-required hydropeaking
applicability review and any supplied judgement. It is not silently assigned a
colour from the grey region. Table 8's exact 40/year band gap is separately
undetermined. These outcomes do not disable unaffected calculations.

A source-screened class 1 is marked `SCREENED`; it is not a missing calculation
and does not claim measured absence of ecological effects. Table 9 is indicative.
Supplied site additions/exclusions and still-significant upstream influences remain
attributable. Impounded reaches remain inventory records, not river classes.

## Reach and catchment inputs

`DrainageNetwork` receives prepared node identities, total areas and disjoint
upstream relations. It rejects cycles, overlapping/nested branch contributions,
negative residual areas and incompatible scenarios. Each indicator uses its nearest
upstream interventions, not recursively rounded predecessor reach classes.
Unaffected intermediate areas require an explicit surveyed condition.

`propagate_indicator` retains the exact weighted class and rounds half upward to
the displayed integer class. Missing area below 15% is omitted from the assessed
denominator while original coverage remains incomplete. Exactly 15% is
source-equality-unresolved; above 15% is unassessed. Areas are compared before
rounding.

`delimit_reach` applies source intervention, tributary, catchment-growth,
groundwater and lake criteria to prepared inputs. `screen_ended_influence` can
carry a verified source end-of-influence decision to a downstream river section.
It does not classify the lake or hide a later significant intervention.

Appendix A4 operates on characteristic quantities, not graphical classes. It
includes both interpolation forms, single/two-donor exponent extrapolation,
specific-discharge estimates and source area-independent weights. Supply
catchment similarity and intervening-change evidence. Summed donor branches also
need disjoint prepared catchment-unit membership. A4 does not license off-plot
graph extrapolation.
