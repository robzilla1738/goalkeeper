"""Goalkeeper Core — domain-neutral contract & proof engine.

This package is intentionally dependency-free (Python 3 stdlib only) so it runs
the same way inside Claude Code, Codex, CI, or a bare shell. It owns the
Universal Goal Contract (v2) schema, state machine, ledger, validator registry,
verifier tiers, completion gate, proof bundles, loop policy, risk gates, and the
subagent packet model. Domain knowledge lives in `goalkeeper_core.adapters`;
host wiring (plugins, hooks, CI) lives under `hosts/`.
"""
from __future__ import annotations

__version__ = "0.4.0"
SCHEMA_VERSION = 2
