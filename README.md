# Goalkeeper

[![CI](https://github.com/robzilla1738/goalkeeper/actions/workflows/ci.yml/badge.svg)](https://github.com/robzilla1738/goalkeeper/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

**An evidence-first control plane for agentic work.**

> **Don't let agents claim done. Make them prove it.**

Goalkeeper turns a vague goal into a bounded **contract**, lets an agent work
inside that contract, and refuses to call the work done until there is
**evidence** — gated by the best available verifier: deterministic, external,
rubric, or human. It sits above the host's first-party `/goal`, hooks, skills,
and subagents.

Coding is the first wedge because software has unusually good proof surfaces
(tests, type checks, diffs, file scope, CI, grep checks). But the contract engine
is **domain-neutral**, with adapters for research, writing, and ops.

> **Contract, don't vibe.** Don't build a raw infinite-loop wrapper — both Codex
> and Claude Code already have first-party continuation. The winning layer is a
> contract system that makes long-running work **measurable, bounded, and
> auditable**, then **gates completion on proof**.

---

## The promise, honestly

Goalkeeper does **not** claim to automatically prove any goal is done. It
**defines what proof means** for the goal, **records the evidence**, and **gates
completion** according to the best available verifier — and it always shows you
the **completion tier (0–6)** so confidence is never faked.

```
Contract → Work → Evidence → Verification → Audit → Accept / Review
```

## What's inside

- **Goalkeeper Core** (`goalkeeper_core/`) — domain-neutral, dependency-free
  (Python 3 stdlib): the Universal Goal Contract v2, a **validator registry**
  (command · git_diff · file · http · github · ticket · sql · rubric ·
  human_approval), **verifier tiers (0–6)**, a real **completion gate**, **proof
  bundles**, **bounded run-output artifacts**, **risk/approval gates**, **loop
  modes**, and **subagent packets**.
- **Adapters** (`goalkeeper_core/adapters/`) — `code`, `research`, `writing`,
  `ops`; selected by `goal.domain`.
- **Hosts** (`hosts/`) — `claude` and `codex` plugins (skills, agents, hooks), a
  **GitHub Actions** gate + PR-comment workflow, and a bare-`shell` entrypoint.
- **Schema** (`schema/goalkeeper.contract.schema.json`) and a stdlib
  `validate-contract`.

## How it works (one diagram)

```
/goalkeeper "Refactor auth…"            ← a skill (instructions)
        │  the model runs the goalkeeper CLI to write the v2 contract
  .goalkeeper/  →  state.json (canonical) · goal.md (generated) · runs.jsonl · proof.md
        │  goalkeeper doctor (gate) → render --format prompt
  /goal <objective + scope + proof + constraints>   ← primary host workflow
        │  the host works the goal; hooks inject the contract and block
        │  obvious destructive / out-of-scope shell commands
        ▼
  goalkeeper run → goalkeeper gate → complete → proof   (PASS only with evidence)
```

Goalkeeper's primary integration is native `/goal`: it renders a prompt the host
can run, then verifies completion independently. It does **not** depend on a
separate `/loop` command. Optional Stop-hook auto-continue can ask the host to
continue while gate blockers remain, but it is off by default and bounded by the
contract's turn budget. See [`/goal` and continuation](./docs/concepts/GOAL_AND_LOOP.md).

## Quick start

```bash
# in a target git repo
python3 /path/to/goalkeeper/bin/goalkeeper init --auto -o "Refactor auth to the new token API while preserving behavior"
python3 /path/to/goalkeeper/bin/goalkeeper status
python3 /path/to/goalkeeper/bin/goalkeeper render --format prompt   # paste into /goal
python3 /path/to/goalkeeper/bin/goalkeeper run "<required validator command>"
python3 /path/to/goalkeeper/bin/goalkeeper checkpoint --id cp1 --evidence "validators passed and diff reviewed" --met
python3 /path/to/goalkeeper/bin/goalkeeper gate                     # exit 0 only when complete
python3 /path/to/goalkeeper/bin/goalkeeper complete --accepted-by you
python3 /path/to/goalkeeper/bin/goalkeeper proof
```

If work already started before Goalkeeper was initialized, use
`goalkeeper adopt -o "Finish the current change"` to scope the contract around
the current git diff. For local setup, `goalkeeper install all --dry-run` shows
the shell/Claude/Codex symlinks it would create, and `goalkeeper smoke core`
proves the end-to-end gate flow in a disposable repo.

**As a Claude Code plugin:** `claude --plugin-dir ./hosts/claude` then
`/goalkeeper Refactor the auth module…`. **As a Codex plugin:** see
[`hosts/codex`](./hosts/codex). **In CI:** see
[`hosts/github-actions`](./hosts/github-actions).

## Documentation

- [Architecture](./docs/concepts/ARCHITECTURE.md) · [`/goal` and continuation](./docs/concepts/GOAL_AND_LOOP.md) · [Goal Contract v2](./docs/concepts/GOAL_CONTRACT.md)
- [Verifier tiers](./docs/concepts/VERIFIER_TIERS.md) · [Loop modes](./docs/concepts/LOOP_MODES.md)
- [Contract schema reference](./docs/schemas/CONTRACT_V2.md) · [Writing an adapter](./docs/adapters/WRITING_AN_ADAPTER.md)
- [Risk & approvals](./docs/security/RISK_AND_APPROVALS.md) · [CLI](./docs/CLI.md) · [Hooks](./docs/HOOKS.md)
- Playbooks: [code refactor](./docs/real-world-playbooks/code-refactor.md), [recurring maintenance](./docs/real-world-playbooks/recurring-maintenance.md)
- Examples: [`examples/`](./examples) (runnable v2 contracts)

## Status

Goalkeeper Core, the hook, host wiring, installer, and smoke path are covered by a
57-test `pytest` suite running in CI on Python 3.9–3.12 (zero runtime
dependencies). The plugins still need long live Claude/Codex sessions before
claiming production maturity, but local hook execution and isolated proof flows
are now testable with `goalkeeper host doctor` and `goalkeeper smoke`.

## License

MIT © Robert Courson — see [LICENSE](./LICENSE).
