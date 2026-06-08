# `goalkeeper` CLI reference

Dependency-free Python 3 (stdlib only). Invoke via `bin/goalkeeper`, a
PATH-installed `goalkeeper`, or a host plugin's bundled entrypoint. State lives
in the nearest ancestor `.goalkeeper/`.

## Lifecycle commands

| Command | What it does |
|---------|--------------|
| `init [-o OBJ] [--template NAME] [--domain D] [--force]` | Scaffold v2 `.goalkeeper/`, capture `base_ref`, render `goal.md`. Templates: `code-refactor, bugfix, research, writing, recurring-maintenance, data-quality, incident-review`. |
| `init --auto [-o OBJ] [--force]` | Inspect a code repo and create an active contract with detected validators, scope, forbidden paths, and a default checkpoint. Falls back to `git diff --check` when no stack-specific command is detected. |
| `adopt [-o OBJ] [--force]` | Create an active contract around the current git diff when work already started. `--force` replaces the current contract and clears goal-specific runtime evidence so old runs cannot satisfy the new goal. |
| `status` | Compact summary (status, objective, domain, risk, loop, lock). |
| `set FIELD VALUE` | Set a nested field by **dotted path** (e.g. `goal.objective`, `scope.allowed_resources`, `risk.level`). Re-renders `goal.md`. Refuses `completion.status=complete` and locked-contract edits. |
| `get FIELD` | Read a nested field as JSON. |
| `detect [--apply]` | Detect stack; suggest/write command validators. |
| `seed [--apply] [--json]` | Mine `AGENTS.md`/`CLAUDE.md`/CI for policy; suggest validators + forbidden resources. |
| `render [--format md\|prompt\|json]` | Render `goal.md` (md), the native `/goal` string (prompt), or canonical JSON. `goal.md` is generated — never hand-edit it. |
| `generate-goal` | Alias of `render --format prompt`. |
| `checkpoint [--add D] [--id ID --evidence E --met]` | Manage checkpoints (status `pending`/`met`). |
| `run "CMD"` | Run a validation command, stream output, record exit/duration/artifact metadata to `runs.jsonl`, and save capped stdout/stderr under `.goalkeeper/artifacts/runs/`. Returns the wrapped exit code. |

## Verification commands

| Command | Exit | What it does |
|---------|------|--------------|
| `validate-contract [--strict] [--json]` | 0/2 | Structural schema check; `--strict` adds cross-field rules. |
| `doctor [--json]` | 0/2 | Contract-quality report (bounded objective, required validator, scope, baseline visibility, strict-valid). |
| `score [--base REF] [--json]` | 0/2 | Evaluate validators + diff; print verdict + `Completion tier: N/6`. |
| `gate [--ci] [--json]` | 0/2 | **Exit 0 only when the active contract is complete and contract quality passes.** Lists blockers. `--ci` emits machine-parseable output. |
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

## Install, host, smoke

| Command | What it does |
|---------|--------------|
| `install shell\|claude\|codex\|all [--dry-run] [--json]` | Symlink the CLI or host plugin package into the default local target. |
| `uninstall shell\|claude\|codex\|all [--dry-run] [--json]` | Remove only Goalkeeper-owned symlinks. Refuses unrelated paths. |
| `host doctor [shell\|claude\|codex\|all] [--json]` | Verify local host wiring: paths, manifests, hook execution, binaries, and install hints. |
| `smoke [core\|claude\|codex] [--json]` | Run an isolated temp-repo proof flow and optional host hook deny check. |

Default install targets are `~/.local/bin/goalkeeper`,
`~/.claude/skills/goalkeeper`, and `~/.codex/plugins/goalkeeper`. Override them
with `GOALKEEPER_INSTALL_BIN_DIR`, `GOALKEEPER_CLAUDE_PLUGIN_DIR`, or
`GOALKEEPER_CODEX_PLUGIN_DIR`. Uninstall only removes symlinks that resolve back
to this checkout.

## Exit codes

`0` success / gate COMPLETE · `1` usage or no state · `2` review/incomplete /
strict-invalid · *n* = `run` returns the wrapped command's exit code.

## Run output capture

`goalkeeper run` streams stdout/stderr live and captures a bounded proof copy of
each stream. The default cap is 65536 bytes per stream; override with
`GOALKEEPER_RUN_OUTPUT_LIMIT_BYTES`. Truncated artifacts include a marker and the
JSON ledger records `stdout_truncated` / `stderr_truncated`.
