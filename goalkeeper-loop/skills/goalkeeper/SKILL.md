---
name: goalkeeper
description: >
  Start a long-running, bounded coding task by turning a messy request into a
  measurable Goal Contract. Writes .goalkeeper/ state files (goal.md,
  state.json, work_log.md) and generates a native /goal command for Claude Code
  or Codex. Use this BEFORE large refactors, migrations, research sweeps, or any
  multi-turn work where "done" must be defined up front. Trigger on requests
  like "refactor X", "migrate Y to Z", "keep working until tests pass", or when
  the user invokes /goalkeeper.
---

# Goalkeeper — author a Goal Contract, then hand off to native /goal

You are setting up a **contract, don't vibe** workflow. The deliverable of this
skill is a precise, bounded Goal Contract plus a ready-to-run native `/goal`
command. You are NOT yet doing the implementation work.

## Principle

Do not build a raw infinite loop. Both Claude Code and Codex have first-party
continuation primitives (`/goal`). Your job is the layer *above* them: define
**objective, validation surface, allowed scope, constraints, iteration policy,
and stopping condition** before any agent runs. Every objective must be
*measurable* and *bounded*.

## Workflow

### 1. Detect the stack and existing policy
Run the helper to detect the project's language(s) and suggested validations,
and read any repo policy files so the contract reflects reality:

```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" detect
```

Also read, if present: `AGENTS.md`, `CLAUDE.md`, `package.json` scripts, CI
config (`.github/workflows/*`), and `CONTRIBUTING.md`. Use these to choose
real test/build/typecheck commands rather than guessing.

### 2. Interview the request into a contract
From the user's request, derive each field. If a field is genuinely ambiguous
and the answer changes scope, ask the user — otherwise pick a sensible default
and state it.

- **Objective** — one sentence, outcome-oriented, not a task list.
- **Allowed paths** — globs the agent may modify (e.g. `src/auth/**`).
- **Forbidden paths / actions** — e.g. "do not change public API", "do not add
  production dependencies", "do not touch CI config".
- **Validation surface** — exact commands whose exit code proves done
  (e.g. `npm test -- tests/auth exits 0`, `npm run typecheck exits 0`,
  plus targeted `rg` checks for the specific change).
- **Checkpoints** — measurable milestones; each needs evidence later.
- **Stopping condition** — all validations pass AND every checkpoint has
  evidence; pause if credentials/human input needed, or after N turns.

### 3. Initialize state
```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" init -o "<objective>"
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" set allowed_paths "src/auth/**,tests/auth/**"
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" set forbidden_actions "do not change public behavior,do not add production dependencies"
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" set validations "npm test -- tests/auth,npm run typecheck"
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" set stop_after_turns 12
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" checkpoint --add "All auth routes use new token API"
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" set status active
```

Then open `.goalkeeper/goal.md` and flesh out the human-readable contract so a
fresh agent could pick it up cold.

### 4. Generate the native /goal command
```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" generate-goal
```

Show the generated command to the user and explain that running it hands the
turn-by-turn loop to the host's first-party evaluator. A good generated goal
contains **objective, scope, proof, constraints, and a stop budget**, e.g.:

> `/goal Complete the auth refactor only in src/auth/**, src/routes/auth**, and
> tests/auth/**. Done means npm test -- tests/auth exits 0, npm run typecheck
> exits 0, rg "jwt\.decode" src/routes/auth returns no direct route-handler
> usage, and .goalkeeper/work_log.md contains evidence for each checkpoint. Do
> not change public behavior or add production dependencies. Pause if
> credentials are needed or after 12 turns without all checks passing.`

### 5. Recommend next steps
- Run the generated `/goal` (Claude Code ≥ v2.1.139) or, on Codex, enable goals
  with `codex features enable goals` and run `/goal`.
- Use **goalkeeper-split** only if parallel work is genuinely useful.
- Run **goalkeeper-audit** before accepting "done".

## Guardrails
- Never produce an unbounded objective (no "make it better", no "etc.").
- Every objective needs a measurable done-state and a stop budget.
- Prefer native `/goal` over the optional Stop-hook auto-continue. Mention
  auto-continue only if the user explicitly wants headless bounded looping;
  it is off by default in `state.json`.
- Do not start implementing in this skill. Set up the contract and hand off.
