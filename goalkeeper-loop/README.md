# Goalkeeper Loop

A cross-compatible **Claude Code + Codex** plugin that adds a **Goal Contract →
verifier → ledger → subagent packet** layer on top of the first-party `/goal`,
`/loop`, hooks, skills, and subagents.

> **Contract, don't vibe.** The DSPy lesson — *program, don't prompt* — applied
> to agentic coding: define objective, validation surface, allowed scope,
> constraints, iteration policy, and stopping condition *before* agents run.

This plugin does **not** ship a raw infinite-loop wrapper. Claude Code and Codex
already have first-party continuation primitives; Goalkeeper sits above them.

## Why this exists

| Primitive | What it's for |
|-----------|---------------|
| `/goal` (Claude Code & Codex) | Keep working turn-by-turn until a **condition** is met. A fast evaluator judges the condition from conversation evidence. Use when the next turn happens because the last one didn't satisfy the condition. |
| `/loop` (Claude Code) | **Scheduled / recurring** prompts (CI polling, PR babysitting, reminders). Use when the next turn happens because *time passed*. Session-scoped; recurring tasks expire after ~7 days. |
| Hooks | Enforcement: inject context, block tool use, participate in stop/continue. |
| Skills / Plugins | Reusable, progressively-loaded workflows and packaging. |
| Subagents | Separate-context work for noisy/read-heavy/specialized tasks (costly — scope tightly). |

Goalkeeper turns a messy request into a **measurable, bounded, auditable**
contract and then hands the loop to native `/goal`.

## The flow

```
/goalkeeper -> create Goal Contract -> generate native /goal
            -> run checkpoints -> goalkeeper-audit -> complete or pause
```

It creates project-local state:

```
.goalkeeper/
  goal.md          # human-readable Goal Contract
  state.json       # structured machine-readable state
  work_log.md      # evidence ledger + parking lot
  agent_packets.md # multi-agent task packets
  events.jsonl     # hook event log
  runs.jsonl       # recorded validation runs (cmd + exit code)
```

## Contents

```
goalkeeper-loop/
  .codex-plugin/plugin.json     # Codex manifest
  .claude-plugin/plugin.json    # Claude Code manifest
  skills/
    goalkeeper/                 # author a Goal Contract, generate /goal
    goalkeeper-audit/           # verify the diff satisfies the contract
    goalkeeper-split/           # safe non-overlapping subagent packets
  hooks/
    hooks.json                  # wires the hook to host events
  bin/
    goalkeeper                  # state CLI (init/status/detect/generate-goal/score/...)
    goalkeeper_hook.py          # conservative cross-host hook
  agents/                       # Claude Code plugin agents
  codex-agents/                 # Codex custom-agent TOML examples for .codex/agents/
  examples/marketplace.json     # local Codex marketplace config
  tests/                        # pytest suite (CLI + hook, run via `pytest -q`)
  README.md
```

## Skills

- **goalkeeper** — starts a long-running task. Turns a messy request into a
  measurable Goal Contract, writes `.goalkeeper/` state, and generates a native
  `/goal` command for Codex or Claude Code.
- **goalkeeper-split** — turns the active goal into safe subagent packets,
  preventing the failure mode where multiple agents edit the same files or
  wander into unrelated cleanup.
- **goalkeeper-audit** — checks whether the active diff actually satisfies the
  contract: evidence, scope drift, missing validation, forbidden-path changes,
  premature completion claims.

## Hooks

The hook (`bin/goalkeeper_hook.py`) is intentionally conservative. By default it:

- injects active `.goalkeeper` context into new sessions, prompts, and subagents
- blocks obvious destructive commands (dangerous `rm` / `git reset --hard` /
  `git clean -fd` / force-push / `mkfs` / `dd` / fork-bomb patterns)
- blocks commands mentioning configured forbidden paths/actions
- logs hook events to `.goalkeeper/events.jsonl`
- does **not** auto-continue unless explicitly enabled

### Optional bounded auto-continue (off by default)

Native `/goal` is usually the better mechanism. If you want a headless,
*bounded* Stop-hook loop, set in `.goalkeeper/state.json`:

```json
{
  "autocontinue": true,
  "max_autocontinue_turns": 4,
  "autocontinue_turns_used": 0
}
```

The Stop hook then continues only while the goal is active and within the turn
budget, and stops automatically once all checkpoints are met or the budget is
spent. Toggle via:

```
python3 bin/goalkeeper autocontinue on --max 4
python3 bin/goalkeeper autocontinue off
```

## The `goalkeeper` CLI

Dependency-free (Python 3 stdlib). Same behavior in Claude Code, Codex, CI, or a
bare shell.

```
goalkeeper init [-o OBJECTIVE] [--force]   # scaffold .goalkeeper/, capture diff baseline
goalkeeper status                          # compact summary
goalkeeper set FIELD VALUE                 # objective, allowed_paths, validations, ...
goalkeeper detect [--apply]                # detect stack, suggest validations
goalkeeper seed [--apply] [--json]         # mine AGENTS.md/CLAUDE.md/CI to seed contract
goalkeeper doctor [--json]                 # contract-quality + consistency check
goalkeeper generate-goal                   # print a native /goal command
goalkeeper checkpoint [--add | --id --evidence --met]
goalkeeper run "CMD"                        # run a validation and RECORD it (exit code)
goalkeeper score [--base REF] [--json]     # score the diff against the contract
goalkeeper log MESSAGE                      # append to work_log.md
goalkeeper autocontinue on|off|reset [--max N]
```

