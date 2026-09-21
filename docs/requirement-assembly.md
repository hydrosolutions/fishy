# Assemble and check uncapped requirements

Fishy assesses one supplied configuration. The caller runs reference members and
selects a complete family. Requirements are not deliveries, water sources, or
extra consumptive demands. All examples below are hypothetical scenarios, not
adopted Uzbek policy or validated basin applications.

Run the complete worked example:

```console
uv run python examples/requirement_chain.py
```

It uses full daily reference years (2001–2002), complete 2003 design classes,
explicit preceding days, real statistical/pattern operators, active mixing,
a supported lateral wetland schedule, and final hydraulic/habitat checks.
It then derives the floor and issues the class95 obligation. The example also
shows a direct floor, missing evidence, and an independently prescribed duty.

## Compose one interval

`requirement_composition.compose_requirement` receives an ecological `FlowSample`,
an output `Provenance`, and optional actual `QualityComponent` and `ControlMapping`
inputs. Build quality with `quality_activation.apply_quality_component` first.
The base, quality result, mapping, uncapped candidate and checks remain separate.

A supported same-water mapping combines lower bounds by maximum. A lateral
mapping combines continuing river flow with the **upstream control release** for
the selected receptor schedule. Obtain that release from the signed storage/loss/
travel account in `receptor_delivery.map_arrival`, then verify the actual selected
schedule with `assess_delivery`. `ControlMapping` itself represents only its
explicit zero-loss, zero-delay shared section relation. It is not a general
network solver. Missing mapping evidence leaves integration unresolved and keeps
the separate operands. Multiple pathways need a supplied allocation.

Quality remains advisory unless activated under its own rules. Hypothetical
activation does not waive source controls, account closure, or original limits.
Floor-only quality produces a floor, not a regime or obligation.

## Verify the external selection

`RequirementFamily` contains all four `ClassRequirement` records on one complete
fixed-day accounting year. `FloorSeries` instead contains the complete declared
direct-floor period, without invented design classes. Both use `FamilyBasis`:
location, calendar, scenario, method, parameter version, activation version and
reference kind. Flow samples retain their own member, data and software identities.

For every retained member supply a `RequirementMember`. Its evidence scope is
`candidate_scope(candidate)`, which binds the exact values and identities.
A `SelectionSpecification` fixes the retained IDs, exclusions with reasons,
configured threshold, reconstruction applicability and source. Different policy
configurations are separate studies, not uncertainty members.

```python
selection = assess_selected_family(members, caller_selected, specification)
```

Fishy verifies the supplied candidate against the median or upper envelope over
**every** class and day. The whole-family spread selects one branch. Equality
uses the median. Zero/zero spread is zero; zero median with positive maximum has
infinite spread. Every tied minimum, maximum and median contributor is retained.
No delivery cap enters this calculation. No selected natural mosaic or new natural
cap is constructed. Original member hydrology/bound results remain in typed construction records and
are recomputed at finalization, as the complete example demonstrates.

Every natural baseline, top or transfer family needs at least two accepted,
structurally distinct reference members. One member remains visible for screening;
`NOT_REQUIRED` and imported or observed labels cannot waive this rule. Direct
floors derive applicability from their actual accepted source. Potential floors
and an accepted observed-statistic entry do not acquire a reconstruction gate.
A presumptive reference without proof of direct observations still needs structural
selection. Imported or hypothetical production labels alone are not that proof.
A missing external candidate stays pending. Failed member support remains failed
even if another check or the selected result is missing.

## Repeat final physical checks

`requirement_checks.assess_requirement` rechecks one exact final `FlowSample`.
Its manifest declares extra quality, mapping, receptor, hydraulic and study checks.
Finalization also derives mandatory checks from the actual source and composition:
a mapped receptor requires final mapping and quantity/salinity evidence; source
study criteria and process conditions cannot be dropped or relaxed. An empty
manifest cannot pass. Missing required
inputs remain unknown. Use `sample_subject(sample)` as the candidate ID in supplied
mapping, receptor, hydraulic and study records. Changing the flow, interval or
provenance changes this identity.

