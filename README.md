# Fishy

Fishy assesses environmental water duties and hydrological evidence. Supply an
identified requirement and matched observations or physical results. Fishy reports
shortfalls without changing the duty or creating water demands.

## Start with a supplied duty

Python 3.13 or later and [uv](https://docs.astral.sh/uv/) are required.

```sh
git clone https://github.com/hydrosolutions/fishy.git
cd fishy
uv sync --locked
uv run python examples/supplied_duty.py
```

The example compares daily duties `[2, 3]` with deliveries `[1.5, 3.5]` m³/s.
It returns shortfalls `[0.5, 0]` and **43,200 m³**. Later surplus does not cancel
an earlier shortfall. No simulator is needed for observation or imported inputs.

The public modules separate stable responsibilities:

- `fishy.spatial`: prepared water-body, reach, section, point and model mappings;
  independent plan assignment; explained natural/potential track decisions.
- `fishy.evidence`: immutable source versions, separate evidence findings and
  required-check aggregation. Unknown required checks cannot become a pass.
- `fishy.time`, `fishy.quantities`: exact intervals and unit-bearing quantities.
- `fishy.flows`: located observations/imports, volume-preserving aggregation and
  `daily_discharge` for dated diagnostics.
- `fishy.duties`: independently supplied obligations, delivery shortfalls and
  deliverability checks. Requirements, floors and issued obligations stay distinct.
- `fishy.physical`: optional explicit Taqsim physical-result exchange.
- `fishy.diagnostics`: source-defined IHA and IARI on identified dated flows.
  See [flow diagnostics](docs/flow-diagnostics.md) for profiles and an executable example.

## Use Taqsim results

```sh
uv sync --locked --extra taqsim
uv run --extra taqsim python examples/taqsim_delivery.py
```

Choose incoming water at an outlet or arrival point, or outgoing reach transfers.
Do not use stored inventory as interval flow. Declare how the model's naive clock
is interpreted. The adapter converts interval volumes using actual elapsed time;
it does not invent finer-resolution observations. Live and saved physical
projections use the same boundary. Saved projections are not restart checkpoints.

Compatible source revisions are locked:

| Component | Git revision |
|---|---|
| Taqsim | `396ad093c2b6f240e702a3b05aee1fb96a69b3f7` |
| Incidence | `665da4e0d81ab28921b8d5d2edbb9be27f4ec612` |

## Assess quality and conservative feasibility

```sh
uv run python examples/imported_quality.py
uv run --extra taqsim python examples/taqsim_quality.py --save mixed.taqsim
```

Configure individual, group, range or relative-reference targets. Imported evidence
works without Taqsim. A fixed conservative boundary returns the full feasible
arrival interval, including upper bounds and strict endpoints. Source-control,
local/basin accounting and five-condition activation remain separate operations.
The 456 catalogue records and eight seed rules stay inactive until explicitly
selected and qualified. See [quality operations and limits](docs/quality.md) and
[executed acceptance crosswalk](docs/quality-acceptance.md).

## Meaning and limits

Present zero, missing, absent, outside-horizon and unsupported evidence remain
separate. Numerical shortfall is not a legal-compliance or responsibility finding.
Uncertainty, scientific adequacy and official admissibility require their own
supplied evidence. A daily mean cannot certify unseen within-day conditions.

A missing basin-plan assignment does not block a supported reach calculation.
Scenario changes do not rewrite source profiles or issued duty versions. The
library does not infer national methods, choose policy, reconstruct natural flow,
or run an all-method orchestrator. Quality-limit findings do not issue duties. Route-specific
issuance rules remain separate.

See [assessment contracts and executed crosswalk](docs/assessment.md).

## Development

```sh
uv run --all-extras pytest
uv run --all-extras ruff format --check
uv run --all-extras ruff check
uv run --all-extras ty check
```

Synthetic tests establish software behavior, not basin scientific certification.
