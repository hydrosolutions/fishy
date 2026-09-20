# Swiss interest balancing

`fishy.swiss_balancing.assess_balancing` evaluates a supplied Art. 33 decision.
It does not choose economic weights or determine the authority's judgement.
It runs without Taqsim, HYDMOD or hydrological estimation.

## Inputs

- `preceding_minimum`: an immutable `FlowSample` schedule for one exact location,
  scenario and reference member. Supply the supported Art. 31 minimum or the
  applicable Art. 32 exception minimum. Assess other protection locations
  separately, including normal protection beyond a limited exception reach.
- `preceding_summary`: the retained minimum/safeguard assessment. A failed
  safeguard cannot become a pass through economic balancing.
- `safeguards=`: the actual `SafeguardAssessment`, including site studies and
  their relationship domains. Its studies are rechecked at each proposed final
  total by `assess_safeguard_candidate`. A previous passing summary alone cannot
  certify the new total; omitted studies leave support unresolved. An authorized
  decision requires `SafeguardUse.FINAL_SIZING`, not an exploratory scenario.
- Alternatively, `exception=` supplies the actual `ExceptionAssessment` for one
  exact location, period, scenario/member and data/configuration version. The
  exception is recomputed from its stored conditions and decision, rather than
  trusting its cached summary. Its applied minimum must equal the preceding
  sample. Supply either normal safeguards or an exception, not both; assess
  outside-exception locations and periods separately with normal safeguards.
  A hypothetical exception cannot support an authorized final total.
- `BalancingDecision`: identifier, decision maker, rationale, explicit
  `BalancingBasis.HYPOTHETICAL` or `AUTHORIZED`, final total schedule,
  interest considerations, applicant report and `EvidenceFindings`.

Use `balancing_scope(preceding_minimum, final_total)` to construct the scientific
context scope for the interest and applicant-report findings. Its product binds both
complete immutable schedules: location (body, reach, section and mapping
versions), every interval and amount, presence, uncertainty, and provenance
including data, configuration and software versions. A changed final total needs
new scoped evidence. Do not construct a reach-only substitute.

Construct `BalancingDecision` with `evidence=None`. Then attach decision findings
using `balancing_decision_scope(preceding_minimum, decision)`. This second scope
also binds its identifier, decision maker, rationale, hypothetical/authorized
basis, all interest assessments and the complete applicant report, including
their scientific findings. Only the decision's own evidence wrapper is excluded
from the fingerprint. A draft without reviewed evidence remains unresolved.
Changing a decision's attribution or content requires new scoped review; changing
its enum from hypothetical to authorized cannot reuse the old findings.

Supply evidence with the same scenario/member/reference kind. Each
`InterestConsideration` identifies one `AbstractionInterest`, the study's
assessment, and scoped evidence. All nine statutory groups are required:
public interests, source-region economy, applicant economy, energy, landscape,
habitats/biodiversity/fish yield and natural reproduction, long-term water quality,
future groundwater/drinking water/land use/vegetation, and irrigation.
An irrelevant interest still needs a reasoned supplied assessment.

`ApplicantAlternatives` retains the applicant, effects of alternative abstraction
rates, energy production/costs, anticipated protection impairments and prevention
measures. State why energy is inapplicable for a non-energy application. Missing
reports or interests remain unresolved. The software checks supplied evidence
acceptance, not the truth or completeness of free-text study conclusions.

Each final sample must match a preceding sample's exact location and interval.
There is no implicit resampling or routing. Seasonal totals are compared against
seasonal minima independently. An interval omitted from the final schedule stays
unknown. An unlisted interval or mismatched location/scenario is refused.

## Outputs

The decision retains its numerical candidate, uncertainty and provenance.
A final-total schedule cannot be labelled `ProductionMethod.OBSERVED`: a
prescription is not an observation. Study evidence excluded as warm-up cannot
support sizing for that period.
`balancing_summary` reports the decision, report, interests, numerical minimum
comparisons and actual final-candidate safeguard rechecks. The result also retains
its input `safeguards` assessment. `preceding_summary` remains separate; `summary` includes both.
`supported_final_total` is available only when all required checks pass. An empty
preceding summary cannot establish support. Unknown or unsupported values never
become zero. A known failure remains failure with incomplete coverage when another
check is missing.

For a supported preceding minimum of 180 l/s and a supported decision of 220 l/s,
the final total is **220 l/s**, not 400 l/s. A second season with a preceding
minimum of 250 l/s makes that season's 220 l/s proposal fail. The original
schedule is not changed.

`official` reports supplied decision admissibility separately. A hypothetical
scenario can have a supported total while `official` remains unknown. An
`AUTHORIZED` basis also requires admissibility in the exact scope. No arithmetic
result authenticates a permit. Indicative scientific evidence remains visible but
does not qualify final sizing. Final totals are residual needs, not intake duties;
supported downstream-to-intake mapping is a separate operation.

