# Ecological donor transfer and presumptive floors

These are configurable proposed Uzbek fallback methods. They do not supply adopted national settings or qualify a real donor.

## Transfer one ecological relationship

`transfer_ecological_regime` consumes:

- One complete **pre-quality** `EcologicalMemberCandidate`. A final requirement, sanitary duty, delivery cap or advisory spawning schedule is not this input.
- Four accepted `DailyPattern` objects for the donor and four for the recipient. Their own, **unshifted** exceedances are 25%, 50%, 75% and 95%. Each family uses one exact natural reference and one intended-use scope; separately accepted scopes cannot be mixed across its classes.
- One `TransferProfile`, selected before `evaluated_at`, with a reason independent of the answer.
- `QualificationTest` criteria and observations for regime, intermittency, ecological purpose, the transferable relationship and recipient evidence. Limits are supplied, never defaults.
- An accepted `EvidenceFindings` bound by `transfer_scope` to the exact donor candidate, both natural families and the transfer profile. Changing their content invalidates that permission. Natural patterns also need their separate content-bound annual and daily scientific assessments for sizing.
- A versioned directed `TransferRegister`.

For each class, Fishy divides the donor ecological discharge by the donor natural discharge. It maps this **dimensionless ratio** to the recipient calendar, then multiplies by the recipient natural discharge. A donor ecological pair 2/4 over natural 4/8 has ratios 0.5/0.5. Recipient natural flows 6/10 give ecological flows 3/5. Donor quality values 5/6 are not operands.

Both families cover complete real accounting years. Accounting starts and fixed UTC offsets must match. Leap-month mapping takes overlap-weighted within-month ratio means. A constant ratio remains constant across February; its annual sum need not be conserved. There is no volume mapping, area scaling, melt shift or second probability shift.

Zero donor denominators, including 0/0, make the complete transfer unavailable. Supported finite ratios times recipient zero return zero. Ratios above one are not clipped. `RatioMapping.above_one_days` and `adequacy_check` retain the need for transfer-adequacy review. A transferred donor cannot seed another transfer. The register checks reach identities, including transfers through different sections of one reach, and the successful result adds its directed edge.

`TransferResult` retains inputs, evaluated time, source and mapped ratios, acceptance and failed checks. The optional `.candidate` remains **pre-quality**. Keep the result as well as the candidate. Derived samples do not inherit untransformed natural-flow uncertainty bounds. They retain their original reference sample as a component, while the result retains donor uncertainty. Quantitative output uncertainty is unavailable until separately supported. Apply supported local quality and receptor constraints, repeat physical/quality tests, then check the final natural floor invariant. This operator does not claim those checks passed. It does not impose the baseline-only duration gate; separately commissioned transfer safeguards remain application inputs.

## Calculate only a presumptive floor

`fishy.presumptive_floor.presumptive_floor(reference, profile)` multiplies an accepted present-climate `DailyPattern` by supplied seasonal fractions. The profile names the reference convention and binds its exact identity with `presumptive_reference_identity`. A reference at a chosen design probability is one supported convention, not a prescribed denominator.

`SeasonalFraction` uses explicit `[start_day, end_day)` offsets in that reference's accounting year. Seasons must cover every day once. This supports arbitrary fixed-day boundaries, including leap years. Fractions lie in [0, 1]. Their adoption or hypothetical scenario basis and uncertainty remain explicit.

The result has daily base-floor samples, not a regime, full requirement or new delivery obligation. Active local quality must survive later floor assembly. Missing reference, acceptance or season coverage returns no floor, not an invented zero. Supported zero remains a value. Existing independent duties are unaffected.

## Run a complete synthetic example

```bash
uv run python examples/ecological_transfer.py
```

The example supplies complete calendars and exact annual/daily acceptance records under stipulated synthetic evidence. It prints transferred first-day values 3 and 5 m³/s, then a hypothetical seasonal floor and a missing-reference result. It does not certify a basin or establish official admissibility.

`tests/test_ecological_transfer.py` exercises U6 transfer arithmetic, zero denominators, unsupported identities/calendars, ratio-versus-volume mapping, qualification failures, chains/cycles, leap-year coverage, presumptive missing inputs and fallback-route recomputation. Exact rational witnesses use zero tolerance.

Source meaning: the owner-selected 19 September 2026 handover, Appendix A step 7 fallback and D.10 `sec-donor-transfer`. The source supplies no accepted donor list or adopted presumptive schedule. Local composition, scientific application acceptance and competent decisions remain separate.
