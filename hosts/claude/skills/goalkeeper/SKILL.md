---
name: goalkeeper
description: >
  Turn a vague goal into a bounded, evidence-first Goal Contract (v2) before any
  agent runs. Writes .goalkeeper/ state (canonical state.json + generated
  goal.md), picks a domain (code/research/writing/ops), defines typed validators,
  risk/approval gates, a loop mode, and a completion gate, then emits a native
  /goal command. Use BEFORE refactors, migrations, research sweeps, writing, ops
  tasks, or any multi-turn work where "done" must be proven. Trigger on "refactor
  X", "research Y", "keep working until tests pass", or /goalkeeper.
---

# Goalkeeper — author a Goal Contract, then hand off to native /goal

You set up a **contract, don't vibe** workflow. The deliverable is a precise,
bounded Goal Contract plus a ready-to-run `/goal` command. You are NOT yet doing
the implementation work.

The user's request is:

> $ARGUMENTS

If empty, ask for the objective. Treat the request as a *messy draft* to turn into
a measurable contract — do not act on it literally yet.

## Principle

Don't build a raw infinite loop. Both Claude Code and Codex have first-party
goal execution. Your job is the layer above it: define **objective, scope,
typed validators, risk, loop mode, and a completion gate**, then emit a native
`/goal` handoff so completion is proven, not claimed.

## Workflow

### 1. Pick a domain + template
Choose the domain that fits (`code`, `research`, `writing`, `ops`) and the closest
template:

```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" init --template code-refactor -o "<objective>"
```

Templates: `code-refactor, bugfix, research, writing, recurring-maintenance,
data-quality, incident-review`. For code, also mine the repo:

```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" detect
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" seed
```

Read any listed policy files (AGENTS.md/CLAUDE.md/CONTRIBUTING.md) and fold their
rules in.

### 2. Shape the contract (dotted-path `set`)
```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" set scope.allowed_resources "src/auth/**,tests/auth/**"
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" set scope.forbidden_resources ".github/**,package-lock.json"
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" set scope.forbidden_actions "change public behavior,add production dependencies"
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" set risk.level medium
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" detect --apply        # writes command validators
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" checkpoint --add "Auth routes use the new token API"
```

Add typed validators beyond shell commands where they help (`git_diff` for scope,
`file_contains` for a banned pattern, `human_approval`/`rubric` for subjective or
high-risk work). For high/critical risk or external side effects, set
`risk.approval_required_before` — completion will require a recorded approval.

### 3. Gate the contract, then emit /goal
```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" validate-contract --strict
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" doctor
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" set completion.status active
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" render --format prompt
```

Show the generated `/goal` to the user. `goal.md` is generated — never hand-edit it.

### 4. Recommend next steps
- Run the `/goal` (Claude Code ≥ v2.1.139; on Codex `codex features enable goals`).
- Use **goalkeeper-split** only if disjoint parallel work genuinely helps.
- During work, record proof with `goalkeeper run "<cmd>"` and
  `goalkeeper checkpoint --id … --evidence … --met`.
- Before accepting, run **goalkeeper-audit**, then `goalkeeper gate`,
  `goalkeeper complete --accepted-by <name>`, and `goalkeeper proof`.

## Guardrails
- Never produce an unbounded objective. Every objective needs a measurable
  done-state, a stop budget, and at least one required validator.
- `completion.status=complete` is set ONLY by `goalkeeper complete` after `gate`
  passes — never with `set`.
- The Stop hook enforces the gate by default for gated contracts (templates /
  `init --auto`): the turn is held open until the gate passes, bounded by
  `loop.max_turns`. Disable with `goalkeeper autocontinue off` / `GOALKEEPER_NO_STOP=1`.
- Do not start implementing in this skill — set up the contract and hand off.
