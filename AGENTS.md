# AGENTS.md — context for AI agents working on Goalkeeper

This file orients an AI (or human) contributor. Read it before changing code.
Goalkeeper's own `goalkeeper seed` looks for `AGENTS.md`/`CLAUDE.md`, so keep this
accurate.

## What this project is

Goalkeeper is an **evidence-first control plane for agentic work**: it turns a vague
goal into a bounded **contract**, lets an agent work inside it, and **refuses to call
the work done until there is evidence** — gated by the best available verifier
(deterministic, external, rubric, or human). Coding is the first wedge; the engine is
domain-neutral via adapters.

Core principle: **the LLM decides, deterministic code verifies.** Never make the
verifier trust the agent's word — proof is a recorded validation run, bounded
output artifacts, a clean diff, checkpoint evidence, and (where required) a human
approval.

## Hard constraints (do not break)

1. **Dependency-free runtime.** `goalkeeper_core/`, `bin/goalkeeper`, and
   `bin/goalkeeper_hook.py` must run on a clean Python 3.9+ stdlib. No third-party
   imports. `pytest` is dev-only; `pyproject.toml` is a dev/CI convenience and is
   never required at runtime.
2. **Remote validators degrade, never import drivers.** `github_check`,
   `ticket_state`, `sql_query` (and `http_check` unless `GOALKEEPER_ALLOW_NET=1`)
   return `available=False, passed=None` instead of importing `requests`/a DB driver.
   A required-but-unavailable validator is a *pause*, not a false pass.
3. **`completion.status=complete` is written ONLY by `goalkeeper complete`**, and only
   after `goalkeeper gate` passes. `set` refuses it.
4. **state.json is canonical; goal.md is generated** by `render`. Never hand-edit
   goal.md or teach the agent to.
5. **The hook must never crash the host.** Any internal error exits 0 ("do nothing").

## Repository map

```
goalkeeper_core/            # the engine (stdlib only) — the IP
  cli.py                    # argparse wiring + every cmd_* (dispatch layer)
  contract.py               # v2 default skeleton, lock/unlock/amendments, hashing
  state.py                  # load/save state.json, dotted-path get/set, coercion
  schema.py                 # hand-rolled structural validator (+ strict cross-field)
  ledger.py                 # runs.jsonl / artifacts / work_log; run_command, latest_run
  gitio.py  matching.py     # git helpers + changed_files; glob matching
  validators/               # registry: base.py + local.py + deferred.py + human.py
  evaluation.py             # build EvalContext, evaluate_all, scope/forbidden helpers
  tiers.py                  # compute_tier (0-6 monotone gates)
  gate.py                   # evaluate_gate -> {verdict, tier, blockers}
  proof.py                  # proof.md / proof.json / artifacts bundle
  risk.py                   # risk_blockers, record_approval
  loop.py                   # decide_stop (Stop-hook engine), loop-mode semantics
  packets.py                # split/list/run/reconcile, disjoint write-sets
  render.py                 # goal.md / /goal prompt / json
  detect.py templates.py    # stack presets + seed; init --template presets
  autocontract.py           # init --auto / adopt from repo facts and current diff
  quality.py                # shared doctor/gate contract-quality checks
  install.py hostdoctor.py  # local symlink installer + host diagnostics
  smoke.py                  # isolated proof-flow and host-hook smoke checks
  adapters/                 # code, research, writing, ops (get_adapter by goal.domain)
bin/                        # thin entrypoints: sys.path bootstrap -> import goalkeeper_core
schema/                     # published JSON Schema for the v2 contract
hosts/{claude,codex,github-actions,shell}/   # host wiring (plugins, CI Action, shell)
examples/*/.goalkeeper/state.json            # runnable v2 contracts (tracked despite .gitignore)
docs/{concepts,schemas,adapters,security,real-world-playbooks}/
tests/{unit,integration,hooks}/              # pytest, stdlib only
```

