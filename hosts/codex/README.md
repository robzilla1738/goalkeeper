# Goalkeeper — Codex host

The Codex plugin package: skills, custom-agent prompts, and hooks. It calls the
shared `goalkeeper_core` engine through the same dependency-free entrypoints as
the shell and Claude hosts.

## Install / path setup

Use one of these paths before invoking the Codex skills:

```bash
# preferred local install
python3 bin/goalkeeper install codex
python3 bin/goalkeeper install shell

# or point skills at an explicit entrypoint
export GOALKEEPER_BIN=/absolute/path/to/goalkeeper/bin/goalkeeper

# for copied plugin packages whose bin/ cannot walk up to the repo root
export GOALKEEPER_CORE_HOME=/absolute/path/to/goalkeeper
```

Hook commands also honor `GOALKEEPER_HOOK` when you need to point at a specific
`goalkeeper_hook.py`.

## Contents

- **Skills** — `goalkeeper` (author a v2 contract + emit `/goal`),
  `goalkeeper-split` (disjoint subagent packets), `goalkeeper-audit`
  (verify + gate before "done").
- **Codex agents** — researcher, scoped implementer, and verifier prompt configs.
- **Hooks** — `hooks/hooks.json` wires `bin/goalkeeper_hook.py`: contract
  injection, destructive/forbidden command blocking, and a gate-aware Stop
  (off by default).
