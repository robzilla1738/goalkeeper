# Goalkeeper — Claude Code host

The Claude Code plugin package: skills, agents, hooks. It calls the shared
`goalkeeper_core` engine through `bin/goalkeeper` (a thin bootstrap that locates
the package — no install step).

## Install (local)

```bash
claude --plugin-dir ./hosts/claude
/goalkeeper Refactor the auth module to the new token API while preserving behavior and passing tests.
```

Plugin skills are namespaced `/<plugin>:<skill>` (e.g. `/goalkeeper:goalkeeper`);
the model can also auto-invoke from a skill's `description`. `/goal` requires
Claude Code **v2.1.139+**.

> The bootstrap finds `goalkeeper_core` by walking up from `bin/` to the repo root,
> or via `GOALKEEPER_CORE_HOME`. When using `--plugin-dir ./hosts/claude` from a
> clone this works out of the box; for a vendored/copied install, set
> `GOALKEEPER_CORE_HOME` to wherever `goalkeeper_core/` lives.

## Contents

- **Skills** — `goalkeeper` (author a v2 contract + emit `/goal`), `goalkeeper-split`
  (disjoint subagent packets), `goalkeeper-audit` (verify + gate before "done").
- **Agents** — `goalkeeper-researcher` (read-only), `goalkeeper-implementer`
  (scoped write), `goalkeeper-verifier` (read-only).
- **Hooks** — `hooks/hooks.json` wires `bin/goalkeeper_hook.py`: contract injection,
  destructive/forbidden command blocking, and a gate-aware Stop (off by default).

## Workflow

`init --auto` or `adopt` → `doctor` → `render --format prompt` → `/goal` →
`run`/`checkpoint` (record proof) → `gate` → `complete --accepted-by` → `proof`.

Goalkeeper is not a replacement for Claude Code continuation. It generates the
contract and `/goal` handoff, then verifies the result. Stop-hook
auto-continue is optional and off by default. See
[`/goal` and continuation](../../docs/concepts/GOAL_AND_LOOP.md).
