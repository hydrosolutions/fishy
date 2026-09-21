# Annual hydrological estimates

Use `fishy.annual_statistics` for annual mean discharge. It does not calculate
Swiss Q347, sanitary nearest-year minima, daily shapes or ecological duties.
No simulator or daily record is needed when complete annual means are supplied.

```sh
uv run python examples/annual_estimation.py
```

The example returns a median of **25 m³/s**, a supported indicative annual
screen, a prohibited sizing use, unavailable P99 ranking and an attributable
external P99 estimate. All inputs and decisions are synthetic.

## Prepare a reference

Supply `AnnualReference` with one complete annual `FlowSample` per accepted year,
a reference period, climate basis and evidence, accounting start month, fixed UTC
offset and explicit excluded years. Each year starts on the first day of the
same month. Accepted and excluded years must account for the declared period.
All accepted samples must identify the same location, scenario, reference kind
and reconstruction member. Supported reconstructed years retain their provenance.
Do not pool donor stations or members into extra local climate years.

Use `annual_mean` to aggregate contiguous interval means. It sums actual volumes
and divides by actual elapsed year duration. Partial/missing input stays
unsupported. Gaps, overlap and partial calendar years are refused. A supplied
annual interval mean can be used directly without fabricating daily values.

## Choose an estimator

- `empirical_estimate` uses descending Weibull positions and linear discharge
  interpolation. A target outside rank support returns `value=None` with a reason.
  It never clamps or extrapolates.
- `empirical_membership` retains every year and gives tied values the mean of
  their rank positions. Probabilities refer to the full accepted reference.
- `fitted_estimate` fits the selected stationary zero-mixture lognormal candidate.
  It needs at least two positive values with positive log variance, even for a
  target at the zero atom. This is one candidate, not an automatically best family.
- `fit_zero_mixture` exposes parameters and both sides of every empirical and
  fitted jump. `distribution_distance` is their supremum absolute difference,
  without an independent-sample significance claim. The jump records also supply
  the values and probabilities for caller plots. `fitted_membership` uses atom
  midpoints, not rank probabilities.

`AnnualEstimate` retains the reference, estimator/profile, target, provenance,
rank neighbours or fitted parameters, and reasons. Probability and discharge
support distances are separate. No observed zeros proves neither perennial flow
nor tail validity. Annual-mean targets are not return periods for duration minima.

## Import specialist estimates

Use `import_annual_estimate` with `ImportedDerivation`. Identify the equation,
parameter estimation, calibration data, diagnostic artifacts, extrapolation,
uncertainty and reproducibility reference. A nonstationary import also needs
covariates and an evaluation date/scenario. `ImportedAnnualReference` retains
accepted/excluded years and reference identity without requiring raw calibration
values. Discharge support distance is then unknown, not invented.

The import boundary checks declarations and identity. It does not independently
validate an unseen model, retrieve artifacts or accept unexplained numbers.

## Check a proposed use

Build or obtain scientific `EvidenceFindings` for `estimate.scope(intended_use)`.
The scope includes the annual statistic, target, estimator/profile, reach, member
and reference period, plus a content fingerprint of the complete reference/result.
The fingerprint includes climate, calendar, full location versions, accepted and
excluded years, values and derivation. Reference population order does not change
it. The finding must retain the estimate's exact provenance.
Call `annual_use_checks` alongside the application's scientific criteria.

A numerical result is not an acceptance decision. An untreated genuine trend
blocks stationary present-climate use; unassessed climate treatment stays unknown.
Supported nonstationary imports remain possible. Rating restrictions bind even
for indicative findings. Official approval remains separate. A short record alone
does not reject a computable, supported annual use. No annual finding establishes
a daily pattern, minimum or rare-tail application.

## Consume sampling uncertainty

`fishy.sampling_uncertainty` checks external results rather than generating them.
Supply a `SamplingPlan` with consecutive complete annual years, circular block
indices, integer `1 <= L < n`, `B >= 2`, generator/version/seed and uniform starts.
`L=1` needs an independence justification; other lengths need dependence and
block-length sensitivity evidence. Related `ReplicateSeries` must retain exactly
the same indices and estimator/version. Every replicate is either a `Flow` or an
attributable `ReplicateFailure`.

`sampling_intervals` computes ascending linear-interpolated endpoint quantiles.
Any failed replicate prevents that quantity's interval; all failure indices and
reasons remain available. The interval is conditional stationary sampling
uncertainty, not total uncertainty. Statistical circular indices never permit
physical hydrograph wrapping.

`FlowCovariance` checks compatible squared-flow units, exact symmetry and positive
semidefiniteness. `propagate_linear_covariance` returns `cᵀΣc` for dimensionless
signed `LinearFlowCoefficients`. It does not turn a standard deviation into a
verdict half-width. That requires a separately supported coverage/distribution
interpretation. Nonlinear tail uncertainty needs its own supported analysis.

See the [source and executable acceptance crosswalk](annual-statistics-acceptance.md).
