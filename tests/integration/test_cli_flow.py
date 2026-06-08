"""Integration tests driving the real CLI entrypoint (proves the bootstrap)."""
from __future__ import annotations

import json

from tests.conftest import load_state, run_cli


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


def test_split_packets_disjoint(repo):
    run_cli(repo, "init", "-o", "x")
    run_cli(repo, "set", "scope.allowed_resources", "src/a/**,src/b/**")
    r = run_cli(repo, "split", "--write-packets")
    assert r.returncode == 0
    assert (repo / ".goalkeeper" / "agent_packets.md").exists()
    lst = run_cli(repo, "packets", "list")
    assert "P1" in lst.stdout and "P2" in lst.stdout
