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
  events.jsonl     # hook log
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
goalkeeper init [-o OBJECTIVE] [--force]   # scaffold .goalkeeper/
goalkeeper status                          # compact summary
goalkeeper set FIELD VALUE                 # objective, allowed_paths, validations, ...
goalkeeper detect [--apply]                # detect stack, suggest validations
goalkeeper generate-goal [--host ...]      # print a native /goal command
goalkeeper checkpoint [--add | --id --evidence --met]
goalkeeper score [--base REF] [--json]     # score the diff against the contract
goalkeeper log MESSAGE                      # append to work_log.md
goalkeeper autocontinue on|off|reset [--max N]
```

`detect` knows Node, Python, Rust, Go, Java (Maven/Gradle), and Rails, and only
suggests Node scripts that actually exist in `package.json`.

`score` reports files changed outside allowed paths, forbidden-path changes,
checkpoints without evidence / not met, and an overall PASS/REVIEW verdict.

## Install — Claude Code (local testing)

```
claude --plugin-dir ./goalkeeper-loop
```

Then:

```
/goalkeeper Refactor the auth module to the new token API while preserving behavior and passing tests.
```

`/goal` requires Claude Code **v2.1.139+**.

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

Restart Codex, install from the local marketplace, then invoke:

```
$goalkeeper Refactor the auth module to the new token API while preserving behavior and passing tests.
```

Enable goals if needed:

```
codex features enable goals
```

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

1. **Language-aware validation presets** — implemented in `goalkeeper detect`
   (Node/Python/Rust/Go/Java/Rails); extend coverage.
2. **Diff-to-contract scoring** — implemented in `goalkeeper score`; add
   "validation commands not run" detection via the events log.
3. **Agent packet executor helpers** — generate exact Codex/Claude prompts per
   packet (researcher/implementer/verifier).
4. **Project policy integration** — read `AGENTS.md`, `CLAUDE.md`, package
   scripts, CI config to auto-improve the contract.
5. **A small eval suite** — DSPy-style metrics for contract quality (measurable
   done state, bounded objective, validation present, boundaries present, stop
   condition present).

## Status

Python helpers and hook behavior are syntax/smoke-tested. Test the plugin inside
live Codex or Claude Code in a disposable repo before using it on production
work.

## License

MIT © Robert Courson
