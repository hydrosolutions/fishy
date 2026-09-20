# ADR-0001: Doctrine lives in the template and propagates by sync

## Status

Accepted

## Context

The design doctrine (§2, and the language-neutral parts of testing and documentation) is authored once but must hold in every project started from `pyplate` or `rustplate`. Today it is copied at project creation and never updated again. The cost is measurable: `orthographos` and `temenos` still mandate a version bump on every commit, a rule the templates removed in `ecf38ef`, because nothing told them. `orthographos` and `temenos` additionally carry an 8.8 KB `CLAUDE.md` that duplicates their `AGENTS.md`, so two overlapping instruction files load every session.

Three ways to propagate were considered.

*Symlink `AGENTS.md` into a shared file.* Rejected: git commits the symlink itself, so any clone without the target — a colleague, CI, a container, a cloud agent — reads an empty file rather than an error. It is also all-or-nothing per file, and cannot combine shared doctrine with project-local content.

*Keep the doctrine in `~/.claude/CLAUDE.md`.* Rejected: colleagues start projects from these templates, and a home-directory file is invisible to them, to CI, and to agents running outside this machine. Their projects would have no design guidance at all, and the absence would be silent.

*Vendor the doctrine into each project inside a delimited, version-marked block, refreshed by a sync script.* Chosen.

## Decision

The template repository is the single source of truth for the doctrine. Each project's `AGENTS.md` carries the doctrine verbatim inside an explicitly delimited block stamped with the template version it came from. Everything outside that block is gotchas — rules true of that project alone.

A project does not edit its own doctrine block. Changing the doctrine means changing the template and syncing. A sync script, shipped in the template and not removed by `init.sh`, refreshes the block from the template and, in `--check` mode, reports drift without writing. Sync refuses to overwrite a block that has been locally modified, reporting the conflict instead.

Repositories remain self-contained: the doctrine is readable in a fresh clone with no network and no home directory.

## Consequences

Every project stays readable standalone, which is what colleagues, CI, and cloud agents require. Drift becomes visible — the version marker is legible without running anything, and `--check` names it precisely.

Drift is not eliminated, only made detectable and cheap to fix; a project that never runs sync still goes stale, silently in behaviour if not in appearance. The doctrine is duplicated across every repository by design, so a doctrine change is not instantaneous anywhere.

Follow-up obligations: every existing project must be retrofitted, or it will contradict the template while appearing to agree with it. The fleet is larger than the projects surveyed when this was written, so retrofit begins with discovery rather than a fixed list, and sync must be runnable across many repositories in one pass. `orthographos` and `temenos` must lose their duplicate `CLAUDE.md`. Version bumping is removed everywhere: it is a doctrine decision, not a project one, and no repository keeps it as a gotcha.
