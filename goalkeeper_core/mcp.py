"""Minimal stdlib MCP server exposing Goalkeeper as first-class tools.

Speaks newline-delimited JSON-RPC 2.0 over stdio (the MCP stdio transport) with
zero third-party dependencies. Each tool wraps a core function and returns
structured JSON, so an agent calls `gate`/`run`/`checkpoint`/`complete` directly
instead of shelling out and parsing CLI stdout. This is the most portable surface
(works even on hosts whose hook support is absent or untrusted) and complements
the hooks: hooks *force* the gate, MCP *enables* the agent to drive it.

Run via `goalkeeper mcp` or `python3 hosts/mcp/server.py`.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from . import gate as gate_mod
from . import proof as proof_mod
from .ledger import log as ledger_log
from .ledger import run_command
from .paths import find_root
from .state import load_state, save_state

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "goalkeeper"

_OBJ: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}

TOOLS: list[dict] = [
    {
        "name": "goalkeeper_status",
        "description": "Summarize the active Goal Contract: objective, completion status, "
                       "checkpoint progress, scope, and the suggested next action.",
        "inputSchema": _OBJ,
    },
    {
        "name": "goalkeeper_run",
        "description": "Run a validation command and record its exit code + bounded output "
                       "into runs.jsonl as evidence the gate reads.",
        "inputSchema": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "shell command to run"}},
            "required": ["command"],
            "additionalProperties": False,
        },
    },
    {
        "name": "goalkeeper_checkpoint",
        "description": "Set evidence on a checkpoint and optionally mark it met.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "checkpoint id, e.g. cp1"},
                "evidence": {"type": "string"},
                "met": {"type": "boolean", "default": False},
            },
            "required": ["id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "goalkeeper_gate",
        "description": "Evaluate the completion gate. Returns verdict (COMPLETE/INCOMPLETE), "
                       "tier (0-6), and blockers. Set rerun=true to re-execute required command "
                       "validators from a clean state (earns tier 4).",
        "inputSchema": {
            "type": "object",
            "properties": {"rerun": {"type": "boolean", "default": False}},
            "additionalProperties": False,
        },
    },
    {
        "name": "goalkeeper_complete",
        "description": "Record completion (only if the gate passes) and write the proof bundle. "
                       "Requires accepted_by; refused for human-gated contracts unless a named human accepts.",
        "inputSchema": {
            "type": "object",
            "properties": {"accepted_by": {"type": "string", "description": "who accepts completion"}},
            "required": ["accepted_by"],
            "additionalProperties": False,
        },
    },
    {
        "name": "goalkeeper_proof",
        "description": "Write and return the proof bundle (proof.md/proof.json) for the current contract.",
        "inputSchema": _OBJ,
    },
]


# --------------------------------------------------------------------------- #
# Tool implementations
# --------------------------------------------------------------------------- #
def _need_state(root: Path) -> dict:
    state = load_state(root)
    if not state:
        raise ValueError("no .goalkeeper/state.json; run `goalkeeper init` first")
    return state


def _status(state: dict, root: Path) -> dict:
    goal = state.get("goal", {})
    cps = state.get("checkpoints", []) or []
    met = sum(1 for c in cps if isinstance(c, dict) and c.get("status") == "met")
    g = gate_mod.evaluate_gate(state, root)
    return {
        "objective": goal.get("objective"),
        "domain": goal.get("domain"),
        "completion_status": state.get("completion", {}).get("status"),
        "checkpoints": {"met": met, "total": len(cps)},
        "scope": state.get("scope", {}),
        "verdict": g["verdict"],
        "tier": g["tier"],
        "blockers": [{"code": c, "detail": d} for c, d in g["blockers"]],
    }


def _gate(state: dict, root: Path, rerun: bool) -> dict:
    if rerun:
        for v in state.get("validators", []):
            if isinstance(v, dict) and v.get("required") and v.get("type") == "command" and v.get("command"):
                _quiet_run(v["command"], root, record_extra={"rerun": True})
    g = gate_mod.evaluate_gate(state, root)
    return {"verdict": g["verdict"], "tier": g["tier"],
            "blockers": [{"code": c, "detail": d} for c, d in g["blockers"]]}


def _quiet_run(cmd: str, root: Path, record_extra: dict | None = None) -> int:
    """run_command with output sent to /dev/null so it can't corrupt stdio JSON-RPC."""
    with open(os.devnull, "wb") as devnull:
        return run_command(cmd, root, record_extra=record_extra, out_stream=devnull, err_stream=devnull)


