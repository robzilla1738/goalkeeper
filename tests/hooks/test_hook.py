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
    # A bare `init` contract does not enforce (loop.enforce=False) -> Stop is silent.
    _init_active(repo)
    r = run_hook(repo, {"hook_event_name": "Stop", "cwd": str(repo)})
    assert r.stdout.strip() == ""


def _active_enforced_with_validator(repo):
    """An active, enforced contract with one unrun required validator + checkpoint."""
    run_cli(repo, "init", "-o", "Refactor the auth module under src/auth")
    run_cli(repo, "set", "scope.allowed_resources", "**")
    s = load_state(repo)
    s["loop"]["enforce"] = True
    s["validators"] = [{"id": "ok", "type": "command", "command": "true",
                        "pass_condition": "exit_zero", "required": True}]
    s["checkpoints"] = [{"id": "cp1", "description": "behavior preserved",
                         "evidence_required": "command output", "status": "pending", "evidence": ""}]
    (repo / ".goalkeeper" / "state.json").write_text(json.dumps(s, indent=2))
    run_cli(repo, "set", "completion.status", "active")


def test_stop_enforces_without_autocontinue(repo):
    # loop.enforce alone (no `autocontinue on`) holds the turn open while incomplete.
    _active_enforced_with_validator(repo)
    r = run_hook(repo, {"hook_event_name": "Stop", "cwd": str(repo)})
    out = json.loads(r.stdout)
    assert out.get("decision") == "block"
    assert load_state(repo)["loop_runtime"]["autocontinue_turns_used"] == 1


def test_no_stop_env_disables_enforcement(repo, monkeypatch):
    _active_enforced_with_validator(repo)
    import subprocess
    import sys
    from tests.conftest import HOOK
    env = {**__import__("os").environ, "GOALKEEPER_NO_STOP": "1"}
    r = subprocess.run([sys.executable, str(HOOK)], cwd=repo,
                       input=json.dumps({"hook_event_name": "Stop", "cwd": str(repo)}),
                       capture_output=True, text=True, env=env)
    assert r.stdout.strip() == ""  # kill switch -> no enforcement


def test_stop_continues_while_incomplete(repo):
    _init_active(repo)
    s = load_state(repo)
    s["validators"] = [{"id": "ok", "type": "command", "command": "true",
                        "pass_condition": "exit_zero", "required": True}]
    (repo / ".goalkeeper" / "state.json").write_text(json.dumps(s, indent=2))
    run_cli(repo, "run", "true")
    run_cli(repo, "checkpoint", "--add", "do work")
    run_cli(repo, "autocontinue", "on", "--max", "3")
    r = run_hook(repo, {"hook_event_name": "Stop", "cwd": str(repo)})
    out = json.loads(r.stdout)
    assert out.get("decision") == "block"  # continue
    assert load_state(repo)["loop_runtime"]["autocontinue_turns_used"] == 1


def test_stop_auto_completes_when_gate_passes(repo):
    run_cli(repo, "init", "-o", "x")
    run_cli(repo, "set", "scope.allowed_resources", "**")
    run_cli(repo, "set", "completion.status", "active")
    run_cli(repo, "autocontinue", "on", "--max", "3")
    s = load_state(repo)
    s["validators"] = [{"id": "ok", "type": "command", "command": "true",
                        "pass_condition": "exit_zero", "required": True}]
    (repo / ".goalkeeper" / "state.json").write_text(json.dumps(s, indent=2))
    run_cli(repo, "checkpoint", "--add", "done")
    run_cli(repo, "run", "true")
    run_cli(repo, "checkpoint", "--id", "cp1", "--evidence", "true -> exit 0", "--met")
    # passing gate on a non-human-gated contract -> auto-complete + proof bundle.
    r = run_hook(repo, {"hook_event_name": "Stop", "cwd": str(repo)})
    ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "completion recorded (auto:goalkeeper)" in ctx
    st = load_state(repo)
    assert st["completion"]["status"] == "complete"
    assert st["completion"]["accepted_by"] == "auto:goalkeeper"
    assert (repo / ".goalkeeper" / "proof.md").exists()


def test_stop_human_gated_prompts_for_named_acceptance(repo):
    run_cli(repo, "init", "-o", "Write the launch post in drafts/post.md")
    run_cli(repo, "set", "scope.allowed_resources", "**")
    s = load_state(repo)
    s["loop"]["enforce"] = True
    s["validators"] = [{"id": "review", "type": "human_approval",
                        "pass_condition": "approved:review", "required": True}]
    s["checkpoints"] = [{"id": "cp1", "description": "drafted", "evidence_required": "note",
                         "status": "met", "evidence": "draft done"}]
    (repo / ".goalkeeper" / "state.json").write_text(json.dumps(s, indent=2))
    run_cli(repo, "set", "completion.status", "active")
    run_cli(repo, "approve", "review", "--by", "robert")
    # gate passes (approval satisfies the validator) but a human must accept -> no auto-complete.
    r = run_hook(repo, {"hook_event_name": "Stop", "cwd": str(repo)})
    ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "complete --accepted-by" in ctx
    assert load_state(repo)["completion"]["status"] == "active"


