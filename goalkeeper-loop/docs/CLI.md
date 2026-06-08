# `goalkeeper` CLI reference

A dependency-free Python 3 (stdlib only) tool that manages the Goal Contract
state under `.goalkeeper/`. It behaves identically in Claude Code, Codex, CI, or
a bare shell.

```bash
# Inside a plugin (Claude Code / Codex) the path is expanded for you:
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" <command> [args]

# From a clone:
python3 goalkeeper-loop/bin/goalkeeper <command> [args]
# or, if on PATH / executable:
goalkeeper <command> [args]
```

The CLI locates state by walking up from the current directory to the nearest
ancestor containing a `.goalkeeper/` directory (falling back to the cwd).

## Commands

### `init`
Scaffold `.goalkeeper/` and capture the diff baseline.

```
goalkeeper init [-o/--objective TEXT] [--force]
```
- `-o, --objective TEXT` — seed the objective.
- `--force` — overwrite an existing `state.json` (otherwise init is a no-op for
  state and only fills in missing files).
- Captures `base_ref` from `git rev-parse HEAD`. Creates `state.json`, `goal.md`,
  `work_log.md`, `agent_packets.md`, `events.jsonl`.

### `status`
Print a compact summary (status, objective, checkpoints met, scope, validations,
turn budget, auto-continue state). Exit 1 if no state exists.

### `set`
Set a single field in `state.json`.

```
goalkeeper set FIELD VALUE
```
- List fields (`allowed_paths`, `forbidden_paths`, `forbidden_actions`,
  `validations`) take a comma-separated VALUE → JSON array.
- Int fields (`stop_after_turns`, `max_autocontinue_turns`) are coerced to int.
- `autocontinue` accepts `on/off/true/false/yes/no/1/0`.
- Any other FIELD is set as a string (e.g. `objective`, `status`).
- Setting `status active` captures `base_ref` if it is not already set.

### `detect`
Detect the project stack and print suggested validation commands.

```
goalkeeper detect [--apply]
```
- Knows Node, Python, Rust, Go, Java (Maven/Gradle), Ruby/Rails.
- For Node, only suggests `npm run <script>` entries that exist in `package.json`.
- `--apply` writes the suggestions into `state.json` `validations`.

### `seed`
Mine repository policy/config to seed the contract.

```
goalkeeper seed [--apply] [--json]
```
- Reports detected validations, policy files (`AGENTS.md`, `CLAUDE.md`,
  `CONTRIBUTING.md`), CI workflows, and commonly-forbidden dirs (`.github/**`,
  `node_modules/**`, `dist/**`, `build/**`, `vendor/**` — only those that exist).
- `--apply` writes suggested `validations` and merges `forbidden_paths`.
- `--json` emits the findings as JSON.

### `doctor`
Contract-quality + consistency check (DSPy-style metrics).

```
goalkeeper doctor [--json]
```
Checks: objective set; objective bounded (no vague terms like "better",
"improve", "etc"); validation surface present; scope boundaries present; stop
condition present; ≥1 checkpoint; `goal.md` ⇄ `state.json` consistency;
`base_ref` captured.
- **Exit 0** if all checks pass (100%); **exit 2** otherwise.

### `generate-goal`
Print the native `/goal` command assembled from the contract (objective + scope +
validations + constraints + stop budget). Same syntax works in Claude Code and
Codex.

### `checkpoint`
Manage measurable milestones.

```
goalkeeper checkpoint                       # list checkpoints
goalkeeper checkpoint --add "DESC"          # add one (auto-id cpN)
goalkeeper checkpoint --id cp1 --evidence "…" --met   # update one
```
Updating a checkpoint also appends a line to `work_log.md`.

### `run`
Run a validation command, stream its output, and **record** the result.

```
goalkeeper run "npm test -- tests/auth"
```
- Executes via the shell in the project root.
- Appends `{cmd, exit, ts}` to `.goalkeeper/runs.jsonl` and a line to
  `work_log.md`.
- **Returns the wrapped command's exit code** (so it composes in scripts/CI).
- This is the authoritative record `score` reads to confirm validations ran and
  passed — host `PostToolUse` hooks cannot reliably capture exit codes.

### `score`
Score the current diff against the contract.

```
goalkeeper score [--base REF] [--json]
```
- Diffs the working tree against `--base` if given, else the `base_ref` captured
  at goal start, else `HEAD`. Uses a three-dot merge-base diff, **excludes**
  `.goalkeeper/` itself, and **includes** untracked files.
- Reports: `files_outside_allowed_paths`, `forbidden_path_changes`,
  `validations_not_run`, `validations_failed`, `checkpoints_without_evidence`,
  `checkpoints_not_met`, a 0–100 `score`, and a `PASS`/`REVIEW` `verdict`.
- `--json` emits the full report.
- **Exit 0** if `verdict == PASS`; **exit 2** otherwise.

### `log`
Append a timestamped line to `work_log.md`.

```
goalkeeper log "AUDIT: typecheck exit 0; scope clean"
```

### `autocontinue`
Toggle the optional bounded Stop-hook auto-continue.

```
goalkeeper autocontinue on  [--max N]   # enable (default budget 4 if unset)
goalkeeper autocontinue off
goalkeeper autocontinue reset           # zero the used-turns counter
```
Off by default — native `/goal` is the preferred loop. See [HOOKS.md](./HOOKS.md).

## Exit codes (summary)

| Code | Meaning |
|------|---------|
| `0` | Success / `doctor` 100% / `score` PASS |
| `1` | Usage error (e.g. no `state.json`; `status` with no state) |
| `2` | `doctor` < 100%, `score` REVIEW |
| *n* | `run` returns the wrapped command's own exit code |
