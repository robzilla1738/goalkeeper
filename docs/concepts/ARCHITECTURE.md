# Architecture

Goalkeeper is an **evidence-first control plane for agentic work**. It turns a
vague goal into a bounded **contract**, lets an agent work inside that contract,
and refuses to call the work done until there is **evidence** — gated by the best
available verifier: deterministic, external, rubric, or human.

Guiding principle: **the LLM decides, deterministic code verifies.** "Done" is
never the agent's word — it is an exit code, a clean diff, recorded evidence, and
(where required) a human signature.

## Three concentric layers

| Layer | Where | Role |
|-------|-------|------|
| **Goalkeeper Core** | `goalkeeper_core/` | Domain-neutral IP: contract schema, state machine, ledger, validator registry, verifier tiers, completion gate, proof bundles, loop policy, risk gates, packets. No LLM, stdlib only. |
| **Adapters** | `goalkeeper_core/adapters/` | Per-domain proof: `code`, `research`, `writing`, `ops`. Selected by `goal.domain`. Provide templates, expected validator types, and render/verify customization. |
| **Hosts** | `hosts/` | Wiring into a runtime: `claude` (plugin), `codex` (plugin), `github-actions` (gate Action + workflow), `shell`. Skills/agents/hooks live here. |

The CLI entrypoint `bin/goalkeeper` and the hook `bin/goalkeeper_hook.py` are thin
bootstraps that put `goalkeeper_core` on `sys.path` (no install step) and dispatch.
Both the CLI and the hook import the *same* Core, so gate/loop/contract logic is
written once and shared.

## The pipeline

```
Contract → Work → Evidence → Verification → Audit → Accept / Review
```

```
  goalkeeper init --auto …        (capture base_ref, detect validators/scope)
  goalkeeper adopt …              (alternative: scope a contract around current diff)
  goalkeeper set / checkpoint …   (shape scope, validators, risk, loop)
  goalkeeper doctor               (GATE: reject vague/invalid contracts)
  goalkeeper render --format prompt → /goal …      (hand to the host loop)
        │  host loops the agent; the hook injects the contract + blocks bad cmds
        ▼
  goalkeeper run "<validation>"   (records exit/duration + bounded output artifacts)
  goalkeeper checkpoint --met …   (records evidence)
  goalkeeper approve … --by …     (records human/risk approvals)
        ▼
  goalkeeper gate                 (exit 0 only when complete; computes tier)
  goalkeeper complete --accepted-by …   (only writer of status=complete)
  goalkeeper proof                (shareable audit artifact)
```

## State files (project-local under `.goalkeeper/`)

| File | Writer | Reader | Purpose |
|------|--------|--------|---------|
| `state.json` | CLI | CLI, hook | **Canonical** Universal Goal Contract v2 + runtime bookkeeping |
| `goal.md` | CLI (`render`) | humans, agent | **Generated** view of the contract — never hand-edited (kills drift) |
| `work_log.md` | CLI (`log`/`run`/`checkpoint`) | humans, agent | Evidence ledger + parking lot |
| `runs.jsonl` | CLI (`run`) | CLI (gate/score) | Authoritative validation command ledger: command, exit, duration, artifact refs |
| `events.jsonl` | hook | humans | Append-only hook event log |
| `agent_packets.md` | CLI (`split`) | humans, subagents | Per-packet scoped prompts |
| `proof.md` / `proof.json` | CLI (`proof`/`complete`) | humans, CI | Shareable audit bundle |
| `artifacts/` | CLI (`run`/`proof`) | humans | Captured stdout/stderr and other artifacts referenced by the proof |

## What changed from v1 (and why)

- **Verification now blocks completion.** `gate` is the single arbiter; `complete`
  is the only writer of `status=complete` and only succeeds after `gate` passes.
- **Contract quality is part of the gate.** An empty, draft, unscoped, or
  validator-free contract cannot pass by skipping `doctor`.
- **Useful contracts can be bootstrapped from reality.** `init --auto` detects
  package-manager test commands, Python/Rust/Go validators, likely scope, and a
  safe fallback validator; `adopt` scopes around the current git diff.
- **Local host readiness is testable.** `install`, `host doctor`, and `smoke`
  expose shell/Claude/Codex wiring problems before relying on a long agent run.
- **state.json is canonical; goal.md is rendered** — the v1 drift is gone.
- **The contract is domain-neutral.** Code is the first wedge; research/writing/ops
  are adapters.
- **Validators are typed**, not just shell commands (`command`, `git_diff`,
  `file_exists`, `file_contains`, `http_check`, `github_check`, `ticket_state`,
  `sql_query`, `rubric`, `human_approval`).
- **Completion is graded** on a 0–6 verifier-tier ladder, always displayed.

## Known limitations

- **Command blocking is a seatbelt, not a sandbox.** Best-effort regex on the shell
  string; use host permission/sandbox modes for real isolation.
- **External validators are deferred.** `http_check` is opt-in (`GOALKEEPER_ALLOW_NET=1`);
  `github_check`/`ticket_state`/`sql_query` mark themselves unavailable and require
  manually-supplied evidence rather than importing third-party drivers.
- **Parallel packets are experimental.** `packets reconcile` is the safety net for
  overlapping write-sets, not a lock.
- **Live host behavior still needs real-session proof.** Isolated hook execution is
  covered by smoke tests, but skill invocation and Stop-hook continuation can still
  vary by Claude/Codex host version.
