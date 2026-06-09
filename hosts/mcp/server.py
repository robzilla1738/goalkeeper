#!/usr/bin/env python3
"""Standalone launcher for the Goalkeeper stdio MCP server.

Bootstraps `goalkeeper_core` onto sys.path (honoring GOALKEEPER_CORE_HOME, else
walking up from here) and runs the server. Equivalent to `goalkeeper mcp`.
"""
import os
import sys


def _bootstrap():
    here = os.path.dirname(os.path.realpath(__file__))
    override = os.environ.get("GOALKEEPER_CORE_HOME")
    candidates = [override] if override else []
    cur = here
    for _ in range(8):
        candidates.append(cur)
        cur = os.path.dirname(cur)
    for root in candidates:
        if root and os.path.isfile(os.path.join(root, "goalkeeper_core", "__init__.py")):
            if root not in sys.path:
                sys.path.insert(0, root)
            return
    sys.path.insert(0, os.path.abspath(os.path.join(here, "..", "..")))


_bootstrap()

from goalkeeper_core import mcp  # noqa: E402

if __name__ == "__main__":
    try:
        sys.exit(mcp.serve())
    except KeyboardInterrupt:
        sys.exit(0)
