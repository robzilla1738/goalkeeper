---
name: goalkeeper-split
description: >
  Turn the active Goal Contract into safe, non-overlapping subagent packets so
  parallel agents never edit the same files or wander into unrelated cleanup.
  Uses `goalkeeper split` to partition allowed scope into disjoint write-sets and
  writes ready-to-paste prompts to .goalkeeper/agent_packets.md. Use only when
  parallel or specialized work genuinely helps. Trigger via /goalkeeper-split or
  when the user asks to parallelize.
---

# Goalkeeper Split — safe subagent packets

You convert one Goal Contract into a small set of **tightly-scoped packets** whose
**write sets do not overlap**, preventing the classic multi-agent failure modes
(two agents editing the same files, or drifting into unrelated refactors).

Subagents are useful but costly. Only split when it pays off.

Use `${GOALKEEPER_BIN:-goalkeeper}`; set `GOALKEEPER_BIN` to the absolute
Goalkeeper entrypoint if the CLI is not on `PATH`.

## When NOT to split
- The work is sequential or small.
- Packets would share editable files.
- A single `/goal` run would be simpler. (Say so and stop.)

## Workflow

### 1. Partition scope into disjoint packets
```
${GOALKEEPER_BIN:-goalkeeper} split --write-packets
${GOALKEEPER_BIN:-goalkeeper} packets list
```

`split` carves `scope.allowed_resources` into one implementer packet per resource
(disjoint by construction), inherits the contract's forbidden paths/actions, and
writes a ready-to-paste subagent prompt for each to `.goalkeeper/agent_packets.md`.
If any write-sets overlap, it warns — do **not** run those in parallel.

Classify additional packets by hand if useful: **researcher** (read-only),
**implementer** (exclusive write-set), **verifier** (read-only re-runs validators).

### 2. Run packets
```
${GOALKEEPER_BIN:-goalkeeper} packets run P1
```
Launch a Claude Code subagent/Task (or a Codex custom agent from
`hosts/codex/codex-agents/`) with the packet's prompt. Run researchers first if
implementers depend on their findings; run disjoint implementers in parallel.

### 3. Reconcile + audit
```
${GOALKEEPER_BIN:-goalkeeper} packets reconcile
```
`reconcile` checks the combined diff honored the disjoint write-sets and flags any
changed file not owned by a packet. Then run **goalkeeper-audit** and `goalkeeper
gate` on the combined result.

## Guardrails
- No two implementer packets may share an editable path. If you cannot make write
  sets disjoint, do not split — recommend sequential work.
- Researchers and verifiers are strictly read-only.
- Parallel packets are experimental: `reconcile` is the safety net, not a lock.
