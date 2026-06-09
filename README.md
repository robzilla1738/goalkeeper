# Goalkeeper

[![CI](https://github.com/robzilla1738/goalkeeper/actions/workflows/ci.yml/badge.svg)](https://github.com/robzilla1738/goalkeeper/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

**An evidence-first control plane for agentic work.**

> **Don't let agents claim done. Make them prove it.**

Goalkeeper turns a vague goal into a bounded contract, lets an agent work inside
it, and refuses to call the work done until there's proof. Proof is whatever the
best available verifier can give you: a passing test, a clean diff, an external
check, a human signing off. It runs on top of the host's own `/goal`, hooks,
skills, and subagents rather than replacing them.

Coding came first because software is easy to check: tests pass or fail, a diff
is in scope or it isn't, CI is green or red. The contract engine itself is
domain-neutral, though, with adapters for research, writing, and ops.

> **Contract, don't vibe.** Don't build a raw infinite-loop wrapper. Codex and
> Claude Code already have first-party continuation. The piece that's actually
> missing is a contract system that makes long-running work measurable, bounded,
> and auditable, then gates completion on proof.

---

## The promise, honestly

Goalkeeper does not claim it can automatically prove any goal is done. What it
does: define what proof means for that goal, record the evidence as the work
happens, and gate completion on the best verifier available. It always shows the
completion tier (0–6), so nobody gets to fake confidence.

```
Contract → Work → Evidence → Verification → Audit → Accept / Review
```

## What's inside

- **Goalkeeper Core** (`goalkeeper_core/`) is domain-neutral and dependency-free
  (Python 3 stdlib only): the Universal Goal Contract v2, a validator registry
  (command, git_diff, file, http, github, ticket, sql, rubric, human_approval),
  verifier tiers 0–6, the completion gate, proof bundles, bounded run-output
  artifacts, risk/approval gates, loop modes, and subagent packets.
- **Adapters** (`goalkeeper_core/adapters/`): `code`, `research`, `writing`,
  `ops`, picked by `goal.domain`.
- **Hosts** (`hosts/`): `claude` and `codex` plugins (skills, agents, hooks), an
  MCP server, a GitHub Actions gate + PR-comment workflow, and a bare `shell`
  entrypoint.
- **Schema** (`schema/goalkeeper.contract.schema.json`) plus a stdlib
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

Goalkeeper renders a native `/goal` prompt the host runs, then verifies
completion on its own. It does not need a separate `/loop` command. The hooks are
what make "done" non-bypassable: for an enforced contract (templates and
`init --auto` switch this on) the **Stop** hook holds the turn open, bounded by
the contract's turn budget, until the gate passes. Then it records completion and
the proof bundle automatically, or pauses for a named human if the contract calls
for one. Writes outside scope get denied at the boundary (`Edit`/`Write`, and
Codex `apply_patch`), and commands run during the turn are auto-recorded as
evidence. Turn it all off with `goalkeeper autocontinue off` or
`GOALKEEPER_NO_STOP=1`. See [`/goal` and continuation](./docs/concepts/GOAL_AND_LOOP.md).

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

Already started a change before initializing Goalkeeper? Run
`goalkeeper adopt -o "Finish the current change"` to scope the contract around
your current git diff. For local setup, `goalkeeper install all --dry-run` shows
the shell/Claude/Codex symlinks it would create, and `goalkeeper smoke core`
runs the whole gate flow in a throwaway repo.

**As a Claude Code plugin:** `claude --plugin-dir ./hosts/claude`, then
`/goalkeeper Refactor the auth module…`. **As a Codex plugin:** see
[`hosts/codex`](./hosts/codex). **As MCP tools (either host):** see
[`hosts/mcp`](./hosts/mcp). **In CI:** see
[`hosts/github-actions`](./hosts/github-actions).

## Documentation

- [Architecture](./docs/concepts/ARCHITECTURE.md) · [`/goal` and continuation](./docs/concepts/GOAL_AND_LOOP.md) · [Goal Contract v2](./docs/concepts/GOAL_CONTRACT.md)
- [Verifier tiers](./docs/concepts/VERIFIER_TIERS.md) · [Loop modes](./docs/concepts/LOOP_MODES.md)
- [Contract schema reference](./docs/schemas/CONTRACT_V2.md) · [Writing an adapter](./docs/adapters/WRITING_AN_ADAPTER.md)
- [Risk & approvals](./docs/security/RISK_AND_APPROVALS.md) · [CLI](./docs/CLI.md) · [Hooks](./docs/HOOKS.md)
- Playbooks: [code refactor](./docs/real-world-playbooks/code-refactor.md), [recurring maintenance](./docs/real-world-playbooks/recurring-maintenance.md)
- Examples: [`examples/`](./examples) (runnable v2 contracts)

## Status

Goalkeeper Core, the hook, host wiring, the MCP server, the installer, and the
smoke path are covered by a 76-test `pytest` suite that runs in CI on Python
3.9–3.12 with zero runtime dependencies. The in-process hook loop (enforce →
continue → auto-complete) is tested end to end. What's still unproven is a long
live Claude or Codex session driving the plugin skills turn after turn; on Codex
you also do the one-time `/hooks` trust first. Check local wiring with
`goalkeeper host doctor` and `goalkeeper smoke`.

## License

MIT © Robert Courson — see [LICENSE](./LICENSE).
