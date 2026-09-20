# Project domain context

## Canonical terms

| Term | Meaning |
|---|---|
| Denotation line | A one-line statement, recorded in a module's docstring before implementation, of what the module computes as a mathematical object. Carriers must be named domain types; if the line cannot be written, the design is not ready. |
| Composition root | The single entry point where config is read, paths are resolved, raw input is parsed into domain types, and authority is granted. All other modules receive what they need as arguments and never self-configure. |
| Domain type | A `NewType`, frozen dataclass, or enum encoding a domain concept that carries an invariant or unit ambiguity. Domain types are constructed once at the composition root; bulk numerical data remains in library-native carriers. |
| Non-obviousness criterion | The admission test for a rule in `AGENTS.md`: it belongs only if it encodes an arbitrary project choice a model cannot infer or a practice that default model output violates. Tool-enforced and readily inferred practices are excluded. |
| Repository inventory | The deterministic, path-ordered records produced after Git-worktree discovery and linked-worktree de-duplication, pairing each selected repository with its instruction layout. It is discovery output, never an owner or repository allowlist. |
| Instruction layout | Exactly one structural classification of a repository's root instruction files: exactly one well-formed doctrine block, `AGENTS.md`-only markerless, substantive duplicated `AGENTS.md`/`CLAUDE.md` pair, `CLAUDE.md`-only, no instruction file, or malformed/ambiguous. It excludes doctrine status. |
| Doctrine status | The read-only comparison of one eligible `AGENTS.md` target with pyplate's source doctrine: `CURRENT`, `STALE`, `LOCALLY_EDITED`, or `UNSTAMPED`. Missing, malformed, ambiguous, unsupported-layout, and operational-error results remain explicit non-clean fleet results rather than doctrine statuses. |
| Fleet doctrine check | The discovery-driven, path-ordered application of doctrine checking to every repository inventory record, with one isolated result per repository and a clean aggregate only when every result is `CURRENT`. |
| Fleet doctrine sync | The discovery-driven, path-ordered application of `sync_doctrine` only to repositories with one unambiguous, well-formed, content-stamped `AGENTS.md` block. Every other layout is an explicit non-writing result; the aggregate is clean only when every result is `UPDATED` or `UNCHANGED`. |
| Controlled retrofit | The snapshot-gated operation that resolves an explicitly approved repository set from repository inventory, transforms only authorized instruction paths in detached worktrees based on fetched `origin/main`, verifies doctrine synchronization, and publishes through an explicit landing mode. |
| Pre-retrofit snapshot | The private, complete record of resolved repository identities and live-checkout state captured before retrofit commits; it gates controlled retrofit without granting write authority and is never committed. |

## Aliases to avoid

| Avoid | Use instead | Why |
|---|---|---|
| equation, type signature, summary line | Denotation line | These aliases omit the requirement that the line state the module's mathematical object before implementation. |
| setup code, wiring layer, boundary layer | Composition root | These aliases obscure that there is one authority-granting entry point. |
| wrapper class, validated dict | Domain type | These aliases do not guarantee that invalid states are unrepresentable after parsing. |
| non-obvious rule, style guide entry | Non-obviousness criterion | These aliases confuse the admission test with the rules it admits. |
| fleet list, repository registry | Repository inventory | These aliases imply an authored allowlist instead of discovered output. |
| doctrine status, sync status | Instruction layout | These aliases conflate file structure with downstream freshness or sync results. |
| layout, inventory result | Doctrine status | These aliases conflate an eligible target's content comparison with repository discovery and structural classification. |
| repository loop | Fleet doctrine check or fleet doctrine sync | This alias omits discovery, deterministic ordering, per-repository isolation, and aggregate cleanliness. |
| batch sync | Fleet doctrine sync | This alias omits layout-gated write eligibility and explicit non-writing refusals. |

## Relationships

| Concepts | Relationship |
|---|---|
| Composition root and domain type | The composition root parses raw boundary values into domain types before passing authority downstream. |
| Repository inventory and instruction layout | A repository inventory pairs each de-duplicated discovered Git repository with exactly one instruction layout. |
| Instruction layout and doctrine status | Instruction layout is determined first and contains no doctrine-status determination; downstream checking may determine doctrine status only for eligible layouts. |
| Repository inventory and fleet doctrine check | The fleet doctrine check consumes the discovered repository inventory and enriches each record without changing discovery or layout classification. |
| Fleet doctrine check and doctrine status | The fleet doctrine check delegates eligible targets to `check_doctrine`; every other layout receives an explicit non-clean result without guessing a target or changing a repository. |
| Repository inventory and fleet doctrine sync | Fleet doctrine sync consumes the discovered repository inventory without replacing it with an owner or repository allowlist. |
| Fleet doctrine sync and instruction layout | Fleet doctrine sync delegates only the exactly-one-well-formed-block layout to `sync_doctrine`; markerless, missing, duplicated, `CLAUDE.md`-only, and malformed or ambiguous layouts are never written. |
| Controlled retrofit and repository inventory | Controlled retrofit resolves every approved exact repository basename against the de-duplicated repository inventory before any fetch or write. |
| Controlled retrofit and pre-retrofit snapshot | Controlled retrofit requires the pre-retrofit snapshot to match the complete resolved identity set and each target's tracked live state before processing. |
| Controlled retrofit and fleet doctrine sync | Controlled retrofit supplies markerless insertion and landing orchestration, then delegates doctrine checking and repeat synchronization verification to fleet doctrine sync primitives. |

## Ambiguities

| Topic | Current interpretation | Resolution condition |
|---|---|---|