- **`detect`** knows Node, Python, Rust, Go, Java (Maven/Gradle), and Rails, and
  only suggests Node scripts that actually exist in `package.json`.
- **`seed`** reads `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, CI workflows, and
  common build/output dirs to propose validations and forbidden paths.
- **`doctor`** scores the contract (DSPy-style metrics): measurable done-state,
  bounded objective, validations present, boundaries present, stop condition
  present, and `goal.md` ⇄ `state.json` consistency. Exits non-zero if any fail.
- **`run`** is the *authoritative* validation recorder. PostToolUse hooks can't
  reliably capture exit codes (and don't fire for non-Bash tools in Codex), so
  running validations through `goalkeeper run` writes `.goalkeeper/runs.jsonl`,
  which `score` and the audit read to confirm each validation actually ran and
  exited 0.
- **`score`** diffs against the `base_ref` captured when the goal started
  (three-dot merge-base, excluding `.goalkeeper/` itself and including untracked
  files), and reports: files outside allowed paths, forbidden-path changes,
  validations not run / failed, checkpoints without evidence / not met, and an
  overall PASS/REVIEW verdict.

## Install — Claude Code (local testing)

```
claude --plugin-dir ./goalkeeper-loop
```

Plugin skills are **namespaced by plugin name**, so invoke it as:

```
/goalkeeper-loop:goalkeeper Refactor the auth module to the new token API while preserving behavior and passing tests.
```

(The model can also auto-invoke the skill from its description; the namespaced
slash form is the explicit way to call it. To get a shorter command, rename the
plugin's `name` in both manifests.) `/goal` requires Claude Code **v2.1.139+**.

## Install — Codex (local marketplace testing)

From your repo root:

```
mkdir -p ./plugins .agents/plugins
cp -R goalkeeper-loop ./plugins/goalkeeper-loop
```

Create `.agents/plugins/marketplace.json`:

```json
{
  "name": "local-repo",
  "plugins": [
    {
      "name": "goalkeeper-loop",
      "source": { "source": "local", "path": "./plugins/goalkeeper-loop" },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Productivity"
    }
  ]
}
```

Restart Codex, install from the local marketplace, then invoke the skill by
typing `$` in the composer and picking it (or):

```
$goalkeeper Refactor the auth module to the new token API while preserving behavior and passing tests.
```

Enable goals if needed:

```
codex features enable goals
```

### Codex caveats (verified, real-world)

- **Hook schema is compatible.** Codex models its hooks on Claude Code: same
  `hooks.json` shape, same stdin/stdout JSON, and it aliases `CLAUDE_PLUGIN_ROOT`
  — so the single shared hook script works in both.
- **Plugin-bundled hooks can be flaky in Codex** (known loading issue). If the
  hook doesn't fire, also register `hooks/hooks.json` at the user layer
  (`~/.codex/hooks.json`) and inspect with `/hooks`.
- **Codex hooks fire reliably for `Bash`, not for `apply_patch`/MCP edits**, so
  path-edit guarding is best-effort there — rely on `goalkeeper-audit`.
- **No `/loop` in the Codex CLI.** Use `/goal` for long-horizon autonomy;
  interval scheduling is a Codex *app* automation feature, not CLI.
- **Codex custom agents are not bundled by the manifest.** Copy the examples
  from `codex-agents/` into `.codex/agents/`. Codex gates capability via
  `sandbox_mode` (`read-only` / `workspace-write`), not a per-agent tools list.

## Best-practice workflow

For large refactors, research, migrations, and multi-agent work:

1. Run **goalkeeper**.
2. Let it create `.goalkeeper/goal.md` and `state.json`.
3. Review the generated native `/goal` command.
4. Run `/goal` with the generated bounded condition.
5. Use **goalkeeper-split** only if parallel work is actually useful.
6. Run **goalkeeper-audit** before accepting "done".

A good generated native goal looks like:

```
/goal Complete the auth refactor only in src/auth/**, src/routes/auth**, and
tests/auth/**. Done means npm test -- tests/auth exits 0, npm run typecheck
exits 0, rg "jwt\.decode" src/routes/auth returns no direct route-handler usage,
and .goalkeeper/work_log.md contains evidence for each checkpoint. Do not change
public behavior or add production dependencies. Pause if credentials are needed
or after 12 turns without all checks passing.
```

That is the core: **objective, scope, proof, constraints, and stop budget.**

## Roadmap

1. ✅ **Language-aware validation presets** — `goalkeeper detect`
   (Node/Python/Rust/Go/Java/Rails). *Extend coverage.*
2. ✅ **Diff-to-contract scoring** — `goalkeeper score`, with baseline capture
   and "validations not run / failed" via the run ledger.
3. **Agent packet executor helpers** — `goalkeeper-split` emits per-packet
   prompts; a one-shot executor that launches them is still TODO.
4. ✅ **Project policy integration** — `goalkeeper seed` reads
   `AGENTS.md`/`CLAUDE.md`/CI to seed the contract. *Deepen parsing.*
5. ✅ **Contract-quality eval** — `goalkeeper doctor` (DSPy-style metrics).
   *Grow into a fixture-based eval set.*

## Status & testing

A `pytest` suite (`tests/`) covers the CLI helpers, scoring, the run ledger,
`doctor`, and the hook end-to-end (32 tests); CI runs it on Python 3.9–3.12.

```
cd goalkeeper-loop && pip install pytest && pytest -q
```

Still: test the plugin inside **live** Codex or Claude Code in a disposable repo
before production use — the hosts' hook loading and skill invocation are
environment-specific (see Codex caveats above).

## License

MIT © Robert Courson
