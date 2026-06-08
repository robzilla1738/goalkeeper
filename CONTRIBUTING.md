# Contributing to Goalkeeper Loop

Thanks for your interest! This is a small, dependency-free project — easy to hack
on. Everything lives under [`goalkeeper-loop/`](./goalkeeper-loop).

## Dev setup

Requirements: **Python 3.9+** and **git**. No runtime dependencies; the only dev
dependency is `pytest`.

```bash
git clone https://github.com/robzilla1738/goalkeeper
cd goalkeeper/goalkeeper-loop
pip install pytest
pytest -q
```

## Project layout

| Path | What it is |
|------|------------|
| `bin/goalkeeper` | The CLI (Python, no extension) — deterministic state + verification |
| `bin/goalkeeper_hook.py` | The cross-host hook |
| `hooks/hooks.json` | Wires the hook to host events |
| `skills/*/SKILL.md` | Instruction playbooks the model reads |
| `agents/*.md`, `codex-agents/*.toml` | Claude / Codex subagents |
| `tests/test_goalkeeper.py` | The full test suite |
| `docs/` | Reference docs |

See [docs/ARCHITECTURE.md](./goalkeeper-loop/docs/ARCHITECTURE.md) for how the
pieces fit together.

## Before you open a PR

Run the same checks CI runs:

```bash
cd goalkeeper-loop
python -m py_compile bin/goalkeeper bin/goalkeeper_hook.py     # syntax
python -c "import json; [json.load(open(f)) for f in ['.claude-plugin/plugin.json','.codex-plugin/plugin.json','hooks/hooks.json','examples/marketplace.json']]"
pytest -q                                                       # tests
```

CI (`.github/workflows/ci.yml`) runs these on Python 3.9, 3.11, and 3.12.

## Guidelines

- **Stay dependency-free.** The CLI and hook must run on a clean Python 3 stdlib.
  Don't add third-party imports (pytest is dev-only).
- **Keep the hook un-crashable.** It must never raise into the host; wrap risky
  work and exit `0` on failure. Add a test for any new event handling.
- **Match the existing style** — module docstrings, small helpers, type hints
  with `from __future__ import annotations`.
- **Add tests** for any behavior change (the suite covers both the CLI and the
  hook via subprocess). Update `docs/` and `CHANGELOG.md` when behavior changes.
- **Don't commit `.goalkeeper/`** state or `__pycache__` (both are git-ignored).

### Common contributions

- **Add a stack preset** (`detect`/`seed`): append to the `PRESETS` list in
  `bin/goalkeeper` (marker files + test/build/typecheck/lint commands) and add a
  `detect_stack` test.
- **Add a destructive-command pattern**: extend `DESTRUCTIVE_PATTERNS` in
  `bin/goalkeeper_hook.py` and add a `test_hook_blocks_*` case. Remember the
  security model — this is a seatbelt, not a sandbox.
- **Improve a skill**: edit the relevant `SKILL.md`; keep instructions concrete
  and reference the CLI rather than embedding logic.

## Reporting issues

Open a GitHub issue with the host (Claude Code / Codex) and version, the command
or event, and the observed vs expected behavior. For security concerns, see
[SECURITY.md](./SECURITY.md).

By contributing you agree your contributions are licensed under the project's
[MIT License](./LICENSE).