The import bootstrap in `bin/*` resolves `goalkeeper_core` by walking up from the
entrypoint's realpath, or via `GOALKEEPER_CORE_HOME`. Both the CLI and the hook
import the same Core — don't duplicate logic into the hook.

## How to run / verify

```bash
pip install pytest          # dev only
pytest -q                   # full suite (57 cases; 3.9/3.11/3.12 in CI)
python3 -m compileall -q goalkeeper_core
python3 bin/goalkeeper --version
python3 bin/goalkeeper host doctor all --json
python3 bin/goalkeeper smoke core --json
```

CI: `.github/workflows/ci.yml` (compile + manifest JSON + `validate-contract --strict`
over every example + pytest). Keep it green.

## Conventions

- Style: module docstrings, small helpers, `from __future__ import annotations`, type
  hints. Match surrounding code.
- Every new feature module ships a unit test for its pure logic and at least one
  subprocess integration test through `bin/goalkeeper` (proves the bootstrap).
- Update `docs/` + `CHANGELOG.md` on any behavior change.
- Don't commit runtime `.goalkeeper/` (git-ignored) except the curated
  `examples/**/.goalkeeper/state.json`.

## Adding things (the common cases)

- **Validator type**: add a handler in `goalkeeper_core/validators/`, register it in
  `validators/__init__.py:REGISTRY`, add its `type` to the schema enum (`schema.py`
  pulls from `known_types()`, but also update `schema/goalkeeper.contract.schema.json`),
  set `tier_on_pass`, add a unit test. Decide can_run_locally honestly.
- **Adapter (domain)**: a module in `goalkeeper_core/adapters/` implementing `Adapter`,
  registered in `adapters/__init__.py`. See `docs/adapters/WRITING_AN_ADAPTER.md`.
- **Template**: add to `goalkeeper_core/templates.py:TEMPLATES`; add an example +
  ensure `validate-contract --strict` passes.

## Status & roadmap (what's done / what's open)

**Done (v0.4.0):** v2 contract + JSON Schema + `validate-contract`; validator registry;
verifier tiers; `gate`/`complete`; strict gate quality checks; bounded run-output
artifacts; proof bundles; risk/approval gates + `approve`; loop modes + gate-aware
Stop hook; contract lock/amendments; packet executor; templates; adapters
(code/research/writing/ops); `init --auto`/`adopt`; symlink installer; host doctor;
isolated smoke checks; render (goal.md generated); hosts for
claude/codex/github-actions/shell; rewritten docs/skills/tests; runnable examples.

**Open / next:**
- **Standalone plugin packaging.** The local installer uses symlinks to this checkout.
  Marketplace-copied installs still need a release-time decision: vendor
  `goalkeeper_core` into `hosts/*`, or ship a bootstrap installer.
- **Live host validation.** Isolated CLI and hook smoke tests pass, but Goalkeeper has
  not yet been exercised in a long Claude Code/Codex session with real skill
  invocation and Stop-hook continuation.
- **External validators.** `github_check`/`ticket_state`/`sql_query` are deferred/manual.
  If you wire real execution, do it behind an opt-in env flag and keep the stdlib-only
  default path intact (mirror the `http_check` + `GOALKEEPER_ALLOW_NET` pattern).
- **Budgets.** `loop.max_wall_time_minutes`/`max_cost_usd` are only enforced where the
  host exposes elapsed/cost; turn budget is always enforced.
- **Packet concurrency** is experimental — `packets reconcile` is the safety net, not a
  lock. Don't launch overlapping write-sets.

## Gotchas

- Git fixtures must disable signing (`git -c commit.gpgsign=false`) — see
  `tests/conftest.py`.
- `gate` diffs against `base_ref` (captured at init / when status first goes active),
  excluding `.goalkeeper/`. If `base_ref` is empty it falls back to `HEAD`.
- The seatbelt hook blocks obvious destructive/forbidden `Bash` only — it is **not** a
  sandbox. Real isolation is the host's job.

The full plan that produced v0.4.0 lives in the PR/commit history; the design rationale
is in `docs/concepts/ARCHITECTURE.md`.
