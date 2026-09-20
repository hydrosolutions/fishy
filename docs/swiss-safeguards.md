# Swiss safeguards

`fishy.swiss_safeguards.assess_safeguards` calculates supported residual-flow
lower bounds under GSchG Art. 31(2). It does not issue a permit or infer a
hydraulic, habitat or water-quality equation.

## Inputs

Declare every affected control point and exact interval as a `SafeguardSite`.
Include affected sections below the intake and below a return where relevant.
Each site carries its existing `FlowSample` starting minimum, Q347, elevation
in metres above sea level, spawning/rearing function and inventory source.
Use separate intervals for seasonal and event needs. A point inventory is a
supplied application fact; the function does not discover missing geography.

For each site, supply a `SafeguardStudy` for:

- Prescribed surface-water quality, including existing wastewater.
- Groundwater recharge for dependent drinking-water abstraction.
- Agricultural-soil water balance.
- Rare habitats and communities, whether inventoried or not.
- Free fish passage with a site-supported depth criterion.
- Spawning/rearing function where Q347 is at most 40 l/s and elevation is below
  800 m. This test uses each downstream site's elevation, not intake elevation.

A `FlowNeed` specifies the specialist-derived **total** lower bound, its valid
flow domain, site relationship and acceptance criterion. The calculation takes
the maximum only among supported same-point, same-interval total lower bounds.
It rechecks every relationship's upper domain after combining requirements.
No universal coefficient, depth threshold or monotonic habitat law is assumed.

Selected alternative measures remain named inputs and outputs. Rare-habitat
preservation measures are distinct from replacement. Replacement needs explicit
findings for equivalence, possibility and absence of overriding reasons. A bare
replacement label cannot waive the safeguard. `IMPOSSIBLE` retains a supported
failure even if another required study is absent.

## Results

Each `SiteMinimum` keeps the original site, calculated `minimum`, studies,
selected measures, original `initial_conditions`, and final `summary`.
For example, a 130 l/s starting minimum and a supported 180 l/s fish-passage
total produce 180 l/s, not 310 l/s. The initial depth criterion remains failed
in `initial_conditions`; the supported final criterion can pass separately.

Call `assess_safeguard_candidate(assessment, candidates)` before accepting a later
final total. It recomputes the original site/study inputs, rather than trusting
cached summaries or derived minima. It rechecks the actual studies, including upper domains and every
required point/interval. A passing lower-bound summary does not certify an
arbitrarily higher total.

`SafeguardUse.SCENARIO` labels exploratory calculations. `FINAL_SIZING` requires
scientifically accepted studies, not merely indicative findings. Both retain
separate official admissibility.

A numerical partial lower bound can remain available when other safeguards
are missing. Always carry `summary` into balancing and intake assessment.
A known failure plus missing evidence remains failure with incomplete coverage.
An empty affected-point inventory cannot pass.

Build evidence with `safeguard_study_scope(site, safeguard, treatment, flow_need,
measure, replacement)`. This binds the exact reviewed site and study content.
Changing a numerical requirement, treatment or site revision requires new findings.
Evidence must match this intended use, full physical
location, scenario, reference member and exact interval. Scientific use and
supplied official admissibility remain separate. The returned number alone is
neither accepted final sizing nor permission. Uncertainty in supplied samples
and studies remains available in the input records; the output does not invent
combined uncertainty bounds.

## Source and limits

GSchG consolidation 2025-08-01, Art. 31(2)(a–e), and FOEN's 2000 *Wegleitung
Restwassermengen*, section 4.4, printed pp. 39–48. The guide's 20 cm passage
recommendation is qualified, not a statutory universal value. Its seasonal
alluvial-forest example supports time-specific needs and measures, not a
universal intake/downstream conversion. Use `swiss_balancing` for the separate
Art. 33 decision and `swiss_delivery` for supported intake relationships.

Public Act: <https://www.fedlex.admin.ch/eli/cc/1992/1860_1860_1860/de>

## Source-to-test crosswalk

All flow assertions use exact rational arithmetic with zero tolerance.
`tests/test_swiss_safeguards.py` supplies original synthetic witnesses.

| Source requirement | Public input or operation | Observable test |
|---|---|---|
| Act31(2)(a), surface quality | `Safeguard.WATER_QUALITY`, `FlowNeed` | `test_all_safeguards_supported_totals_are_not_added`, `test_combined_lower_bound_rechecked_against_all_relationship_domains` |
| Act31(2)(b), both groundwater functions | `DRINKING_RECHARGE` and `SOIL_WATER` required independently | `test_all_safeguards_supported_totals_are_not_added`, `test_known_failure_survives_missing_safeguards_and_no_universal_depth` |
| Act31(2)(c), preservation/replacement | `PRESERVATION`, `HabitatReplacement` | `test_alternative_measure_avoids_uplift_and_qualified_habitat_replacement`, `test_habitat_preservation_measure_is_not_an_unqualified_replacement` |
| Act31(2)(d), site passage needs | `FISH_PASSAGE`, supplied criterion, no hardcoded depth | `test_all_safeguards_supported_totals_are_not_added`: 130→180 l/s, original stays130 |
| Act31(2)(e), q40/elevation800 | `q347`, `Elevation`, `FishFunction` per affected point | `test_spawning_boundaries_at_affected_point`, `test_high_intake_does_not_exclude_low_downstream_spawning` |
| Guide4.4 pp43–48, seasonal/event/alternative needs | Separate sites/intervals, named measures | `test_seasonal_and_event_needs_stay_at_each_interval_and_point`: winter180/event500; `test_alternative_measure_avoids_uplift_and_qualified_habitat_replacement`: no uplift130 |
| Final candidate safeguards | `assess_safeguard_candidate` rechecks real relationships | `test_final_candidate_rechecks_actual_safeguard_domains`: lower180 passes domain200; final220 fails |
| Scientific/official distinction | `SafeguardUse`, retained `EvidenceFindings` | `test_indicative_studies_are_labelled_scenarios_not_final_sizing` |
| Context and accepted subject identity | `safeguard_study_scope` | `test_findings_cannot_be_rebound_to_another_section_or_reach_revision`, `test_study_cannot_transfer_to_new_data_or_configuration_version`, `test_accepted_study_cannot_be_rebound_to_an_unreviewed_flow_requirement` |
| Absent/unknown/failure integrity | Original and candidate summaries | `test_absent_and_empty_inventory_cannot_pass`, `test_known_failure_survives_missing_safeguards_and_no_universal_depth`, `test_unknown_spawning_function_cannot_invent_a_known_failure` |

Run `uv run pytest tests/test_swiss_safeguards.py -q`.
