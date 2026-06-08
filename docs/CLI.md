# `goalkeeper` CLI reference

Dependency-free Python 3 (stdlib only). Invoke via `bin/goalkeeper`, or inside a
plugin via `python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper"`. State lives in the
nearest ancestor `.goalkeeper/`.

## Lifecycle commands

| Command | What it does |
|---------|--------------|
| `init [-o OBJ] [--template NAME] [--domain D] [--force]` | Scaffold v2 `.goalkeeper/`, capture `base_ref`, render `goal.md`. Templates: `code-refactor, bugfix, research, writing, recurring-maintenance, data-quality, incident-review`. |
| `status` | Compact summary (status, objective, domain, risk, loop, lock). |
| `set FIELD VALUE` | Set a nested field by **dotted path** (e.g. `goal.objective`, `scope.allowed_resources`, `risk.level`). Re-renders `goal.md`. Refuses `completion.status=complete` and locked-contract edits. |
| `get FIELD` | Read a nested field as JSON. |
| `detect [--apply]` | Detect stack; suggest/write command validators. |
| `seed [--apply] [--json]` | Mine `AGENTS.md`/`CLAUDE.md`/CI for policy; suggest validators + forbidden resources. |
| `render [--format md\|prompt\|json]` | Render `goal.md` (md), the native `/goal` string (prompt), or canonical JSON. `goal.md` is generated — never hand-edit it. |
| `generate-goal` | Alias of `render --format prompt`. |
| `checkpoint [--add D] [--id ID --evidence E --met]` | Manage checkpoints (status `pending`/`met`). |
| `run "CMD"` | Run a validation command, stream it, record exit code to `runs.jsonl`. Returns the wrapped exit code. |

## Verification commands

| Command | Exit | What it does |
|---------|------|--------------|
| `validate-contract [--strict] [--json]` | 0/2 | Structural schema check; `--strict` adds cross-field rules. |
| `doctor [--json]` | 0/2 | Contract-quality gate (bounded objective, required validator, scope, baseline, strict-valid). |
| `score [--base REF] [--json]` | 0/2 | Evaluate validators + diff; print verdict + `Completion tier: N/6`. |
| `gate [--ci] [--json]` | 0/2 | **Exit 0 only when the contract is complete.** Lists blockers. `--ci` emits machine-parseable output. |
| `complete --accepted-by NAME` | 0/2 | The **only** writer of `completion.status=complete`; refuses unless `gate` passes; writes the proof bundle. |
| `proof [--format md\|json\|both]` | 0/2 | Write `.goalkeeper/proof.{md,json}` + `artifacts/`. |

## Risk, contract, packets

| Command | What it does |
|---------|--------------|
| `approve WHAT --by NAME [--note N]` | Record a human/risk approval. |
| `contract-lock` | Freeze the contract (stores a content hash). |
| `contract-unlock --reason TEXT` | Unlock + record an amendment (reason required). |
| `contract-diff` | Show whether the contract changed since lock. |
| `split [--write-packets]` | Partition allowed scope into disjoint-write packets; write prompts to `agent_packets.md`. |
| `packets list \| run ID \| reconcile` | List packets, scope one, or check combined diffs honored disjoint write-sets. |
| `autocontinue on\|off\|reset [--max N]` | Toggle bounded Stop-hook auto-continue. |
| `log "MSG"` | Append a line to `work_log.md`. |

## Exit codes

`0` success / gate COMPLETE · `1` usage or no state · `2` review/incomplete /
strict-invalid · *n* = `run` returns the wrapped command's exit code.
