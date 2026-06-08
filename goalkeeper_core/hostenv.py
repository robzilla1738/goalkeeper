"""Host detection (Claude Code vs Codex vs generic)."""
from __future__ import annotations

import os


def detect_host() -> str:
    if os.environ.get("CODEX_HOME") or os.environ.get("CODEX_SANDBOX"):
        return "codex"
    if os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("CLAUDECODE"):
        return "claude"
    return "generic"
