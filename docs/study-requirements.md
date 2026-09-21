# Study requirements and potential floors

These operations calculate one supplied study configuration. They do not select national targets, authenticate decisions, issue delivery duties, or run a habitat simulator.

## Select and assess a study flow

Run the complete synthetic example:

```console
uv run python examples/study_requirements.py
```

The example supplies a non-monotone flow–habitat curve, an ecologist-selected flow of 8 m³/s, an accepted habitat range, an exact season, and attributable sediment, hydraulic, flood-safety and ramping findings. `assess_natural_study` calculates 52 m² of habitat and retains the 8 m³/s pulse. The 3 m³/s baseline median cap is reported but does not clip it. A supported pulse is not release permission.

Public imports are from `fishy.study_requirements`, `fishy.potential_requirements`, and `fishy.service_conveyance`.

- `assess_study(selection, relations)` evaluates the supplied flow on exact points or explicitly accepted piecewise-linear relations. It never inverts a non-monotone curve. A selected holistic requirement can instead carry a fully attributed `holistic_assessment` with its criterion, assessed value, domain and scientific evidence. Depth and velocity criteria use the same selection. Each variable retains units, bed/direction reference and spatial domain.
- `assess_natural_study(...)` keeps independently usable components, missing study needs and the supplied eligible descent route. Valid heavily-modified designation blocks new natural calculations. A sediment-trapping trigger needs an accountable owner and deadline. Pulse safeguards are required even when omitted from the caller's condition list.
- `size_potential_floor(...)` tries habitat, joint depth/velocity, then authenticated service conveyance. Earlier missing ecological conditions remain in `routes` after later success. Winter-share sizing is suspended. The result is a seasonal floor candidate; full requirement and newly derived delivery obligation remain pending.
- `retain_requirement_history(...)` preserves issued versions until a supported supplied competent replacement names the previous version. A designation before first calculation creates no fictional natural result. Replacement recording does not authenticate or issue its supplied duties.

`StudyScope` binds candidate, physical location, scenario, reference member, exact interval, season and purpose. `EvidenceFindings` retains disclosure, scientific permission, reason-specific restrictions and official admissibility separately. Indicative evidence can calculate when permitted. A pending official decision does not prevent a supported hypothetical calculation. Unknown components never count as passes.

## Service conveyance

`solve_service_conveyance(request)` uses interval volumes and actual elapsed seconds. Supply authenticated duties at named service points, a supported relation, other timed inflows, capacity, initial trial, initial storage, ramp transition, and stopping rule before calculation.

The relation maps trial flow to final storage and named loss volumes. Every point carries the same loss destinations; an explicit empty loss tuple means accepted zero losses. Unknown losses require an absent or unsupported relation. The operating rule or approving act takes precedence over the permit entitlement. Observations never become duties. Multiple competing primary duties at one point are rejected rather than merged.

For each trial:

```text
required volume = scheduled duties + final storage - initial storage
                  + named losses - other accepted inflows
residual = trial flow × interval seconds - required volume
```

The next trial is the required interval volume divided by its duration. All trials, residuals, destinations, storage, capacity and ramp checks remain visible. Only a converged supported feasible trial returns `flow`. Failure or nonconvergence returns `None`, not the last iterate. A seepage destination remains a transfer; no return is subtracted without its own exact timed, located supported inflow record.

The supplied ramp operator is an inclusive directional discharge increment over a declared elapsed transition. Its trace also reports the discrete rate. It is not an instantaneous or within-day maximum test. Other hydraulic operators remain separate.

## Zero, additional conditions and existing duties

A numerical zero from any route still needs `ServiceZeroDetermination`: evidence, audited service determination, Committee sign-off, audit right, dispute route, supplied service-impact criterion and responsible dated review. Designed-dry treatment also requires an adopted or explicitly hypothetical characteristic-drying interpretation. Missing evidence never authorizes zero. Hypothetical treatment stays labelled.

`additional_conditions`, `active_quality` and `existing_duties` are retained unchanged for final assembly. A successful service balance makes no ecological-adequacy claim. Unsupported groundwater dependence and applicable unsized reservoir thermal conditions remain explicit conditions with the supplied review milestone. No natural conservative interim value or air-temperature substitute is inferred. Quality/receptor reconciliation and final Uzbek issuance are deliberately outside these operations.

## Scope and limits

Relations are supplied surveyed tables with supported interpolation, not native basin-wide physical models. Each call has an exact interval; callers supply separate seasons and schedules without implicit resampling. Numerical tolerance is engineering precision, not scientific uncertainty. The tests use synthetic settings, not policy defaults or calibration. Physical body and calculation reach are separate `Location` records; no plan assignment is needed to calculate.

See [the acceptance crosswalk](study-requirements-acceptance.md) for source pointers, numerical witnesses and executed commands.
