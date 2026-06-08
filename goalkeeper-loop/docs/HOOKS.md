# Hooks reference

`hooks/hooks.json` registers a single script, `bin/goalkeeper_hook.py`, against
host lifecycle events. The host pipes a JSON event to the script on **stdin**;
the script replies with JSON on **stdout**. The script is defensive: any internal
error exits `0` ("do nothing") so it can never crash the host, and it tolerates
unknown event shapes (it reads several field-name aliases).

Claude Code and Codex share this hook convention (same JSON shapes; Codex aliases
`CLAUDE_PLUGIN_ROOT`), so the one script serves both.

## Wired events

| Event | Matcher | What the hook does |
|-------|---------|--------------------|
| `SessionStart` | — | Inject the active contract summary as context |
| `UserPromptSubmit` | — | Inject the active contract summary as context |
| `SubagentStart` | — | Inject the active contract summary into the subagent |
| `PreToolUse` | `Bash` | Screen the command; deny if destructive or out-of-scope |
| `Stop` | — | Optional bounded auto-continue (off by default) |
| `SubagentStop` | — | Logged only (no auto-continue for subagents) |

Every event is appended to `.goalkeeper/events.jsonl` for an audit trail.

## stdin payload (fields the hook reads)

```jsonc
{
  "hook_event_name": "PreToolUse",   // also accepts hookEventName/event/type/hook
  "cwd": "/path/to/project",         // also project_dir/projectDir/workspace_root
  "tool_name": "Bash",               // also toolName/tool
  "tool_input": { "command": "…" }   // also cmd/script/content; or a bare string
}
```

The hook resolves the project root from `cwd`/`project_dir` (or
`CLAUDE_PROJECT_DIR` / `CODEX_PROJECT_DIR` / cwd), then walks up to the nearest
`.goalkeeper/`.

## stdout responses

**Context injection** (`SessionStart`, `UserPromptSubmit`, `SubagentStart`):

```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "[Goalkeeper] Active Goal Contract … Objective: …"
  }
}
```

The injected summary lists objective, allowed/forbidden paths, validations, and
checkpoint progress, and reminds the agent to stay in scope, park tangents, and
never claim done without evidence. Nothing is emitted if there is no active goal
(status `complete`/`abandoned` → inert).

**Deny a command** (`PreToolUse`):

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "[Goalkeeper] Blocked: …"
  }
}
```

Safe commands produce no output (the call proceeds normally).

**Bounded continue** (`Stop`, only if `autocontinue` is enabled):

```json
{
  "decision": "block",
  "reason": "[Goalkeeper] Bounded auto-continue 1/4 …",
  "hookSpecificOutput": {
    "hookEventName": "Stop",
    "additionalContext": "[Goalkeeper] Bounded auto-continue 1/4 … remaining checkpoints: cp3 …"
  }
}
```

> `decision: block` forces the host to keep going. The model **ignores the
> `reason` field**, so the actual guidance is duplicated into
> `additionalContext`. Both are emitted for portability.

## Command screening

On `PreToolUse` for `Bash`-like tools, the hook denies a command if it matches a
**destructive pattern** or references a **forbidden path**.

Destructive patterns (best-effort regex) include:

- `rm -rf /`, `rm -rf ~ / $HOME / *`
- `git reset --hard`, `git clean -fd…`, `git checkout -- .`, force-push (`--force` / `-f`)
- `mkfs…`, `dd … of=/dev/…`, `> /dev/sd…`, `chmod -R 777 /`, `truncate -s 0`
- classic fork bomb `:(){ :|:& };:`

Forbidden-path blocking: if a command's text references any `forbidden_paths`
token from the contract, it is denied.

> **Forbidden _actions_ are not screened here.** Inferring intent from keywords in
> a shell string produced false positives (e.g. any command containing
> "production"). Forbidden actions are enforced by `goalkeeper-audit` reading the
> actual diff.

## Bounded auto-continue (opt-in)

Off by default — native `/goal` is the preferred loop. When enabled in
`state.json`:

```json
{ "autocontinue": true, "max_autocontinue_turns": 4, "autocontinue_turns_used": 0 }
```

the `Stop` hook will continue the agent **only** while:

- the goal `status` is `active` (or `draft`), and
- `autocontinue_turns_used < max_autocontinue_turns`, and
- not all checkpoints are already met.

Each continue increments the counter and logs to `events.jsonl`. Toggle with
`goalkeeper autocontinue on|off|reset [--max N]`.

## Security model — important

The hook is a **seatbelt, not a sandbox.** Command screening is pattern matching
on a single shell string and is trivially bypassable (environment variables,
`base64`, `python -c "…"`, writing a script then executing it, etc.). It exists
to catch *accidental* footguns, not to contain a determined or compromised agent.

For real isolation, rely on the host's own permission/sandbox modes:
- Claude Code permission modes and allow/deny rules,
- Codex `sandbox_mode` (`read-only` / `workspace-write`) and `approval_policy`.

Additional cross-host caveats:
- **Codex plugin-bundled hooks can fail to load** (a known issue). If the hook
  doesn't fire, also register `hooks/hooks.json` at the user layer
  (`~/.codex/hooks.json`) and inspect with `/hooks`.
- **Codex hooks fire reliably for `Bash`, not for `apply_patch`/MCP edits**, so
  `PreToolUse` path guarding is best-effort there — lean on `goalkeeper-audit`.

## Testing the hook

The hook is covered end-to-end by the test suite (piping crafted JSON to the
script as a subprocess). To try it by hand:

```bash
echo '{"hook_event_name":"SessionStart","cwd":"'"$PWD"'"}' \
  | python3 goalkeeper-loop/bin/goalkeeper_hook.py
```
