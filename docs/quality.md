# Quality assessment and conservative feasibility

Fishy evaluates one supplied quality profile at one location and interval. It also
solves a fixed-boundary conservative mixing screen. These are separate operations.
A quality result does not select national standards, certify ecological status,
issue a discharge permit, or establish pollution responsibility.

## Choose the operation

- Assess observations, imported concentrations or supported process outputs with
  `fishy.quality`. No simulator is required.
- Solve the full additional-arrival-flow interval with `fishy.mixing`.
- Screen fixed-water load reductions with `fishy.source_control`.
- Check local and basin inventories, transfers and processes with
  `fishy.load_accounts`.
- Apply the report's five activation conditions with `fishy.quality_activation`.
- Read inactive source records with `fishy.catalogue`. See
  [catalogue sources and limitations](catalogue.md).

## Configure a profile, not a national verdict

Identify the jurisdiction, instrument and version, category/use, exact section,
period, required tests, sampling basis, chemical form/fraction and reporting basis.
Supply applicability and any exclusions. A scenario override creates a new profile;
it never rewrites the original profile or an earlier result.

A plain source number does not choose an upper operator. A dash does not mean zero.
A range cell without an interpretation remains unresolved. Similar names and equal
units do not prove chemical identity. No nitrogen-to-ion or conductivity conversion
is inferred. Source-table categories remain source-local.

Individual upper, lower and range checks retain strict endpoints. Configured group
checks retain every required member and positive denominator. TDS stays outside
ionic sums containing its constituents. A supported individual failure remains a
failure when another required test is unknown; coverage remains incomplete.

Uncertainty bounds are not probabilities. An upper test passes only if its entire
supplied interval passes, fails only if the entire interval fails, and is otherwise
indeterminate. Non-detects retain their reporting limits and censoring. Without a
reporting limit they are missing, never zero. Numerical accounting precision is not
measurement or model uncertainty.

## Fixed-boundary mathematics

Declare background water `Qb` in m³/s, loads `Bi` in kg/s, and additional **arrival**
water `q` with source concentrations `Csi` in kg/m³:

```
Qsection = Qb + q > 0
Ci(q) = (Bi + q*Csi) / (Qb + q)
```

All other water carriers belong in `Qb`, their loads in `Bi`, and separate loads
enter once. Exclude the controllable arrival and its load from both background
terms. Inputs must remain fixed as `q` changes. Changing returns, composition,
storage, evaporation, withdrawals or travel time needs recalculation or another
supported physical model. A point sample alone does not establish complete mixing.

Each original test becomes an exact linear inequality. The solver intersects all
lower and upper bounds, including strict endpoints, with positive section water,
nonnegative arrival water, operational limits, capacity and a matched ecological
total or floor. A dirty source or lower quality limit can impose an upper flow bound.
Taking only the largest dilution minimum can therefore give a false answer.

The quality-only interval and combined interval remain separate. An open lower
endpoint is an infimum, not an attained minimum. Fishy never adds an epsilon to
invent a smallest compliant release. With a dry boundary, `(0, infinity)` has no
quality-only minimum. A separately supplied positive base floor can still select a
combined candidate. Recheck supplied candidates in the original concentration tests
after ecological or receptor uplift.

A conditional `Qquality = Qb + qmin` is not an independently protected legal or
ecological floor. Background abstraction or changed loads require recalculation.
Arrival flow is not an upstream release without a supported routing relation.

## Control loads before residual dilution

At fixed water discharge, a single controlled load has allowance `T*Q - Bother`.
Negative allowance means background alone fails; it is not a negative permission.
A whole-drain screen scales all its loads with one common factor in `[0, 1]`, while
holding its water fixed. Removing water as well requires a new balance.

Residual-flow activation requires evidence that controllable discharges have been
addressed. It is reserved for remaining uncontrollable diffuse loads. Source tags
and unmatched mass remain bookkeeping, not causal or legal attribution. Local and
basin accounts retain explicit inventories, inputs, outputs, processes and residuals;
internal transfers cancel. No unexplained residual becomes an invented sink.
Activation requires an explicit mapping from account transfers to background and
excluded controllable arrivals. Every section inflow is classified once. Account
water/load rates must match the fixed boundary; arrival composition must match the
supplied source. A closed but unrelated or empty account cannot certify a wet,
loaded boundary.

## Activation and process limits

The report component requires all five conditions: a reach/season feasibility
screen, held fisheries targets, approved harmfulness grouping, a basin salt budget,
and an NCECC-approved salt-transport model. Even then it binds only where feasible.
Inactive screens stay advisory and retain the base result. Hypothetical activation
needs an explicit scenario label, not invented approvals.

Base, quality and combined findings remain separate. A floor-only route may receive
a quality floor uplift, but does not gain a seasonal requirement, issued obligation
or delivery verdict. Complete receptor and Uzbek regime assembly belong to their
own consumers.

Supported oxygen, pH, temperature and nutrient process outputs can be assessed. Their
corrective flows cannot be predicted with conservative-ion mixing. Signed pH and
temperature values retain their declared domains. No reactive chemistry, oxygen,
thermal, hydraulic or habitat solver is supplied. Air-temperature regression does
not establish reservoir withdrawal temperature.

## Source interpretations remain explicit

SanPiN 0083-24 §22 prose and displayed formula differ at equality. The held official
HTML element `7354152` retains the strict sign. Explicit inclusive, strict and
unresolved-equality scenarios remain separate. SanPiN §§5/22 and draft Пакет 7272
§35 do not automatically share group applicability.

The report recommends one organoleptic group, with qualifier subgroups as a
sensitivity alternative. The external acceptance harness compares both configured
interpretations. Fishy does not orchestrate comparisons or choose the interpretation.
Under DP-QUAL-1's working reading, assigned-category limits size flow while stricter
general SanPiN constraints are assessed separately. Official applicability remains
unconfirmed; neither a stricter substitution nor a claimed sanitary pass is inferred.

## Physical exchange

`PhysicalProjection` consumes current Taqsim's live and saved physical results.
Incoming/outgoing transfers differ from final storage. Concentration is the exact
sum of transported mass divided by the sum of transported water, never a mean of
concentrations. The actual interval duration converts volume to mean flow. Saved
results are physical documents, not resumable checkpoints.

The A13 integration test runs two realised sources through a mixing reach: 10 m³
at 0.8 kg/m³ plus 5 m³ at 0.2 kg/m³ gives 15 m³ and 9 kg. The resulting 600 mg/l
fails an explicitly configured 500 mg/l upper limit. Fishy adds no water or mass.
Missing required chemistry retains incomplete coverage beside that supported failure.

See [executed acceptance crosswalk](quality-acceptance.md) for inputs, exact revisions,
expected and actual outputs, tolerances, and source dispositions.
