# The Goal Contract

A **Goal Contract** is the explicit agreement that governs a long-running task.
It is the answer to "what would make me confident this is done and in-bounds?"
written down *before* the agent starts. Goalkeeper stores it in two forms:

- `.goalkeeper/state.json` — the structured, machine-readable source of truth
  that the CLI and hook read.
- `.goalkeeper/goal.md` — a human-readable rendering for review.

> If the two disagree, `state.json` wins — every program (`generate-goal`,
> `score`, the hook) reads `state.json`. Keep `goal.md` in sync, or treat it as
> a comment.

## The six elements

Every good contract answers six questions. `goalkeeper doctor` checks that they
are all present and that the objective is bounded.

| Element | `state.json` field | Question it answers |
|---------|--------------------|---------------------|
| **Objective** | `objective` | What outcome (one sentence, not a task list)? |
| **Allowed scope** | `allowed_paths` | Which files may change? |
| **Boundaries** | `forbidden_paths`, `forbidden_actions` | What must *not* change? |
| **Validation surface** | `validations` | Which commands prove it works? |
| **Checkpoints** | `checkpoints` | What measurable milestones, each with evidence? |
| **Stopping condition** | `stop_after_turns` | When to stop / pause? |

## `state.json` schema

```jsonc
{
  "schema_version": 1,
  "created_at": "2026-06-08T02:30:00+00:00",
  "updated_at": "2026-06-08T02:45:00+00:00",

  "status": "active",          // draft | active | paused | complete | abandoned
  "objective": "Refactor auth to the new token API while preserving behavior",

  "base_ref": "81fe7e1c…",     // git sha captured at init / first activation;
                               // the baseline `score` diffs against

  "allowed_paths":    ["src/auth/**", "tests/auth/**"],
  "forbidden_paths":  [".github/**"],
  "forbidden_actions": ["add production dependencies", "change public behavior"],

  "validations": ["npm test -- tests/auth", "npm run typecheck"],

  "checkpoints": [
    { "id": "cp1", "desc": "all auth routes use new token API",
      "evidence": "rg jwt.decode src/routes/auth -> no matches", "met": true }
  ],

  "stop_after_turns": 12,      // turn budget for the native /goal stop condition

  // optional bounded Stop-hook auto-continue (off by default)
  "autocontinue": false,
  "max_autocontinue_turns": 4,
  "autocontinue_turns_used": 0,

  "host": "claude"             // detected host: claude | codex | generic
}
```

### Field notes

- **`status`** gates the hook: context is injected and auto-continue runs only
  while a goal is `active` (or `draft`); a `complete`/`abandoned` goal is inert.
- **`base_ref`** is captured at `init` and (if still empty) when `status` is set
  to `active`. `score` diffs the working tree against it. Without it, scoring
  falls back to `HEAD`.
- **`allowed_paths` / `forbidden_paths`** use glob-ish patterns: trailing `/**`
  matches a directory subtree; `fnmatch` patterns like `*.lock` also work.
- **`forbidden_actions`** are *not* enforced by command blocking (that produced
  false positives). They are rendered into the `/goal` constraints and checked by
  `goalkeeper-audit` reading the diff.
- **`checkpoints[]`** each have `id`, `desc`, `evidence`, `met`. A checkpoint is
  only truly done when `met: true` *and* `evidence` is non-empty — `score` flags
  both `checkpoints_not_met` and `checkpoints_without_evidence`.

## Editing the contract

Use the CLI rather than hand-editing JSON where possible:

```bash
goalkeeper set objective "Refactor auth to the new token API, preserve behavior"
goalkeeper set allowed_paths "src/auth/**,tests/auth/**"
goalkeeper set forbidden_paths ".github/**"
goalkeeper set forbidden_actions "add production dependencies,change public behavior"
goalkeeper set validations "npm test -- tests/auth,npm run typecheck"
goalkeeper set stop_after_turns 12
goalkeeper checkpoint --add "all auth routes use new token API"
goalkeeper set status active
goalkeeper doctor          # gate: fix any FAIL before generating /goal
goalkeeper generate-goal
```

Comma-separated values become JSON arrays; `stop_after_turns` /
`max_autocontinue_turns` are coerced to ints; `autocontinue` accepts
`on/off/true/false/1/0`.

## `goal.md` structure

`init` writes a template with sections mirroring the six elements (Objective,
Allowed scope, Forbidden paths/actions, Validation surface, Checkpoints,
Iteration policy, Stopping condition). Flesh it out so a fresh agent could pick
up the task cold. It is the document a human reviews before approving the run.

## What a generated `/goal` looks like

`generate-goal` assembles the contract into a single bounded command:

```
/goal Refactor auth to the new token API while preserving behavior only in
src/auth/**, tests/auth/**. Done means npm test -- tests/auth exits 0, and
npm run typecheck exits 0, and .goalkeeper/work_log.md contains evidence for
each checkpoint. Constraints: do not add production dependencies; do not change
public behavior; do not change .github/**. Pause if credentials or human input
are needed, or after 12 turns without all checks passing.
```

That is the contract in one line: **objective, scope, proof, constraints, and a
stop budget.**
