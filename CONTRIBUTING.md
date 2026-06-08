# Contributing to Goalkeeper

Thanks for your interest! This is a small, dependency-free project — easy to hack
on. The engine lives in [`goalkeeper_core/`](./goalkeeper_core); host wiring lives
under [`hosts/`](./hosts).

## Dev setup

Requirements: **Python 3.9+** and **git**. No runtime dependencies; the only dev
dependency is `pytest`.

```bash
git clone https://github.com/robzilla1738/goalkeeper
cd goalkeeper
pip install pytest
pytest -q
```

## Project layout

| Path | What it is |
|------|------------|
| `goalkeeper_core/` | Domain-neutral engine: contract, state, schema, ledger, validators, tiers, gate, proof, risk, loop, packets, render, adapters |
| `bin/goalkeeper`, `bin/goalkeeper_hook.py` | Thin entrypoints (sys.path bootstrap → Core) |
| `hosts/claude`, `hosts/codex` | Plugin packages: skills, agents, hooks |
| `hosts/github-actions`, `hosts/shell` | CI gate Action/workflow; bare-shell entrypoint |
| `schema/` | Published JSON Schema for the v2 contract |
| `examples/` | Runnable v2 example contracts |
| `tests/{unit,integration,hooks}/` | The test suite |
| `docs/` | Reference docs (concepts/schemas/adapters/security/playbooks) |

See [docs/concepts/ARCHITECTURE.md](./docs/concepts/ARCHITECTURE.md) for how the
pieces fit together.

## Before you open a PR

Run the same checks CI runs (from the repo root):

```bash
python -m compileall -q goalkeeper_core
python -m py_compile bin/goalkeeper bin/goalkeeper_hook.py
python -c "import json; [json.load(open(f)) for f in ['hosts/claude/.claude-plugin/plugin.json','hosts/codex/.codex-plugin/plugin.json','hosts/claude/hooks/hooks.json','schema/goalkeeper.contract.schema.json']]"
for d in examples/*/; do (cd "$d" && python ../../bin/goalkeeper validate-contract --strict); done
pytest -q
```

CI (`.github/workflows/ci.yml`) runs these on Python 3.9, 3.11, and 3.12.

## Guidelines

- **Stay dependency-free.** Core, the CLI, and the hook must run on a clean Python 3
  stdlib. Don't add third-party imports (pytest is dev-only). Remote validators
  degrade to "unavailable" rather than importing drivers — keep it that way.
- **Keep the hook un-crashable.** It must never raise into the host; wrap risky work
  and exit `0` on failure. Add a test for any new event handling.
- **Match the existing style** — module docstrings, small helpers, type hints with
  `from __future__ import annotations`.
- **Add tests** for any behavior change. Update `docs/` and `CHANGELOG.md`.
- **Don't commit runtime `.goalkeeper/`** state (git-ignored), except the curated
  `examples/**/.goalkeeper/state.json` contracts.

### Common contributions

- **Add a validator type**: a handler under `goalkeeper_core/validators/`, register it
  in `validators/__init__.py`, add it to the schema enum, and add a unit test.
- **Add an adapter (domain)**: a module under `goalkeeper_core/adapters/` implementing
  the `Adapter` interface, registered in `adapters/__init__.py`. See
  [docs/adapters/WRITING_AN_ADAPTER.md](./docs/adapters/WRITING_AN_ADAPTER.md).
- **Add a stack preset**: append to `PRESETS` in `goalkeeper_core/detect.py`.
- **Add a destructive-command pattern**: extend `DESTRUCTIVE_PATTERNS` in
  `bin/goalkeeper_hook.py` and add a `test_pretooluse_blocks_*` case.

## Reporting issues

Open a GitHub issue with the host (Claude Code / Codex) and version, the command or
event, and observed vs expected behavior. For security concerns, see
[SECURITY.md](./SECURITY.md).

By contributing you agree your contributions are licensed under the project's
[MIT License](./LICENSE).