The operation calls the existing original mixing tests, `control_equivalent`,
`assess_delivery`, `assess_hydraulics` and `assess_study`. It does not consume
unscoped PASS flags. The mapped continuing flow is the quality operand; receptor
pathway releases must match the mapped diversion. A final uplift can violate a
quality upper-flow bound, hydraulic limit or habitat relation. Supported imported
physical evidence still requires exact subject, scope and use acceptance.

## Finalize a regime or direct floors

`requirement_finalization.finalize_regime` receives the selected family, its
`EcologicalRegimeMethod`, required physical conditions and exact class/day
assessments. The method must match the immutable family basis. Supply all configured
retained-member tests in `expected_duration_tests`. Each applies to every class.
A `DurationTest` provides its threshold, exact scientific assessment, explicit
predecessors, reference relation and uncertainty support. The operation runs
`assess_low_flow` itself on the actual selected samples. It also recomputes
`provisional_diagnostics` from each native pre-quality member source and every
configured class/test. Caller-supplied summary findings cannot replace these
results. Supply `provisional_duration_tests` for explicit pre-quality predecessor,
reference-relation and uncertainty inputs; final-flow predecessors are never reused
as pre-quality context. Missing source, tests, spatial correspondence or preceding
days remain explicit unknown diagnostics. Provisional failure or uncertainty does
not gate final issue: active quality can repair a final requirement. Baseline needs
configured tests for every retained member;
other methods acquire no implicit baseline gate.

Supply `MemberConstruction` records for every retained member. Their
`NaturalRouteInputs` locate the prepared classification and carry the actual tier
inventory, resource/specification evidence, priority and failed attempts.
Finalization calls `select_natural_route` again. Required hydrology and disclosure
must belong to the same member source. A valid heavily-modified designation,
unresourced tier or unrelated disclosure cannot be bypassed by constructing a
baseline arithmetic result directly. This route proof does not apply to potential
floors or independent existing duties.

Each construction holds its
actual typed pre-quality source (`BaselineSource`, `TransferResult`, or
`StudySource`) and all class/day `ClassComposition` records. The final boundary
recomputes those sources and quality/mapping operations. Every original base and
assembled member value must match. Sizing needs exact sizing permission; screening
permission cannot silently become sizing. A later uplift cannot repair rejected
natural bounds or scientific products.

Supply the original retained members' `MemberPhysical` assessments and
`member_duration_tests` separately from the selected-family inputs. The boundary
recomputes both sets. Missing or failed retained members decline the supplied
selection; Fishy never silently removes them and selects a convenient subset.
It also recomputes selection arithmetic and physical findings from retained inputs,
so replacing a summary PASS does not bypass the checks. Actual quality activation
and target policies must agree at each class/day across retained and selected
candidates, not just share a version label. Actual source estimators, derivation
methods, acceptance thresholds, pattern settings, alpha, winter shares, spawning
coefficients, study criteria and transfer qualification policies are also compared.
Reference values and member-specific evidence can differ without changing policy.

The scalar floor is the annual minimum of final class95. It must not exceed any
day in any class. `natural_floor` exposes this numerical diagnostic separately;
it does not authorize issue. `finalize_regime` returns the new requirement and
`Floor` only if every required check passes. Known failure survives missing
coverage. Failure or uncertainty returns neither a new regime nor floor. The
candidate and diagnostics remain visible. Its `route_failure` feeds
`natural_routing.select_natural_route` to try an eligible lower route without
retrying the failed one. No class is lifted, floor lowered, or prior issue mutated.

Use `finalize_floors` for entry, presumptive or potential floors. Supply each
member's `FloorConstruction`: actual `EntryFloorSource`, `PresumptiveFloorSource`
or `PotentialFloorSource` inputs and every daily `FloorComponent` composition.
The function recomputes the original route and final quality adjustment.
Entry keeps its statistic, curve, screen and natural eligibility. Presumptive
keeps its accepted reference, seasonal fractions and natural classification.
Potential reruns its own classification and habitat/hydraulic/service hierarchy;
unresolved earlier ecology remains visible without becoming a baseline gate.
An arbitrary positive series and a generic acceptance flag cannot stand in for
these source inputs. Supply `FloorMemberAssessment` records for every retained
member interval as well as the selected-floor checks. Both are recomputed against
their own exact floor series. The result creates neither a regime nor obligation
and has no baseline-only safeguard argument.

