# Changelog

## 0.3.0 — Evidence-first control plane (Core + adapters + hosts)

A major evolution from "loop plugin" to a domain-neutral contract and proof engine.

### Restructured
- Split the single CLI into **Goalkeeper Core** (`goalkeeper_core/`, stdlib-only):
  `contract`, `state`, `schema`, `ledger`, `gitio`, `validators/`, `tiers`, `gate`,
  `proof`, `risk`, `loop`, `packets`, `render`, `detect`, `templates`, `adapters/`.
- Thin entrypoints `bin/goalkeeper` + `bin/goalkeeper_hook.py` bootstrap the package
  onto `sys.path` (no install). Moved the plugin into `hosts/claude` and `hosts/codex`;
  added `hosts/github-actions` (gate Action + PR-comment workflow) and `hosts/shell`.

### Added — Universal Goal Contract v2 (clean break; no v1 migration)
- Nested contract: `goal/scope/validators/checkpoints/loop/risk/evidence/completion`.
- **Validator registry**: `command, git_diff, file_exists, file_contains, http_check,
  github_check, ticket_state, sql_query, rubric, human_approval` (remote types degrade
  to unavailable + manual evidence rather than importing drivers).
- **Verifier tiers (0–6)** computed as monotone gates and displayed by score/gate/proof.
- **Completion gate**: `gate` exits 0 only when complete; `complete` is the sole writer
  of `completion.status=complete` and only after the gate passes.
- **Proof bundles**: `proof` writes `.goalkeeper/proof.{md,json}` + `artifacts/`.
- **Risk classes + approval gates** (`approve`); high/critical and external-side-effect
  work cannot complete without recorded approval.
- **Loop modes** (`goal_until_pass`, `repair_until_pass`, `research_until_covered`,
  `watch_until_event`, `scheduled_recurring`, `human_review_loop`,
  `multi_agent_packet_loop`) with a gate-aware Stop hook.
- **Contract locking/amendments** (`contract-lock`/`-unlock`/`-diff`), **packet executor**
  (`split --write-packets`, `packets list|run|reconcile`), **templates** (`init --template`),
  `render` (goal.md is now generated — kills drift), `validate-contract [--strict]`, and a
  published JSON Schema (`schema/goalkeeper.contract.schema.json`).
- **Adapters**: `code`, `research`, `writing`, `ops`, selected by `goal.domain`.
- Rewrote docs (concepts/schemas/adapters/security/playbooks), skills, and the test
  suite (unit/integration/hooks) for v2.

## 0.2.1 — Documentation

- Added a full `docs/` set: `ARCHITECTURE.md`, `GOAL_CONTRACT.md` (incl.
  `state.json` schema), `CLI.md` (every command/flag/exit code), `HOOKS.md`
  (events, JSON I/O, security model).
- Added root `CONTRIBUTING.md` and `SECURITY.md`; rewrote the top-level README
  as a public-repo landing page with CI/License badges and doc links.
- Corrected README inaccuracies: hook blocks forbidden *paths* only (not
  actions), test count (33), `SubagentStart` wiring.
- Removed the unused `--host` flag from `generate-goal`.

## 0.2.0 — Hardening pass

Real-world correctness, cross-host accuracy, and test coverage.

### Fixed (correctness)
- **Claude Code Stop hook**: guidance now goes in `hookSpecificOutput.additionalContext`
  (the `reason` field is ignored by the model), so bounded auto-continue actually
  tells the agent what's left. Both fields are emitted for portability.
- **Skill invocation docs** corrected to the real namespaced form
  `/goalkeeper-loop:goalkeeper` (Claude) and `$goalkeeper` (Codex).
- **`goalkeeper` skill** now captures the user's request via `$ARGUMENTS`.
- **Plugin agent frontmatter** `tools` switched to JSON-array form; `agents` in the
  Claude manifest is now an explicit file list.
- **`SubagentStart`** wired into `hooks.json` for subagent context injection.

### Fixed (Codex cross-compatibility)
- Removed the invalid `agents` field from the Codex manifest (Codex manifests
  package skills/MCP/apps + hooks only) and moved presentation fields under
  `interface`.
- Rewrote `codex-agents/*.toml` to the real Codex format: `developer_instructions`
  + `sandbox_mode` (`read-only`/`workspace-write`) + `approval_policy`; removed the
  non-existent `tools`/`read_only`/`instructions` fields.
- Documented Codex caveats: flaky plugin-bundled hooks, Bash-only hook firing, no
  CLI `/loop`, and `CLAUDE_PLUGIN_ROOT` compatibility alias.

### Fixed (scoring trust)
- `score` now diffs against a `base_ref` captured at goal start (three-dot
  merge-base), excludes `.goalkeeper/` from results, includes untracked files via
  `git status --porcelain`, and dedupes. `--base` default no longer overrides the
  stored baseline.
- Removed the naive, false-positive-prone "forbidden action" keyword blocking from
  the hook; action enforcement is now via `goalkeeper-audit` reading the diff.

### Added
- **`goalkeeper run "CMD"`** — authoritative validation recorder writing
  `.goalkeeper/runs.jsonl`; `score` reports `validations_not_run` / `validations_failed`.
- **`goalkeeper doctor`** — contract-quality + consistency metrics (DSPy-style).
- **`goalkeeper seed`** — mines `AGENTS.md`/`CLAUDE.md`/CI/build dirs to seed the contract.
- **`tests/`** — 33-test pytest suite (CLI helpers, scoring, run ledger, doctor,
  hook end-to-end) plus a GitHub Actions CI workflow on Python 3.9–3.12.

## 0.1.0 — Initial scaffold
- Dual manifests, three skills (goalkeeper / goalkeeper-split / goalkeeper-audit),
  conservative cross-host hook, dependency-free `goalkeeper` CLI, Claude/Codex
  agents, README + local marketplace example.
