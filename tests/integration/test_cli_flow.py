"""Integration tests driving the real CLI entrypoint (proves the bootstrap)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from tests.conftest import REPO_ROOT, load_state, run_cli, run_hook


def test_init_template_is_valid(repo):
    r = run_cli(repo, "init", "--template", "code-refactor", "-o", "Refactor auth")
    assert r.returncode == 0
    v = run_cli(repo, "validate-contract", "--strict")
    assert v.returncode == 0, v.stdout
    s = load_state(repo)
    assert s["goal"]["domain"] == "code"
    assert s["schema_version"] == 2
    # goal.md is a generated artifact
    assert (repo / ".goalkeeper" / "goal.md").exists()


def test_gate_rejects_underspecified_contract(repo):
    run_cli(repo, "init", "-o", "Make it better")
    g = run_cli(repo, "gate", "--json")
    assert g.returncode == 2
    blockers = {b["code"] for b in json.loads(g.stdout)["blockers"]}
    assert "contract_not_active" in blockers
    assert "objective_unbounded" in blockers
    assert "validator_missing" in blockers
    assert "required_validator_missing" in blockers
    assert "scope_missing" in blockers
    assert "checkpoint_missing" in blockers


def test_all_templates_validate(repo):
    from goalkeeper_core.templates import template_names
    for name in template_names():
        r = run_cli(repo, "init", "--template", name, "--force", "-o", "Do the thing")
        assert r.returncode == 0, r.stderr
        v = run_cli(repo, "validate-contract")
        assert v.returncode == 0, f"{name}: {v.stdout}"


def test_set_is_nested_and_rerenders(repo):
    run_cli(repo, "init", "-o", "Obj")
    run_cli(repo, "set", "scope.allowed_resources", "src/**,tests/**")
    s = load_state(repo)
    assert s["scope"]["allowed_resources"] == ["src/**", "tests/**"]
    md = (repo / ".goalkeeper" / "goal.md").read_text()
    assert "src/**" in md


def test_set_complete_status_refused(repo):
    run_cli(repo, "init", "-o", "Obj")
    r = run_cli(repo, "set", "completion.status", "complete")
    assert r.returncode != 0
    assert "goalkeeper complete" in r.stderr


def test_lock_blocks_set(repo):
    run_cli(repo, "init", "-o", "Obj")
    run_cli(repo, "contract-lock")
    r = run_cli(repo, "set", "goal.title", "X")
    assert r.returncode != 0 and "locked" in r.stderr
    u = run_cli(repo, "contract-unlock", "--reason", "deliberate change")
    assert u.returncode == 0
    r2 = run_cli(repo, "set", "goal.title", "X")
    assert r2.returncode == 0


def test_gate_complete_proof_lifecycle(repo):
    run_cli(repo, "init", "-o", "Make it pass")
    run_cli(repo, "set", "scope.allowed_resources", "**")
    # one runnable validator
    s = load_state(repo)
    s["validators"] = [{"id": "ok", "type": "command", "command": "true",
                        "pass_condition": "exit_zero", "required": True}]
    (repo / ".goalkeeper" / "state.json").write_text(json.dumps(s, indent=2))
    run_cli(repo, "set", "completion.status", "active")
    run_cli(repo, "checkpoint", "--add", "done")
    # gate fails before evidence
    assert run_cli(repo, "gate").returncode == 2
    run_cli(repo, "run", "true")
    run_cli(repo, "checkpoint", "--id", "cp1", "--evidence", "true -> 0", "--met")
    # gate passes now
    g = run_cli(repo, "gate")
    assert g.returncode == 0, g.stdout
    assert "tier" in g.stdout.lower()
    # complete requires --accepted-by
    assert run_cli(repo, "complete").returncode != 0
    c = run_cli(repo, "complete", "--accepted-by", "robert")
    assert c.returncode == 0
    assert load_state(repo)["completion"]["status"] == "complete"
    assert (repo / ".goalkeeper" / "proof.md").exists()
    assert (repo / ".goalkeeper" / "proof.json").exists()


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


def test_gate_rerun_earns_tier_four(repo):
    _active_command_contract(repo)
    # A normal recorded run proves tier 3 (deterministic), not 4.
    run_cli(repo, "run", "true")
    g3 = json.loads(run_cli(repo, "gate", "--json").stdout)
    assert g3["verdict"] == "COMPLETE" and g3["tier"] == 3
    # --rerun re-executes the validator from a clean state and tags it -> tier 4.
    g4 = json.loads(run_cli(repo, "gate", "--rerun", "--json").stdout)
    assert g4["verdict"] == "COMPLETE" and g4["tier"] == 4


def test_posttooluse_autocapture_satisfies_gate(repo):
    _active_command_contract(repo)
    # Before any evidence the required command validator is inconclusive.
    g0 = json.loads(run_cli(repo, "gate", "--json").stdout)
    assert any(b["code"] == "validator_inconclusive" for b in g0["blockers"])
    # The hook auto-captures a bare command run (no `goalkeeper run` needed).
    run_hook(repo, {"hook_event_name": "PostToolUse", "tool_name": "Bash",
                    "tool_input": {"command": "true"},
                    "tool_response": {"exit_code": 0}, "cwd": str(repo)})
    g1 = json.loads(run_cli(repo, "gate", "--json").stdout)
    assert g1["verdict"] == "COMPLETE"


def test_run_captures_bounded_output_artifacts(repo, monkeypatch):
    monkeypatch.setenv("GOALKEEPER_RUN_OUTPUT_LIMIT_BYTES", "5")
    run_cli(repo, "init", "-o", "Capture output")
    cmd = (
        f"{sys.executable} -c "
        "\"import sys; sys.stdout.write('abcdef'); sys.stderr.write('uvwxyz')\""
    )
    r = run_cli(repo, "run", cmd)
    assert r.returncode == 0
    runs = (repo / ".goalkeeper" / "runs.jsonl").read_text().splitlines()
    rec = json.loads(runs[-1])
    assert rec["cmd"] == cmd
    assert rec["stdout_truncated"] is True
    assert rec["stderr_truncated"] is True
    assert rec["output_limit_bytes"] == 5
    stdout_path = repo / rec["stdout_artifact"]
    stderr_path = repo / rec["stderr_artifact"]
    assert stdout_path.exists()
    assert stderr_path.exists()
    assert "abcde" in stdout_path.read_text()
    assert "output truncated" in stdout_path.read_text()
    assert "uvwxy" in stderr_path.read_text()


def test_complete_refused_until_gate_passes(repo):
    run_cli(repo, "init", "--template", "code-refactor", "-o", "x")
    run_cli(repo, "set", "completion.status", "active")
    r = run_cli(repo, "complete", "--accepted-by", "rob")
    assert r.returncode == 2
    assert "gate failed" in r.stderr.lower()


def test_approve_unblocks_risk_gate(repo):
    run_cli(repo, "init", "-o", "ship it")
    run_cli(repo, "set", "scope.allowed_resources", "**")
    run_cli(repo, "set", "risk.level", "high")
    run_cli(repo, "set", "completion.status", "active")
    # high risk needs approval; gate should flag approval_required
    g = run_cli(repo, "gate", "--json")
    blockers = json.loads(g.stdout)["blockers"]
    assert any(b["code"] == "approval_required" for b in blockers)
    run_cli(repo, "approve", "high-risk-signoff", "--by", "robert")
    g2 = run_cli(repo, "gate", "--json")
    codes = [b["code"] for b in json.loads(g2.stdout)["blockers"]]
    assert "approval_required" not in codes


def test_detect_writes_command_validators(repo):
    (repo / "package.json").write_text('{"scripts":{"test":"jest","typecheck":"tsc"}}')
    run_cli(repo, "init", "-o", "x")
    r = run_cli(repo, "detect", "--apply")
    assert r.returncode == 0
    vals = load_state(repo)["validators"]
    assert any(v["type"] == "command" for v in vals)


def test_init_auto_creates_active_contract_from_repo(repo):
    (repo / "package.json").write_text('{"scripts":{"test":"vitest","typecheck":"tsc --noEmit"}}')
    (repo / "src").mkdir()
    (repo / "src" / "index.ts").write_text("export const ok = true;\n")
    r = run_cli(repo, "init", "--auto", "-o", "Wire the feature")
    assert r.returncode == 0, r.stderr
    s = load_state(repo)
    assert s["completion"]["status"] == "active"
    assert [v["command"] for v in s["validators"]] == ["npm test", "npm run typecheck"]
    assert "src/**" in s["scope"]["allowed_resources"]
    assert s["checkpoints"][0]["id"] == "cp1"


def test_adopt_scopes_current_diff(repo):
    (repo / "src").mkdir()
    (repo / "src" / "auth.py").write_text("VALUE = 'x'\n")
    r = run_cli(repo, "adopt", "-o", "Finish auth change")
    assert r.returncode == 0, r.stderr
    s = load_state(repo)
    assert s["completion"]["status"] == "active"
    assert s["loop_runtime"]["adopted_existing_diff"] is True
    assert "src/**" in s["scope"]["allowed_resources"]


def test_adopt_does_not_forbid_adopted_github_diff(repo):
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
    r = run_cli(repo, "adopt", "-o", "Finish CI workflow")
    assert r.returncode == 0, r.stderr
    s = load_state(repo)
    assert ".github/**" in s["scope"]["allowed_resources"]
    assert ".github/**" not in s["scope"]["forbidden_resources"]
    assert ".git/**" in s["scope"]["forbidden_resources"]


def test_adopt_force_clears_stale_run_evidence(repo):
    (repo / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\n")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("VALUE = 1\n")
    run_cli(repo, "init", "--auto", "-o", "Initial proof")
    run_cli(repo, "run", "python3 -m compileall -q src")
    assert (repo / ".goalkeeper" / "runs.jsonl").exists()

    (repo / "src" / "app.py").write_text("VALUE = 2\n")
    r = run_cli(repo, "adopt", "--force", "-o", "Adopt changed app")
    assert r.returncode == 0, r.stderr
    runs = repo / ".goalkeeper" / "runs.jsonl"
    assert not runs.exists() or runs.read_text() == ""
    g = run_cli(repo, "gate", "--json")
    blockers = {b["code"] for b in json.loads(g.stdout)["blockers"]}
    assert "validator_inconclusive" in blockers


def test_gate_reports_invalid_contract_without_crashing(repo):
    run_cli(repo, "init", "-o", "Scoped objective")
    state_path = repo / ".goalkeeper" / "state.json"
    s = load_state(repo)
    s["goal"] = "not a mapping"
    state_path.write_text(json.dumps(s))
    r = run_cli(repo, "gate", "--json")
    assert r.returncode == 2
    data = json.loads(r.stdout)
    assert data["verdict"] == "INCOMPLETE"
    assert any(b["code"] == "contract_invalid" for b in data["blockers"])


def test_split_packets_disjoint(repo):
    run_cli(repo, "init", "-o", "x")
    run_cli(repo, "set", "scope.allowed_resources", "src/a/**,src/b/**")
    r = run_cli(repo, "split", "--write-packets")
    assert r.returncode == 0
    assert (repo / ".goalkeeper" / "agent_packets.md").exists()
    lst = run_cli(repo, "packets", "list")
    assert "P1" in lst.stdout and "P2" in lst.stdout


def test_copied_host_entrypoints_use_core_home(tmp_path):
    for host in ("claude", "codex"):
        copied = tmp_path / host
        shutil.copytree(REPO_ROOT / "hosts" / host, copied)
        env = os.environ.copy()
        env["GOALKEEPER_CORE_HOME"] = str(REPO_ROOT)
        cli = subprocess.run(
            [sys.executable, str(copied / "bin" / "goalkeeper"), "--version"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        )
        assert cli.returncode == 0, cli.stderr
        assert "goalkeeper" in cli.stdout
        hook = subprocess.run(
            [sys.executable, str(copied / "bin" / "goalkeeper_hook.py")],
            cwd=tmp_path,
            env=env,
            input="{}",
            capture_output=True,
            text=True,
        )
        assert hook.returncode == 0


def test_codex_host_does_not_reference_claude_plugin_root():
    for path in (REPO_ROOT / "hosts" / "codex").rglob("*"):
        if path.is_file():
            assert "CLAUDE_PLUGIN_ROOT" not in path.read_text(encoding="utf-8")


def test_host_bin_copies_match_canonical():
    # bin/ entrypoints are vendored byte-for-byte into each host; guard the drift.
    for name in ("goalkeeper", "goalkeeper_hook.py"):
        canonical = (REPO_ROOT / "bin" / name).read_bytes()
        for host in ("claude", "codex"):
            copy = (REPO_ROOT / "hosts" / host / "bin" / name).read_bytes()
            assert copy == canonical, f"hosts/{host}/bin/{name} drifted from bin/{name}; re-copy it"


def test_install_dry_run_json_uses_env_targets(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("GOALKEEPER_INSTALL_BIN_DIR", str(tmp_path / "bin"))
    r = run_cli(repo, "install", "shell", "--dry-run", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["ok"] is True
    assert data["dry_run"] is True
    assert data["steps"][0]["dest"] == str(tmp_path / "bin" / "goalkeeper")
    assert not (tmp_path / "bin" / "goalkeeper").exists()


def test_host_doctor_json_shape(repo):
    r = run_cli(repo, "host", "doctor", "shell", "--json")
    assert r.returncode in (0, 2)
    data = json.loads(r.stdout)
    assert "checks" in data
    assert any(c["name"] == "python" for c in data["checks"])


def test_host_doctor_codex_surfaces_version_and_trust(repo):
    r = run_cli(repo, "host", "doctor", "codex", "--json")
    assert r.returncode in (0, 2)
    names = {c["name"] for c in json.loads(r.stdout)["checks"]}
    assert "codex_version" in names
    assert "codex_hooks_trust" in names


def test_smoke_core_passes(repo):
    r = run_cli(repo, "smoke", "core", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["ok"] is True
    assert data["before_gate"]["verdict"] == "INCOMPLETE"
    assert data["after_gate"]["verdict"] == "COMPLETE"


def test_smoke_codex_hook_passes(repo):
    r = run_cli(repo, "smoke", "codex", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["hook"]["ok"] is True