A source study's original criteria, relation geometry and process conditions remain
binding at the actual final flow. `source_conditions` repeats the original numeric
responses and requires fresh exact-candidate support for final study/process checks.
A missing final study cannot hide a known habitat violation. A weaker final target
or a more favourable replacement relation cannot replace the source constraints.
For an explicit mapping, study evidence may refer to the continuing section: lateral
water uses its continuing flow; shared water uses the actual final shared flow.

A seasonal potential threshold can apply to daily floors only with separate
constant-threshold support. Use `source_period_scope(selection, relations)` to bind
that permission to the complete original study, relations and full source period.
Place the accepted findings in `PotentialFloorSource.constant_thresholds`. One
full-period permission can support all contained daily intervals; each final daily
quality and study check still needs exact-candidate evidence. Supplemental process
conditions need their own bound temporal permissions. Missing permission stays
unknown; an interval outside the supported season fails. This does not disaggregate
an annual/seasonal mean flow or infer subdaily constancy.

Issuance is separate: `uzbek_issuance.issue_obligation` uses the minimum of the
requirement and deliverability. The complete requirement remains unchanged.
`delivery_assessment` and `floor_assessment` assess their different immutable
issued comparators. An annual scalar floor can be carried unchanged onto its
applicable daily control interval; do not change its value from actual delivery.

## Original obligations at final flow

`IntervalComposition.receptor_source` retains the original `DeliveryStep`.
Finalization repeats its quantity, state, salinity, pathway and water-account checks
in `receptor_conditions`. Fresh final evidence cannot remove an original duty or
relax its limits. A native storage endpoint remains an exact endpoint, not an
inferred minimum. Missing original proof stays unknown.

For lateral water, keep the original supported withdrawal schedule. In the worked
example it is 1 m³/s, so selected continuing flow is selected upstream flow minus
1 m³/s. No second median or envelope is applied to components. Different original
schedules leave the selected decomposition pending. A changed withdrawal is not
an automatic reallocation: supply a supported alternative with the original river
and receptor constraints, or recompose the family before selection. Shared water
uses the actual shared flow for physical checks.

An accepted zero determination does not erase the numerical source that produced
zero. A zero-valued habitat or hydraulic study remains binding after positive
quality uplift. A service account reconciled by the zero determination also keeps
its domain, capacity, ramp and balance constraints. Unused fallback sources are
not added to a successful positive study route.

After whole-family selection, original quality concentrations and operational
limits remain binding. A contributor's pre-quality ecological base is not reapplied
as a new lower bound on a valid selected median. Retained members still keep their
own base. Advisory quality remains visible in source records without requiring a
final quality condition; explicit activation-policy inconsistencies still fail.

For a selected service-conveyance route, `conveyance_conditions` evaluates the
actual final local flow against the original relation domain, capacity, ramp and
service balance. It does not resize the service requirement from the quality
uplift. Excess remains separate from the fixed service duty. Only the original
numerical stopping tolerance applies to the service balance; the raw deficit is
retained and capacity/ramp limits are not relaxed.

`provisional_duration_tests` can carry the original local threshold and scientific
support independently of the final control-section test. Optional
`DurationTest.candidate_support` supplies uncertainty for exact native source
samples. Values, location, period and provenance must match; only uncertainty can
be added. The worked example retains eight complete local-R provisional PASS
assessments. Missing support remains unknown. These diagnostics never gate a
supported repaired final requirement.

## Limits

The report controls these proposed Uzbek operators. It supplies no adopted
threshold, donor qualification, biological tolerance, accepted physical model or
legal finding. The two synthetic reference structures and their scientific
acceptance are stipulated for the worked example. Rare-year extrapolation stays
explicit. The reported 21/21 dry-case seven-day-minimum overestimation is a method
limitation, not a correction factor. Neither passing this calculation nor passing
its safeguard validates a natural reconstruction or confers authority to replace
an existing issue.
