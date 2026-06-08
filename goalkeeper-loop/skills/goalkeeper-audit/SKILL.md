---
name: goalkeeper-audit
description: >
  Verify that the current diff actually satisfies the active Goal Contract
  before anyone accepts "done". Checks for evidence per checkpoint, scope drift
  (files changed outside allowed paths), forbidden-path changes, missing
  validation runs, and premature completion claims. Use when an agent says it is
  finished, before merging, or when invoked via /goalkeeper-audit. This is the
  verifier layer — be skeptical, demand evidence.
---

# Goalkeeper Audit — prove it, don't trust it

You are the **verifier**. Your job is to decide, adversarially, whether the work
in the current diff truly satisfies the contract in `.goalkeeper/`. Assume
"done" is a claim until proven by evidence.

## Workflow

### 1. Load the contract and score the diff
```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" status
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" score --json
```

The `score` helper computes, mechanically (diffing against the `base_ref`
captured when the goal started, and excluding `.goalkeeper/` itself):
- `files_outside_allowed_paths` — scope drift
- `forbidden_path_changes` — contract violations
- `validations_not_run` / `validations_failed` — read from the run ledger
- `checkpoints_without_evidence`
- `checkpoints_not_met`
- a 0–100 score and a PASS/REVIEW verdict.

(To compare against a specific point, pass `--base <ref>`.)

### 2. Run the actual validations (recorded)
Do not trust prior turns. Re-run every command in the contract's validation
surface **through the recorder** so `score` can confirm it actually ran and
passed:

```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" run "npm test -- tests/auth"
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" run "npm run typecheck"
```

Also run each targeted check named in `goal.md` (e.g. `rg` assertions that a
banned pattern is gone, that a new API is used everywhere it should be). Then
re-run `score` — `validations_not_run` and `validations_failed` should be empty.

### 3. Inspect for the failure modes
Read the diff (`git diff`) and check each:

1. **Evidence gap** — every checkpoint must map to concrete evidence (command
   output, file:line, or a link). No evidence ⇒ not met.
2. **Scope drift** — any file changed outside allowed paths? Justify or flag.
3. **Forbidden changes** — any forbidden path/action touched? This is a hard
   fail regardless of score.
4. **Missing validation** — a contract validation that was never run, or run
   and failed.
5. **Premature completion** — claims of "done" without passing validations, or
   checkpoints marked met without evidence.
6. **Hidden behavior change** — "preserve behavior" constraints violated
   (public API, serialized formats, error messages relied upon).

### 4. Record findings as evidence
For each verified checkpoint, write the evidence back so the ledger is honest:
```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" checkpoint --id cp1 --evidence "npm test -- tests/auth -> exit 0 (42 passed)" --met
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" log "AUDIT: scope clean, typecheck exit 0, 1 unmet checkpoint (cp3 no evidence)"
```

### 5. Verdict
Produce a clear verdict with the supporting evidence:

- **PASS** — only if score ≥ 80, zero forbidden changes, every checkpoint met
  with evidence, and every validation re-run exits 0. Then suggest marking
  `status complete`.
- **REVIEW / FAIL** — list each unmet item with the specific fix needed. Do not
  soften. If scope drift is justified, recommend updating the contract's allowed
  paths deliberately rather than silently accepting the drift.

## Guardrails
- Never declare PASS on the strength of a previous turn's word — re-run.
- A forbidden-path change is an automatic FAIL even if everything else passes.
- If validations cannot run (missing deps, needs credentials), report that as an
  inconclusive audit and pause — do not guess.
