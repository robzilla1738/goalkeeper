---
name: goalkeeper-audit
description: >
  Verify that the current work actually satisfies the active Goal Contract before
  anyone accepts "done". Re-runs validators through the recorder, scores the diff,
  checks scope/forbidden drift, checkpoint evidence, risk/approval gates, and the
  completion gate, and reports a verdict with the completion tier (N/6). Use when
  an agent says it is finished, before merging, or via /goalkeeper-audit. Be
  skeptical; demand evidence.
---

# Goalkeeper Audit — prove it, don't trust it

You are the **verifier**. Decide, adversarially, whether the work satisfies the
contract in `.goalkeeper/`. Assume "done" is a claim until proven by evidence.

## Workflow

### 1. Re-run the validations (recorded)
Do not trust prior turns. Re-run every command-type validator **through the
recorder** so the gate can confirm it ran and passed:

```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" run "npm test -- tests/auth"
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" run "npm run typecheck"
```

Also run any targeted checks named in the contract (e.g. `rg` assertions that a
banned pattern is gone).

### 2. Score + gate
```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" score --json
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" gate
```

`gate` mechanically checks (diffing against `base_ref`, excluding `.goalkeeper/`):
- required validators pass / unavailable / failed;
- checkpoints met **and** carry evidence;
- scope drift + forbidden-path changes;
- risk/approval gates (high/critical risk and external side effects need approval);
- the achieved **completion tier (0–6)**.

### 3. Inspect for failure modes
Read `git diff` and check: evidence gap (no evidence ⇒ not met), scope drift,
forbidden changes (hard fail), missing/failed validation, premature completion,
hidden behavior change (a "preserve behavior" constraint violated).

### 4. Record findings + approvals
```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" checkpoint --id cp1 --evidence "npm test -> exit 0 (42 passed)" --met
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" approve "high-risk-signoff" --by <reviewer>   # if high/critical risk
python3 "${CLAUDE_PLUGIN_ROOT}/bin/goalkeeper" log "AUDIT: scope clean, typecheck exit 0, cp3 lacks evidence"
```

### 5. Verdict
- **PASS** — only if `gate` exits 0 (zero blockers). Then:
  `goalkeeper complete --accepted-by <name>` and `goalkeeper proof`.
- **REVIEW / FAIL** — list each blocker with the specific fix. A forbidden-path
  change is an automatic FAIL. Always state the completion tier so confidence is
  honest.

## Guardrails
- Never declare PASS on the strength of a previous turn's word — re-run.
- If validations cannot run (missing deps/credentials), report an inconclusive
  audit and pause — do not guess. That is a `validator_unavailable` pause, not a pass.
- Scope drift that is genuinely needed should become a deliberate contract
  amendment (`contract-unlock --reason …`), not silent acceptance.
