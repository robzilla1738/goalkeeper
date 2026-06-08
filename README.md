# Goalkeeper Loop

[![CI](https://github.com/robzilla1738/goalkeeper/actions/workflows/ci.yml/badge.svg)](https://github.com/robzilla1738/goalkeeper/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

A cross-compatible **Claude Code + Codex** plugin that adds a **Goal Contract →
verifier → ledger → subagent packet** layer on top of the first-party `/goal`,
hooks, skills, and subagents.

> **Contract, don't vibe.** The agentic-coding landscape is mature enough that
> you should *not* build a raw infinite-loop wrapper — both Codex and Claude
> Code already have first-party continuation primitives. The winning layer is a
> contract system that makes long-running work **measurable, bounded, and
> auditable**: define the objective, validation surface, allowed scope,
> constraints, and stopping condition *before* the agent runs.

The plugin lives in [`goalkeeper-loop/`](./goalkeeper-loop). Full reference docs
are in [`goalkeeper-loop/docs/`](./goalkeeper-loop/docs).

---

## What problem it solves

Long-running agentic tasks (refactors, migrations, research sweeps, multi-agent
work) fail in predictable ways: the agent declares "done" without proof, drifts
outside the intended files, wanders into unrelated cleanup, or loops forever.
Goalkeeper fixes this by separating **who decides** from **who verifies**:

- The **LLM decides** what to do, guided by a written Goal Contract.
- **Deterministic code verifies** the outcome — "done" means tests exit 0, the
  diff stayed in scope, and every checkpoint has evidence. Never the agent's word.

## How it works (in one diagram)

```
/goalkeeper-loop:goalkeeper "Refactor auth…"     ← a skill (instructions)
        │
        ▼  the model runs the `goalkeeper` CLI to write project state
  .goalkeeper/  →  goal.md · state.json · work_log.md · runs.jsonl · events.jsonl
        │
        ▼  goalkeeper doctor (gate) → generate-goal
  /goal <objective + scope + proof + constraints + stop-budget>   ← native loop
        │
        ▼  the host loops the agent; the hook injects the contract every turn
           and blocks destructive / out-of-scope commands
        ▼
  goalkeeper-audit → re-runs validations, scores the diff → PASS / REVIEW
```

See [docs/ARCHITECTURE.md](./goalkeeper-loop/docs/ARCHITECTURE.md) for the full walkthrough.

## Quick start

**Claude Code (local):**

```
claude --plugin-dir ./goalkeeper-loop
/goalkeeper-loop:goalkeeper Refactor the auth module to the new token API while preserving behavior and passing tests.
```

Plugin skills are namespaced as `/<plugin>:<skill>`; the model can also
auto-invoke from the skill description. `/goal` requires Claude Code **v2.1.139+**.

**Codex (local marketplace):**

```
mkdir -p ./plugins .agents/plugins
cp -R goalkeeper-loop ./plugins/goalkeeper-loop
cp goalkeeper-loop/examples/marketplace.json .agents/plugins/marketplace.json
# restart Codex, install from the local marketplace
codex features enable goals
$goalkeeper Refactor the auth module to the new token API while preserving behavior and passing tests.
```

Full install notes and Codex caveats: [goalkeeper-loop/README.md](./goalkeeper-loop/README.md).

## What's inside

- **3 skills** — `goalkeeper` (author a contract + generate `/goal`),
  `goalkeeper-split` (safe non-overlapping subagent packets), `goalkeeper-audit`
  (verify the diff against the contract).
- **A conservative cross-host hook** — injects the contract into every
  session/prompt/subagent, blocks destructive and out-of-scope `Bash` commands,
  logs events; optional bounded auto-continue (off by default).
- **A dependency-free `goalkeeper` CLI** —
  `init · status · set · detect · seed · doctor · generate-goal · checkpoint ·
  run · score · log · autocontinue`.
- **Agents** — Claude Code plugin agents (`agents/`) and Codex custom-agent TOML
  examples (`codex-agents/`): researcher (read-only), implementer (scoped),
  verifier (read-only).
- **Project-local state** under `.goalkeeper/`: `goal.md`, `state.json`,
  `work_log.md`, `agent_packets.md`, `events.jsonl`, `runs.jsonl`.

## Documentation

- [Architecture](./goalkeeper-loop/docs/ARCHITECTURE.md) — how the pieces fit together
- [The Goal Contract](./goalkeeper-loop/docs/GOAL_CONTRACT.md) — concept + `state.json` schema
- [CLI reference](./goalkeeper-loop/docs/CLI.md) — every command, flag, and exit code
- [Hooks reference](./goalkeeper-loop/docs/HOOKS.md) — events, JSON I/O, and security limits
- [Plugin README](./goalkeeper-loop/README.md) — install, workflow, Codex caveats
- [Contributing](./CONTRIBUTING.md) · [Changelog](./goalkeeper-loop/CHANGELOG.md) · [Security](./SECURITY.md)

## Status

Helpers and hook behavior are covered by a 33-test `pytest` suite running in CI
on Python 3.9–3.12. The plugin has **not** yet been exercised inside a live
Claude Code or Codex session — test it in a disposable repo before production use
(host hook-loading and skill invocation are environment-specific).

## License

MIT © Robert Courson — see [LICENSE](./LICENSE).
