---
name: goalkeeper-split
description: >
  Turn the active Goal Contract into safe, non-overlapping subagent packets so
  parallel agents never edit the same files or wander into unrelated cleanup.
  Use only when parallel or specialized work genuinely helps (noisy research,
  read-heavy investigation, independent file groups). Generates ready-to-paste
  Claude Code and Codex prompts per packet into .goalkeeper/agent_packets.md.
  Trigger via /goalkeeper-split or when the user asks to parallelize work.
---

# Goalkeeper Split — safe subagent packets

You convert one Goal Contract into a small set of **tightly-scoped packets**.
The whole point is to prevent the classic multi-agent failure modes: two agents
editing the same files, or an agent drifting into unrelated refactors.

Subagents are useful but costly — they run in separate contexts and detailed
results consume real context budget. Only split when it actually pays off.

## When NOT to split
- The work is sequential or small.
- Packets would share editable files.
- A single `/goal` run would be simpler. (Say so and stop.)

## Workflow

### 1. Load the contract
```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" status
```
Read `.goalkeeper/goal.md` for full scope and constraints.

### 2. Partition by disjoint editable paths
Carve the allowed scope into packets whose **write sets do not overlap**.
Classify each packet:
- **researcher (read-only)** — investigate, summarize; edits nothing.
- **implementer (write)** — owns an exclusive set of paths.
- **verifier (read-only)** — re-runs validations, audits a packet's output.

Each packet must declare:
- `id`, `role`, `objective`
- `allowed_paths` (exclusive for implementers)
- `forbidden_paths/actions` (inherited from the contract)
- `validation` it must satisfy
- `done` definition + evidence to produce

### 3. Generate ready-to-paste prompts
Append each packet to `.goalkeeper/agent_packets.md` in this shape, producing
both a Claude Code Task/subagent prompt and a Codex agent prompt:

```
## Packet P1 — implementer
Role: implementer (write)
Allowed paths: src/auth/token/**
Forbidden: do not change public API; do not touch src/routes/**
Objective: replace legacy token verify with new API in token module
Validation: npm test -- tests/auth/token exits 0
Done: validation passes; evidence appended to work_log.md

--- Claude Code subagent prompt ---
You are a scoped implementer. Work ONLY in src/auth/token/**. Do not edit any
other path. Objective: <...>. When done, run `npm test -- tests/auth/token`,
record the exit code and key output to .goalkeeper/work_log.md, and stop. If you
need to change a file outside your allowed paths, STOP and report instead.

--- Codex agent prompt ---
<same, phrased for Codex; reference .codex/agents custom agent if used>
```

For read-only researchers, the prompt must explicitly forbid edits and ask for
a concise findings summary (to limit context blow-up).

### 4. Hand-off guidance
- Run implementer packets that have disjoint paths in parallel; run researchers
  first if implementers depend on their findings.
- After packets complete, run **goalkeeper-audit** to verify the combined diff
  against the contract.
- In Claude Code, launch packets as subagents/Tasks. In Codex, copy the example
  custom agents from `codex-agents/` into `.codex/agents/` and invoke them.

## Guardrails
- No two implementer packets may share an editable path. If you cannot make
  write sets disjoint, do not split — recommend sequential work.
- Researchers and verifiers are strictly read-only.
- Every packet inherits the contract's forbidden paths/actions and stop budget.
