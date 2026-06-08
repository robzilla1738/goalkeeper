# CLAUDE.md

Context for AI agents working on this repo lives in **[AGENTS.md](./AGENTS.md)** —
read it first. It covers the architecture, hard constraints (dependency-free runtime,
gate/complete invariants, canonical state.json), the file map, how to run tests, how to
add validators/adapters/templates, and the open roadmap.

Quick orientation:
- Engine: `goalkeeper_core/` (stdlib only). Entrypoints: `bin/goalkeeper`,
  `bin/goalkeeper_hook.py`. Hosts: `hosts/{claude,codex,github-actions,shell}/`.
- Run tests: `pip install pytest && pytest -q`.
- Key invariant: `completion.status=complete` is written only by `goalkeeper complete`,
  and only after `goalkeeper gate` passes.
