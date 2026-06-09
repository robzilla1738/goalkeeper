"""The stdio MCP server: JSON-RPC handling and tool dispatch over a real contract."""
from __future__ import annotations

import json
import subprocess
import sys

from tests.conftest import CLI, load_state, run_cli


def _rpc(mid, method, params=None):
    msg = {"jsonrpc": "2.0", "id": mid, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def test_mcp_initialize_and_tools_list():
    from goalkeeper_core import mcp
    init = mcp.handle(_rpc(1, "initialize", {}))
    assert init["result"]["serverInfo"]["name"] == "goalkeeper"
    assert init["result"]["protocolVersion"]
    names = {t["name"] for t in mcp.handle(_rpc(2, "tools/list"))["result"]["tools"]}
    assert {"goalkeeper_status", "goalkeeper_run", "goalkeeper_gate",
            "goalkeeper_complete", "goalkeeper_proof", "goalkeeper_checkpoint"} <= names
    # notifications get no response
    assert mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    # unknown request -> method-not-found error
    assert mcp.handle(_rpc(3, "nope"))["error"]["code"] == -32601


def _active_command_contract(repo):
    run_cli(repo, "init", "-o", "Validate the change under src")
    run_cli(repo, "set", "scope.allowed_resources", "**")
    s = load_state(repo)
    s["validators"] = [{"id": "ok", "type": "command", "command": "true",
                        "pass_condition": "exit_zero", "required": True}]
    s["checkpoints"] = [{"id": "cp1", "description": "done", "evidence_required": "x",
                         "status": "met", "evidence": "e"}]
    (repo / ".goalkeeper" / "state.json").write_text(json.dumps(s, indent=2))
    run_cli(repo, "set", "completion.status", "active")


def _call(repo, monkeypatch, name, arguments=None):
    monkeypatch.chdir(repo)
    from goalkeeper_core import mcp
    resp = mcp.handle(_rpc(9, "tools/call", {"name": name, "arguments": arguments or {}}))
    return resp["result"]


def test_mcp_gate_run_complete_flow(repo, monkeypatch):
    _active_command_contract(repo)
    # gate is INCOMPLETE before evidence
    g0 = _call(repo, monkeypatch, "goalkeeper_gate")
    assert g0["structuredContent"]["verdict"] == "INCOMPLETE"
    # run records evidence through MCP
    r = _call(repo, monkeypatch, "goalkeeper_run", {"command": "true"})
    assert r["structuredContent"]["exit"] == 0
    # gate now COMPLETE
    g1 = _call(repo, monkeypatch, "goalkeeper_gate")
    assert g1["structuredContent"]["verdict"] == "COMPLETE"
    # complete records completion + proof
    c = _call(repo, monkeypatch, "goalkeeper_complete", {"accepted_by": "robert"})
    assert c["structuredContent"]["completed"] is True
    assert load_state(repo)["completion"]["status"] == "complete"
    assert (repo / ".goalkeeper" / "proof.md").exists()


def test_mcp_complete_refused_until_gate_passes(repo, monkeypatch):
    _active_command_contract(repo)  # no evidence yet
    c = _call(repo, monkeypatch, "goalkeeper_complete", {"accepted_by": "robert"})
    assert c["structuredContent"]["completed"] is False
    assert load_state(repo)["completion"]["status"] == "active"


def test_mcp_server_stdout_is_clean_jsonrpc(repo):
    # The run tool must not leak subprocess output onto the JSON-RPC stdout channel.
    # The marker lives in a script, not the command string, so it can only reach
    # stdout via a leak (not via the echoed command in the response).
    run_cli(repo, "init", "-o", "x")
    run_cli(repo, "set", "scope.allowed_resources", "**")
    run_cli(repo, "set", "completion.status", "active")
    (repo / "leak.sh").write_text("echo DEADBEEFMARKER\n")
    msgs = [
        _rpc(1, "initialize", {}),
        _rpc(2, "tools/call", {"name": "goalkeeper_run", "arguments": {"command": "sh leak.sh"}}),
    ]
    inp = "".join(json.dumps(m) + "\n" for m in msgs)
    proc = subprocess.run([sys.executable, str(CLI), "mcp"], cwd=repo,
                          input=inp, capture_output=True, text=True)
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert len(lines) == 2
    for ln in lines:
        json.loads(ln)  # every stdout line is a valid JSON-RPC response
    assert "DEADBEEFMARKER" not in proc.stdout  # subprocess output went to /dev/null