def test_stop_loop_drives_incomplete_to_complete(repo):
    """End-to-end: the Stop gate holds the turn open, then closes it on a pass."""
    _active_enforced_with_validator(repo)
    # Turn 1: no evidence yet -> the hook forces continuation.
    r1 = run_hook(repo, {"hook_event_name": "Stop", "cwd": str(repo)})
    assert json.loads(r1.stdout).get("decision") == "block"
    assert load_state(repo)["completion"]["status"] == "active"
    # The agent records evidence and meets the checkpoint.
    run_cli(repo, "run", "true")
    run_cli(repo, "checkpoint", "--id", "cp1", "--evidence", "true -> exit 0", "--met")
    # Turn 2: gate passes -> auto-complete, proof written, loop closed.
    r2 = run_hook(repo, {"hook_event_name": "Stop", "cwd": str(repo)})
    assert "decision" not in json.loads(r2.stdout)  # not a continuation
    st = load_state(repo)
    assert st["completion"]["status"] == "complete"
    assert (repo / ".goalkeeper" / "proof.json").exists()


def test_pretooluse_denies_write_outside_scope(repo):
    _init_active(repo)  # allowed src/**, forbidden .github/**
    r = run_hook(repo, {"hook_event_name": "PreToolUse", "tool_name": "Edit",
                        "tool_input": {"file_path": str(repo / "lib" / "x.py")}, "cwd": str(repo)})
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "outside allowed scope" in out["permissionDecisionReason"]


def test_pretooluse_allows_write_within_scope(repo):
    _init_active(repo)
    r = run_hook(repo, {"hook_event_name": "PreToolUse", "tool_name": "Write",
                        "tool_input": {"file_path": str(repo / "src" / "auth.py")}, "cwd": str(repo)})
    assert r.stdout.strip() == ""


def test_pretooluse_denies_forbidden_path_write(repo):
    _init_active(repo)
    r = run_hook(repo, {"hook_event_name": "PreToolUse", "tool_name": "Edit",
                        "tool_input": {"file_path": str(repo / ".github" / "workflows" / "ci.yml")}, "cwd": str(repo)})
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "forbidden scope" in out["permissionDecisionReason"]


def test_pretooluse_denies_apply_patch_outside_scope(repo):
    # Codex edits go through apply_patch -> scope enforcement must reach them.
    _init_active(repo)
    patch = "*** Begin Patch\n*** Update File: lib/secret.py\n@@\n-x\n+y\n*** End Patch\n"
    r = run_hook(repo, {"hook_event_name": "PreToolUse", "tool_name": "apply_patch",
                        "tool_input": {"input": patch}, "cwd": str(repo)})
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "lib/secret.py" in out["permissionDecisionReason"]


def test_posttooluse_autocaptures_command_with_exit(repo):
    _init_active(repo)
    r = run_hook(repo, {"hook_event_name": "PostToolUse", "tool_name": "Bash",
                        "tool_input": {"command": "pytest -q"},
                        "tool_response": {"exit_code": 0}, "cwd": str(repo)})
    assert r.returncode == 0
    rec = json.loads((repo / ".goalkeeper" / "runs.jsonl").read_text().splitlines()[-1])
    assert rec["cmd"] == "pytest -q" and rec["exit"] == 0 and rec["source"] == "posttooluse"


def test_posttooluse_skips_when_exit_unknown(repo):
    _init_active(repo)
    run_hook(repo, {"hook_event_name": "PostToolUse", "tool_name": "Bash",
                    "tool_input": {"command": "pytest -q"}, "cwd": str(repo)})
    runs = repo / ".goalkeeper" / "runs.jsonl"
    assert not runs.exists() or runs.read_text().strip() == ""


def test_posttooluse_ignores_goalkeeper_run(repo):
    _init_active(repo)
    run_hook(repo, {"hook_event_name": "PostToolUse", "tool_name": "Bash",
                    "tool_input": {"command": "goalkeeper run pytest"},
                    "tool_response": {"exit_code": 0}, "cwd": str(repo)})
    runs = repo / ".goalkeeper" / "runs.jsonl"
    assert not runs.exists() or runs.read_text().strip() == ""


def test_hook_survives_garbage_input(repo):
    _init_active(repo)
    r = run_hook(repo, {})
    assert r.returncode == 0
