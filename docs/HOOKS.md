# Hooks reference

`hosts/<host>/hooks/hooks.json` registers `bin/goalkeeper_hook.py` against host
lifecycle events. The host pipes a JSON event on stdin; the script answers with
JSON on stdout. It is defensive — any internal error exits 0 ("do nothing") and
never crashes the host. Every event is appended to `.goalkeeper/events.jsonl`.

## Events

| Event | Behavior |
|-------|----------|
| `SessionStart` / `UserPromptSubmit` / `SubagentStart` | Inject the active contract summary (objective, scope, validators, checkpoint progress, risk) as context. Inert when status is `complete`/`abandoned`. |
| `PreToolUse` (Bash/shell) | Deny obvious destructive commands (`rm -rf /`, `git reset --hard`, `git clean -fd`, force-push, `mkfs`, `dd`, fork bomb, …) and commands referencing `scope.forbidden_resources`. |
| `Stop` | **Gate-aware and optional.** Only acts when `loop_runtime.autocontinue` is on. Calls `goalkeeper_core.loop.decide_stop`. |

## Gate-aware Stop

`decide_stop` runs the completion **gate** and returns one of:

- **stop** — the gate passes (goal complete); let the host stop. The loop never
  pushes past a passing gate.
- **pause** — a `pause_when` condition is met (needs credentials/human, a required
  validator is unavailable, an approval is required) or the loop mode is human-gated.
  The hook surfaces guidance and lets the host stop.
- **continue** — required blockers remain and budget is left; the hook asks the
  host to continue (bounded by `loop.max_turns`), naming the open blockers.

See [LOOP_MODES](./concepts/LOOP_MODES.md) for per-mode behavior. Auto-continue is
**off by default** — native `/goal` is the preferred loop. Goalkeeper can
cooperate with host continuation, but it is not a universal `/loop` wrapper.

## Security model

Command screening is a **seatbelt, not a sandbox**: best-effort regex on the shell
string, bypassable via env vars, base64, `python -c`, or writing then executing a
script. Use your host's permission/sandbox modes for real isolation. See
[security/RISK_AND_APPROVALS](./security/RISK_AND_APPROVALS.md).

## Cross-host notes

Claude Code and Codex share the same `hooks.json` shape and stdin/stdout JSON; the
hook resolves the project root from the payload (`cwd`/`project_dir`) or
`CLAUDE_PROJECT_DIR`/`CODEX_PROJECT_DIR`. Codex hooks fire reliably for `Bash` but
not for `apply_patch`/MCP edits — which is exactly why validations are recorded
through `goalkeeper run` rather than inferred from tool events.
