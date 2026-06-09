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

**Skills:** `goalkeeper` (author a v2 contract and emit `/goal`),
`goalkeeper-split` (disjoint subagent packets), `goalkeeper-audit` (verify and
gate before "done").

**Agents:** `goalkeeper-researcher` (read-only), `goalkeeper-implementer`
(scoped write), `goalkeeper-verifier` (read-only).

**Hooks** (`hooks/hooks.json` wires `bin/goalkeeper_hook.py`): contract
injection, destructive/forbidden command blocking, write-boundary scope denial
on `Edit`/`Write`, `PostToolUse` evidence capture, and a gate-aware `Stop` that
enforces by default for gated contracts. Kill switch: `goalkeeper autocontinue
off` or `GOALKEEPER_NO_STOP=1`.

## Workflow

`init --auto` or `adopt` → `doctor` → `render --format prompt` → `/goal` →
`run`/`checkpoint` (record proof) → `gate` → `complete --accepted-by` → `proof`.

Goalkeeper writes the contract and the `/goal` handoff, then makes "done"
non-bypassable: for an enforced contract the Stop hook holds the turn open until
the gate passes, then records completion and the proof bundle automatically (or
pauses for a named human). See [`/goal` and continuation](../../docs/concepts/GOAL_AND_LOOP.md).
