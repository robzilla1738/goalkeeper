# Architecture

Goalkeeper Loop is a thin, opinionated layer **above** the host's native
continuation primitive (`/goal`). It does not loop the agent itself. Its job is
to turn a vague request into a precise, machine-checkable **Goal Contract**, keep
the agent inside that contract while the host loops it, and prove the result.

The guiding principle: **the LLM decides, deterministic code verifies.** "Done"
is never the agent's word — it is an exit code, a clean diff, and recorded
evidence.

## The three layers

| Layer | File(s) | Role | Contains logic? |
|-------|---------|------|-----------------|
| **Skills** | `skills/*/SKILL.md` | Instructions the model reads ("what to do") | No — orchestration prose |
| **CLI** | `bin/goalkeeper` | Deterministic state + verification ("source of truth") | Yes — plain Python, no LLM |
| **Hook** | `bin/goalkeeper_hook.py` + `hooks/hooks.json` | Automatic enforcement ("guardrails") | Yes — runs every turn |

Keeping these separate is the whole design. The model is free to be creative
about *how* to do the work; the CLI and hook make the *boundaries and proof*
non-negotiable and reproducible.

### 1. Skills — instructions

A `SKILL.md` is a markdown playbook the model loads when you invoke the skill
(`/goalkeeper-loop:goalkeeper` in Claude Code, `$goalkeeper` in Codex) or when
the host auto-selects it from the `description` frontmatter. Skills *orchestrate*
the CLI; they hold no logic themselves.

- **goalkeeper** — interview a messy request into objective / scope / validations
  / checkpoints, write `.goalkeeper/` state, gate on `doctor`, emit a `/goal`.
- **goalkeeper-split** — partition the contract into non-overlapping subagent
  packets (disjoint write-sets) and emit ready-to-paste prompts.
- **goalkeeper-audit** — re-run validations through `goalkeeper run`, `score` the
  diff, and return a PASS/REVIEW verdict with evidence.

### 2. The `goalkeeper` CLI — deterministic source of truth

Plain Python 3 stdlib, no dependencies, no LLM. The model shells out to it so
the consequential things are reproducible rather than improvised. Highlights:

- `init` captures a git `base_ref` (the diff baseline) and scaffolds state.
- `seed` / `detect` mine the repo (`package.json`, `AGENTS.md`, CI, …) for the
  *real* validation surface instead of guessing.
- `doctor` scores the contract itself — bounded objective? validations present?
  stop budget? — and acts as a gate before any work starts.
- `generate-goal` renders the contract into the native `/goal` string.
- `run "<cmd>"` executes a validation and records its exit code to `runs.jsonl`.
- `score` diffs the working tree against `base_ref` and cross-checks `runs.jsonl`
  to produce a PASS/REVIEW verdict.

Full reference: [CLI.md](./CLI.md).

### 3. The hook — automatic enforcement

`hooks/hooks.json` registers `bin/goalkeeper_hook.py` against host lifecycle
events. The host pipes a JSON event to the script on stdin; the script answers
with JSON on stdout. Every turn, the hook:

- **injects** the active contract as context (`SessionStart`, `UserPromptSubmit`,
  `SubagentStart`), so the agent and every subagent are constantly reminded of
  scope and constraints;
- **blocks** destructive or out-of-scope `Bash` commands (`PreToolUse`);
- optionally **continues** a bounded number of extra turns (`Stop`), only if
  explicitly enabled.

Full reference: [HOOKS.md](./HOOKS.md).

## Lifecycle

```
  invoke skill ──▶ goalkeeper init        (captures base_ref, writes state)
                   goalkeeper seed/detect  (mine real validations + policy)
                   …interview into contract; goalkeeper set / checkpoint …
                   goalkeeper doctor        (GATE: reject vague/unbounded contracts)
                   goalkeeper generate-goal (emit the native /goal string)
                        │
   you run  /goal ──────┘
                        │  host evaluator loops the agent turn-by-turn,
                        │  judging the condition from conversation evidence
                        ▼
                   (hook injects contract + blocks bad commands each turn)
                        ▼
                   goalkeeper run "<validation>"   (records exit codes)
                   goalkeeper checkpoint --met …   (records evidence)
                        ▼
                   goalkeeper-audit → goalkeeper score → PASS / REVIEW
```

## Data flow & state

All state is project-local under `.goalkeeper/` (git-ignored by default):

| File | Writer | Reader | Purpose |
|------|--------|--------|---------|
| `state.json` | CLI | CLI, hook | Structured contract: objective, scope, validations, checkpoints, budget, `base_ref` |
| `goal.md` | CLI (template) / human | humans, the agent | Human-readable contract |
| `work_log.md` | CLI (`log`, `run`, `checkpoint`) | humans, the agent | Evidence ledger + parking lot for tangents |
| `runs.jsonl` | CLI (`run`) | CLI (`score`) | Authoritative record of validation command + exit code |
| `events.jsonl` | hook | humans | Append-only log of every hook event (audit trail) |
| `agent_packets.md` | `goalkeeper-split` | humans, subagents | Per-packet scoped prompts |

## Why `/goal` needs the ledger

The host's `/goal` evaluator judges the completion condition from **evidence
surfaced in the conversation** — it does not independently run commands. So a
validation only "counts" if its result is visible in the transcript. That is
exactly why validations should be run through `goalkeeper run`: it surfaces the
real exit code into the conversation *and* records it to `runs.jsonl`, which the
audit reads. The work log plays the same role for checkpoint evidence.

## Cross-host design

Claude Code and Codex deliberately share hook conventions: the same `hooks.json`
shape, the same stdin/stdout JSON, and Codex aliases `CLAUDE_PLUGIN_ROOT`. So a
single shared hook script works in both. The differences are documented in the
[plugin README](../README.md#codex-caveats-verified-real-world): skill
invocation syntax, Codex's manifest having no `agents` field (agents ship as
separate `.codex/agents/*.toml`), Codex hooks firing reliably only for `Bash`,
and there being no `/loop` in the Codex CLI.

## Known limitations

- **Verification is advisory, not enforcing.** Nothing yet *blocks* `/goal`
  completion when `score` fails; the audit is a step you run. Making the Stop
  hook gate completion on a passing score is the highest-value next step.
- **Command blocking is a seatbelt, not a sandbox.** It is best-effort regex on
  the shell string and can be bypassed. Use host permission/sandbox modes for
  real isolation.
- **Two human-facing sources of truth.** `goal.md` and `state.json` can drift;
  `doctor` only weakly checks consistency. Rendering `goal.md` from `state.json`
  would remove the drift.
- **Concurrency.** Parallel split-packets that read-modify-write `state.json`
  can race; treat parallel packets as experimental.

See the [roadmap](../README.md#roadmap) for what's planned.