def dispatch_tool(name: str, args: dict) -> dict:
    root = find_root()
    state = _need_state(root)
    if name == "goalkeeper_status":
        return _status(state, root)
    if name == "goalkeeper_run":
        cmd = args.get("command")
        if not cmd:
            raise ValueError("command is required")
        rc = _quiet_run(cmd, root)
        return {"command": cmd, "exit": rc, "recorded": True}
    if name == "goalkeeper_checkpoint":
        cps = state.get("checkpoints", []) or []
        target = next((c for c in cps if isinstance(c, dict) and c.get("id") == args.get("id")), None)
        if not target:
            raise ValueError(f"no checkpoint with id {args.get('id')!r}")
        if args.get("evidence") is not None:
            target["evidence"] = args["evidence"]
        if args.get("met"):
            target["status"] = "met"
        save_state(state, root)
        ledger_log(f"checkpoint {target['id']} {target.get('status')}: {target.get('evidence', '')}", root)
        return {"id": target["id"], "status": target.get("status"), "evidence": target.get("evidence", "")}
    if name == "goalkeeper_gate":
        return _gate(state, root, bool(args.get("rerun")))
    if name == "goalkeeper_complete":
        accepted_by = args.get("accepted_by")
        if not accepted_by:
            raise ValueError("accepted_by is required")
        from .loop import requires_human_signoff
        if requires_human_signoff(state) and accepted_by.startswith("auto:"):
            raise ValueError("this contract requires a named human to accept completion")
        g = gate_mod.finalize(state, root, accepted_by)
        if g is None:
            blockers = gate_mod.evaluate_gate(state, root)["blockers"]
            return {"completed": False, "reason": "gate not passing",
                    "blockers": [{"code": c, "detail": d} for c, d in blockers]}
        save_state(state, root)
        proof_mod.write_bundle(state, root, fmt="both")
        return {"completed": True, "tier": g["tier"], "accepted_by": accepted_by}
    if name == "goalkeeper_proof":
        return proof_mod.write_bundle(state, root, fmt="both")
    raise ValueError(f"unknown tool: {name}")


# --------------------------------------------------------------------------- #
# JSON-RPC plumbing
# --------------------------------------------------------------------------- #
def _result(mid: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def _tools_call(mid: Any, params: dict) -> dict:
    name = params.get("name", "")
    args = params.get("arguments") or {}
    try:
        out = dispatch_tool(name, args)
    except Exception as exc:  # surface as a tool error, not a transport error
        return _result(mid, {"content": [{"type": "text", "text": f"error: {exc}"}], "isError": True})
    return _result(mid, {
        "content": [{"type": "text", "text": json.dumps(out, indent=2)}],
        "structuredContent": out,
    })


def handle(msg: dict) -> dict | None:
    """Handle one JSON-RPC message; returns a response dict, or None for notifications."""
    method = msg.get("method")
    mid = msg.get("id")
    if method == "initialize":
        return _result(mid, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": __version__},
        })
    if method == "ping":
        return _result(mid, {})
    if method == "tools/list":
        return _result(mid, {"tools": TOOLS})
    if method == "tools/call":
        return _tools_call(mid, msg.get("params") or {})
    if mid is None:
        return None  # notification (e.g. notifications/initialized): no response
    return _error(mid, -32601, f"method not found: {method}")


def serve(stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict):
            continue
        resp = handle(msg)
        if resp is not None:
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()
    return 0