## Source and executed test crosswalk

Primary source: [GSchG German consolidation, 1 August 2025](https://www.fedlex.admin.ch/eli/cc/1992/1860_1860_1860/de), Art. 33.
Supporting source: [FOEN residual-flow guide (2000)](https://www.bafu.admin.ch/dam/de/sd-web/DURPl8AmZvgE/angemessene_restwassermengenwiekoennensiebestimmtwerdenwegleitun.pdf),
§§4.5–4.6, printed pp. 48–62. The amended Act controls.
All witnesses are synthetic. All flow comparisons are exact rational comparisons;
numerical tolerance is zero. Tests are in `tests/test_swiss_balancing.py`.

| Clause / requirement | Operation and observed result | Executed test |
|---|---|---|
| Art. 33(1), final total | `assess_balancing`: 180 → 220 l/s, final 220 | `test_supported_final_is_total_not_added_and_hypothetical_stays_hypothetical` |
| Art. 33(2)(a–d), (3)(a–e) | Each missing enumerated interest yields unknown | `test_every_enumerated_interest_is_required` (nine cases) |
| Art. 33(4)(a–b) | Missing alternative/mitigation report yields unknown | `test_report_and_decision_required_even_after_exception` |
| Guide §§4.5–4.6 | Exception minimum 35 l/s does not remove balancing requirement | same test |
| Art. 33(1), Art. 35(2) minimum retention | Seasonal 220 < 250 fails despite missing interests | `test_seasonal_minimum_failure_survives_missing_interest` |
| Art. 31(2) separation | Failed habitat + missing quality survives supported economics | `test_preceding_failure_is_not_erased_by_economics` |
| Exact scoped evidence | Foreign scenario/member/reference/location/interval cannot transfer | `test_cross_identity_final_cannot_supply_a_decision`, `test_wrong_location_or_interval_cannot_transfer` |
| Scientific / official separation | Indicative and out-of-scope support withheld; invalid evidence fails | `test_evidence_changes_affect_outcome` |
| Attributed authority | Pending cannot authorize; supplied admissible decision can support total | `test_authorization_is_supplied_not_inferred_from_numbers` |
| Scoped authority | Admissibility for another reach remains unknown here | `test_official_status_does_not_transfer_out_of_scope` |
| Coverage / presence | Missing season, empty checks and unsupported minimum cannot pass | `test_missing_schedule_interval_and_empty_preceding_checks_cannot_pass`, `test_presence_and_unknown_minimum_never_enable_lowering` |

Run:

```sh
uv run pytest tests/test_swiss_balancing.py -q
```

The caller must retain the complete required site inventory. This one-location
operation cannot detect protection sites omitted by its caller. It does not verify
exception eligibility or replace the separate safeguard and intake operations.

Additional scope regressions in `test_evidence_cannot_rebind_to_changed_subject_identity`
exercise section, mapping, reach/body revisions and data/configuration revisions.
All remain unknown under unchanged evidence. `test_derived_final_total_cannot_be_labelled_observed`
refuses observation laundering. `test_decision_evidence_excluded_warmup_cannot_support_total`
keeps excluded study evidence unresolved. These eight tests failed on the old
path before the repair and pass on the repaired path.

`test_decision_evidence_cannot_authorize_changed_final_amount` proves that changing
an already reviewed 220 l/s total to 999 l/s cannot retain supported status from
the previous decision evidence. It failed before the final-subject scope repair.

`test_minimum_summary_alone_cannot_certify_final_safeguards` first proved that
an old passing summary could certify a new candidate without its studies. Such
calls now remain unknown. `test_actual_final_total_rechecks_safeguard_upper_domain`
uses a real `SafeguardAssessment`: the supported minimum 180 l/s passes a domain
ending at 200 l/s, but proposed final 220 l/s fails. No generic supplied check can
replace this candidate evaluation.

The `exception=` route retains the recomputed exception and all its checks.
`test_separate_balancing_after_supported_exception` exercises a supported Art.
32(b) reduction from 130 to 35 l/s, followed by a separate hypothetical Art. 33
final total of 40 l/s. Tests also reject changed exception conditions/amount,
wrong location/period/configuration, multiple periods under one exception,
hypothetical-to-official promotion and ambiguous normal/exception combinations.
An independent preceding failure remains failure.

Art. 33's attributed decision is also covered by
`test_reviewed_decision_cannot_change_authority_or_content`: unchanged admissible
findings cannot support a changed basis, issuer, identifier, rationale, interest
assessment or applicant mitigation. All six cases failed before the decision-scope
repair. `test_two_stage_decision_requires_attached_reviewed_evidence` checks
unreviewed and supported states for both explicit decision bases.
