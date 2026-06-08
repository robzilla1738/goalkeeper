# Changelog

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
