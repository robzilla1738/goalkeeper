"""Hook behavior: context injection, command blocking, gate-aware Stop."""
from __future__ import annotations

import json

from tests.conftest import load_state, run_cli, run_hook


def _init_active(repo):
    run_cli(repo, "init", "-o", "Refactor auth module")
    run_cli(repo, "set", "scope.allowed_resources", "src/**")
    run_cli(repo, "set", "scope.forbidden_resources", ".github/**")
    run_cli(repo, "set", "completion.status", "active")


def test_session_start_injects_contract(repo):
    _init_active(repo)
    r = run_hook(repo, {"hook_event_name": "SessionStart", "cwd": str(repo)})
    out = json.loads(r.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "Refactor auth module" in ctx
    assert "src/**" in ctx


def test_pretooluse_blocks_destructive(repo):
    _init_active(repo)
    r = run_hook(repo, {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                        "tool_input": {"command": "git reset --hard HEAD~3"}, "cwd": str(repo)})
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_pretooluse_blocks_forbidden_path(repo):
    _init_active(repo)
    r = run_hook(repo, {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                        "tool_input": {"command": "echo x > .github/workflows/ci.yml"}, "cwd": str(repo)})
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_pretooluse_allows_safe(repo):
    _init_active(repo)
    r = run_hook(repo, {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                        "tool_input": {"command": "ls src"}, "cwd": str(repo)})
    assert r.stdout.strip() == ""


def test_stop_off_by_default(repo):
    _init_active(repo)
    r = run_hook(repo, {"hook_event_name": "Stop", "cwd": str(repo)})
    assert r.stdout.strip() == ""  # autocontinue off -> no output


def test_stop_continues_while_incomplete(repo):
    _init_active(repo)
    run_cli(repo, "checkpoint", "--add", "do work")
    run_cli(repo, "autocontinue", "on", "--max", "3")
    r = run_hook(repo, {"hook_event_name": "Stop", "cwd": str(repo)})
    out = json.loads(r.stdout)
    assert out.get("decision") == "block"  # continue
    assert load_state(repo)["loop_runtime"]["autocontinue_turns_used"] == 1


def test_stop_allows_stop_when_gate_passes(repo):
    run_cli(repo, "init", "-o", "x")
    run_cli(repo, "set", "scope.allowed_resources", "**")
    run_cli(repo, "set", "completion.status", "active")
    run_cli(repo, "autocontinue", "on", "--max", "3")
    # no validators, no checkpoints, scope clean -> gate COMPLETE -> stop (no output)
    r = run_hook(repo, {"hook_event_name": "Stop", "cwd": str(repo)})
    assert r.stdout.strip() == ""


def test_hook_survives_garbage_input(repo):
    _init_active(repo)
    r = run_hook(repo, {})
    assert r.returncode == 0
