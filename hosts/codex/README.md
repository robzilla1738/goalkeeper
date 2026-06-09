# Goalkeeper — Codex host

The Codex plugin package: skills, custom-agent prompts, and hooks. It calls the
shared `goalkeeper_core` engine through the same dependency-free entrypoints as
the shell and Claude hosts.

## Install / path setup

Pick one of these before invoking the Codex skills:

```bash
# preferred local install
python3 bin/goalkeeper install codex
python3 bin/goalkeeper install shell

# or point skills at an explicit entrypoint
export GOALKEEPER_BIN=/absolute/path/to/goalkeeper/bin/goalkeeper

# for copied plugin packages whose bin/ cannot walk up to the repo root
export GOALKEEPER_CORE_HOME=/absolute/path/to/goalkeeper
```

Hook commands also honor `GOALKEEPER_HOOK` if you need to point at a specific
`goalkeeper_hook.py`.

## Contents

**Skills:** `goalkeeper` (author a v2 contract and emit `/goal`),
`goalkeeper-split` (disjoint subagent packets), `goalkeeper-audit` (verify and
gate before "done").

**Codex agents:** researcher, scoped implementer, and verifier prompt configs.

**Hooks** (`hooks/hooks.json` wires `bin/goalkeeper_hook.py`):

- `SessionStart` / `UserPromptSubmit` inject the active contract summary.
- `PreToolUse` (Bash) blocks destructive and forbidden-resource commands.
- `PreToolUse` (apply_patch / Edit / Write) denies writes outside allowed scope
  or inside forbidden scope. Codex edits go through `apply_patch`, so scope gets
  enforced at the write boundary instead of caught afterward.
- `PostToolUse` (Bash) records the command and its exit code into `runs.jsonl`,
  so the gate has evidence even when the agent skipped `goalkeeper run`.
- `Stop` is gate-aware. For an enforced contract it holds the turn open (bounded
  by `loop.max_turns`) until the gate passes, then records completion and the
  proof bundle automatically. Human-gated contracts pause for a named accepter
  instead. It's on by default for templated and `init --auto` contracts;
  `goalkeeper autocontinue off` or `GOALKEEPER_NO_STOP=1` turns it off.

## Codex versions and the hooks trust gate

Codex hooks went GA in 2026, so use a recent Codex (`codex --version`). Three
things specific to Codex are worth knowing:

- **The trust step.** Non-managed hooks (user, project, plugin) don't run until
  you review and trust the exact hook definition once via `/hooks` in Codex.
  Change a hook and you re-trust it. `goalkeeper host doctor codex` reminds you.
- **Managed hooks.** Teams that want hooks trusted by policy can ship them via
  `requirements.toml` `[hooks]` (`allow_managed_hooks_only = true`) under MDM,
  which skips the per-user `/hooks` prompt.
- **Deny only.** Goalkeeper emits `permissionDecision: "deny"`. Codex parses
  `"ask"` but doesn't honor it yet, so deny is the only deterministic block.

Pin a minimum Codex version for `doctor` with `GOALKEEPER_CODEX_MIN_VERSION`
(for example `export GOALKEEPER_CODEX_MIN_VERSION=0.50.0`).

## Workflow

`init --auto` or `adopt` → `doctor` → `render --format prompt` → `/goal` →
`run`/`checkpoint` (record proof) → `gate` → `complete --accepted-by` → `proof`.

Codex has first-class `Stop` `decision:block`, so the gated-continuation loop
works the same as it does on Claude Code once you've done the one-time `/hooks`
trust: the agent can't end the turn claiming done before the gate passes. See
[`/goal` and continuation](../../docs/concepts/GOAL_AND_LOOP.md).
