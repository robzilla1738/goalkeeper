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
| `PreToolUse` (`Edit`/`Write`, Codex `apply_patch`) | Deny writes whose target path is outside `scope.allowed_resources` or inside `scope.forbidden_resources` — scope enforced at the write boundary, not just detected after the fact. Allows when the path can't be parsed. |
| `PostToolUse` (Bash/shell) | Auto-record the command + exit code into `runs.jsonl` so `command` validators have evidence even without `goalkeeper run`. Records nothing when the exit code can't be determined (never fabricates a pass/fail). |
| `Stop` | **Gate-aware.** Acts when the contract is enforced (`loop.enforce`, set by templates / `init --auto`) or `loop_runtime.autocontinue` is on. Calls `goalkeeper_core.loop.decide_stop`. |

## Gate-aware Stop

`decide_stop` runs the completion **gate** and returns one of:

- **stop** — the gate passes (goal complete). On an active goal the hook closes
  the loop: it records completion + proof automatically (`accepted_by:
  auto:goalkeeper`), or, for a human-gated contract, prompts for
  `goalkeeper complete --accepted-by <name>`. The loop never pushes past a passing gate.
- **pause** — a `pause_when` condition is met (needs credentials/human, a required
  validator is unavailable, an approval is required) or the loop mode is human-gated.
  The hook surfaces guidance and lets the host stop.
- **continue** — required blockers remain and budget is left; the hook asks the
  host to continue (bounded by `loop.max_turns`), naming the open blockers.

See [LOOP_MODES](./concepts/LOOP_MODES.md) for per-mode behavior. Enforcement is
**on by default for gated work** (templates and `init --auto`/`adopt`) and is the
mechanism that makes "done" non-bypassable. Kill switches: `goalkeeper
autocontinue off` (clears `loop.enforce`) or `GOALKEEPER_NO_STOP=1`.

## Security model

Command screening is a **seatbelt, not a sandbox**: best-effort regex on the shell
string, bypassable via env vars, base64, `python -c`, or writing then executing a
script. Use your host's permission/sandbox modes for real isolation. See
[security/RISK_AND_APPROVALS](./security/RISK_AND_APPROVALS.md).

## Cross-host notes

Claude Code and Codex share the same `hooks.json` shape and stdin/stdout JSON; the
hook resolves the project root from the payload (`cwd`/`project_dir`) or
`CLAUDE_PROJECT_DIR`/`CODEX_PROJECT_DIR`. Both hosts can intercept `Bash` and the
write tools (Claude `Edit`/`Write`, Codex `apply_patch`). `PostToolUse` evidence
capture is best-effort — when a host doesn't surface a reliable exit code the hook
records nothing, so `goalkeeper run` (and `gate --rerun`) remain the authoritative
way to record a pass/fail. Codex runs non-managed hooks only after a one-time
`/hooks` trust (re-trust after edits); ship managed hooks via `requirements.toml`
to skip the prompt. Goalkeeper only emits `permissionDecision: "deny"` (Codex
parses but does not honor `"ask"`).
