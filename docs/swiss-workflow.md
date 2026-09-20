# Swiss residual-flow workflow

Fishy calculates and assesses a supplied Swiss scenario without Taqsim or HYDMOD.
It does not issue a permit, choose a cantonal judgement or authenticate evidence.

```sh
uv sync --locked
uv run python examples/swiss_prescription.py
```

The example uses original synthetic inputs. It produces these exact values:

| Stage | l/s |
|---|---:|
| Imported Art. 59 Q347 | 160 |
| Literal Art. 31(1) starting minimum | 130 |
| Supported Art. 31(2) safeguard total | 180 |
| Separately supplied Art. 33 final total | 220 |
| Supported Art. 35 intake prescription | 220 |
| Proven temporary inflow | 150 |
| Time-specific Art. 36 duty | 150 |
| Supplied delivery | 120 |
| Delivery shortfall | 30 |

The original 220 l/s prescription stays unchanged. With no supported inflow proof,
the duty stays 220 l/s and the same delivery has a 100 l/s shortfall. The example
labels all evidence and decisions as hypothetical. Its passing calculation checks
are not observed compliance or official approval.

## Prepare one scenario

1. Establish the applicable [permit route](swiss-permits.md). New or renewed
   permits differ from Arts. 80 ff. remediation. An existing prescribed duty can
   be assessed without reconstructing its historical sizing. Significant effects
   from lake or groundwater abstractions require analogous protection.
2. Calculate or import attributable [Q347 and the literal table](swiss-low-flow.md).
   Keep scientific adequacy, final-use verification and official admissibility
   separate. A table output at zero does not establish permanent-flow eligibility.
3. Supply [safeguard studies](swiss-safeguards.md) for every affected protection
   point and exact seasonal/event interval. Requirements are supported totals,
   not successive increments. Preserve selected measures and upper valid domains.
4. Where applicable, assess an explicitly supplied [Art. 32 exception](swiss-exceptions.md).
   Eligibility alone does not lower a requirement. A scoped authorised or labelled
   hypothetical decision is needed. Normal protection remains outside its extent
   and period.
5. Assess the separate [Art. 33 balancing decision](swiss-balancing.md), including
   after an exception. Its final total must retain the applicable minimum.
   Normal-route final candidates are rechecked against actual safeguard studies,
   not accepted from a previously passing summary.
6. Use [supported intake relationships and delivery proofs](swiss-delivery.md).
   The intake release and downstream residual need are different quantities.
   A topology map cannot supply a routing relationship. Each required protection
   point must have a supported mapping, including relevant sections below a return.
   Pass the actual balancing assessments so the shared intake candidate is
   projected to every point and the original site studies are checked again.
   The numerical mapping remains available separately if final scientific
   support is missing. The schedule is not an issued permission.

## Evidence boundaries

Use public scope builders when creating `EvidenceFindings`. They bind acceptance
to the reviewed quantities, physical points and input versions. A changed amount,
relationship, location, data version or scenario needs new findings. Frozen records
preserve earlier issued values. Scope digests identify inputs; they do not prove
that a source is authentic or a specialist judgement is true.

A supported failure remains a failure when another required check is missing.
Incomplete coverage cannot become a pass. Unsupported physical balances cannot
establish a prescription or low-inflow relief. Exact intervals are retained; daily
means do not become instantaneous or within-day proof.

Condition findings such as hydropeaking and seasonality remain linked to the same
reach and scenario, but separate from prescribed-release compliance. A condition
class does not change a duty or create a flow uplift. No HYDMOD installation is
needed to consume these supplied findings.

## Sources and test coverage

The method uses the German GSchG consolidation of 1 August 2025, GSchV consolidation
of 1 December 2025, and supporting FOEN 2000 *Wegleitung Restwassermengen*. The
amended Act controls; guide printed pages are two less than PDF/extraction pages.
The component documents above map source clauses to public operations and tests.

The full connected test is
`tests/test_swiss_prescription_example.py::test_complete_supported_swiss_scenario`.
The same file tests a duty with no historical sizing and configuration isolation.
The delivery suite tests gains/losses, failed balances, missing proof, differing
condition findings and unchanged nominal duties. All literal flow assertions use
exact rational arithmetic, with zero numerical tolerance.

```sh
uv run pytest tests/test_low_flow.py tests/test_swiss_*.py
uv run ruff check
uv run ty check
```

Optional physical compatibility uses the Taqsim and Incidence revisions pinned in
`pyproject.toml` and `uv.lock`. `uv run --extra taqsim pytest` tests those adapters;
the supplied Swiss path does not import them. Software tests do not certify site
ecological adequacy or legal currency.
