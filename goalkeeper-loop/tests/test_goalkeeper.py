"""Test suite for the Goalkeeper Loop CLI and hook.

Run with: pytest -q  (from the goalkeeper-loop/ directory)

The CLI script has no .py extension, so we load it via SourceFileLoader.
Hook behavior is tested end-to-end by piping crafted JSON to the script as a
subprocess, exactly as a host would invoke it.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parent.parent / "bin"
CLI = BIN / "goalkeeper"
HOOK = BIN / "goalkeeper_hook.py"


def _load_cli():
    # The CLI has no .py extension; load it as a module by explicit source path.
    loader = importlib.machinery.SourceFileLoader("gk", str(CLI))
    spec = importlib.util.spec_from_loader("gk", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


import importlib.machinery  # noqa: E402

gk = _load_cli()


# --------------------------------------------------------------------------- #
# Pure-function unit tests
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "path,patterns,expected",
    [
        (".github/workflows/ci.yml", [".github/**"], True),
        ("src/auth/token.ts", ["src/auth/**"], True),
        ("src/auth/token.ts", ["tests/auth/**"], False),
        ("src/other.ts", ["src/auth/**"], False),
        ("tests/auth/x.ts", ["src/auth/**", "tests/auth/**"], True),
        ("src/auth", ["src/auth/**"], True),
        ("README.md", ["*.md"], True),
        ("anything", [], False),
    ],
)
def test_matches_any(path, patterns, expected):
    assert gk._matches_any(path, patterns) is expected


@pytest.mark.parametrize(
    "action,expected",
    [
        ("add production dependencies", "do not add production dependencies"),
        ("do not change public behavior", "do not change public behavior"),
        ("never touch CI", "never touch CI"),
        ("Don't edit migrations", "Don't edit migrations"),
    ],
)
def test_as_prohibition(action, expected):
    assert gk._as_prohibition(action) == expected


def test_build_goal_command_shape():
    state = {
        "objective": "Refactor auth to new token API",
        "allowed_paths": ["src/auth/**", "tests/auth/**"],
        "validations": ["npm test", "npm run typecheck"],
        "forbidden_actions": ["add production dependencies"],
        "forbidden_paths": [".github/**"],
        "stop_after_turns": 12,
    }
    cmd = gk._build_goal_command(state)
    assert "only in src/auth/**, tests/auth/**." in cmd
    assert "npm test exits 0" in cmd
    assert "Done means" in cmd
    assert "do not add production dependencies" in cmd
    assert "do not change .github/**" in cmd
    assert "after 12 turns" in cmd
    # No stray space before the period.
    assert " ." not in cmd.split("Done means")[0]


def test_detect_stack_node(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "jest", "typecheck": "tsc"}})
    )
    stacks = gk.detect_stack(tmp_path)
    assert any(s["name"] == "node" for s in stacks)
    vals = gk.suggested_validations(tmp_path)
    assert "npm test" in vals
    assert "npm run typecheck" in vals
    # build script absent -> not suggested
    assert "npm run build" not in vals


# --------------------------------------------------------------------------- #
# CLI integration tests (run inside a temp git repo)
# --------------------------------------------------------------------------- #
def _run_cli(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=tmp_path, check=True)
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "true"}}))
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.txt").write_text("a")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    return tmp_path


def test_init_and_status(repo):
    r = _run_cli(repo, "init", "-o", "Do the thing")
    assert r.returncode == 0
    assert (repo / ".goalkeeper" / "state.json").exists()
    state = json.loads((repo / ".goalkeeper" / "state.json").read_text())
    assert state["objective"] == "Do the thing"
    # base_ref captured at init
    assert state["base_ref"]
    r2 = _run_cli(repo, "status")
    assert "Do the thing" in r2.stdout


def test_score_excludes_goalkeeper_and_flags_scope(repo):
    _run_cli(repo, "init", "-o", "Refactor X")
    _run_cli(repo, "set", "allowed_paths", "src/**")
    _run_cli(repo, "set", "forbidden_paths", ".github/**")
    _run_cli(repo, "checkpoint", "--add", "done X")
    # make an in-scope change + an out-of-scope change + a forbidden change
    (repo / "src" / "b.txt").write_text("b")
    (repo / "outside.txt").write_text("nope")
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text("ci")

    r = _run_cli(repo, "score", "--json")
    report = json.loads(r.stdout)
    changed = report["changed_files"]
    # .goalkeeper/ files must NOT be counted
    assert all(not f.startswith(".goalkeeper") for f in report["files_outside_allowed_paths"])
    assert "outside.txt" in report["files_outside_allowed_paths"]
    assert ".github/workflows/ci.yml" in report["forbidden_path_changes"]
    assert report["verdict"] == "REVIEW"
    assert changed >= 3


def test_score_uses_captured_baseline_for_committed_changes(repo):
    # Baseline captured at init; a later COMMIT must still be counted as change.
    _run_cli(repo, "init", "-o", "thing")
    _run_cli(repo, "set", "allowed_paths", "src/**")
    (repo / "newfile.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "later"], cwd=repo, check=True)

    report = json.loads(_run_cli(repo, "score", "--json").stdout)
    # base must be the captured sha, not the literal "HEAD"
    assert report["base"] != "HEAD"
    assert "newfile.py" in report["files_outside_allowed_paths"]


def test_run_records_ledger_and_score_checks_validations(repo):
    _run_cli(repo, "init", "-o", "thing")
    _run_cli(repo, "set", "validations", "true,false")
    # before running, both validations are "not run"
    r0 = json.loads(_run_cli(repo, "score", "--json").stdout)
    assert set(r0["validations_not_run"]) == {"true", "false"}

    # run them: `true` exits 0, `false` exits 1
    assert _run_cli(repo, "run", "true").returncode == 0
    assert _run_cli(repo, "run", "false").returncode == 1
    assert (repo / ".goalkeeper" / "runs.jsonl").exists()

    r1 = json.loads(_run_cli(repo, "score", "--json").stdout)
    assert r1["validations_not_run"] == []
    assert "false" in r1["validations_failed"]
    assert "true" not in r1["validations_failed"]


def test_doctor_flags_weak_contract(repo):
    _run_cli(repo, "init", "-o", "make it better")  # vague => unbounded
    r = _run_cli(repo, "doctor", "--json")
    report = json.loads(r.stdout)
    names = {c["name"]: c["ok"] for c in report["checks"]}
    assert names["objective is bounded (no vague terms)"] is False
    assert report["contract_quality"] < 100
    assert r.returncode == 2


def test_seed_detects_policy(repo):
    (repo / "AGENTS.md").write_text("rules")
    r = _run_cli(repo, "seed", "--json")
    findings = json.loads(r.stdout)
    assert "AGENTS.md" in findings["policy_files"]
    assert "npm test" in findings["validations"]


def test_generate_goal_outputs_slash_goal(repo):
    _run_cli(repo, "init", "-o", "Refactor auth")
    _run_cli(repo, "set", "allowed_paths", "src/**")
    _run_cli(repo, "set", "validations", "npm test")
    out = _run_cli(repo, "generate-goal").stdout
    assert out.startswith("/goal ")
    assert "npm test exits 0" in out


# --------------------------------------------------------------------------- #
# Hook end-to-end tests (subprocess + stdin JSON)
# --------------------------------------------------------------------------- #
def _hook(repo: Path, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


@pytest.fixture
def active_repo(repo: Path) -> Path:
    _run_cli(repo, "init", "-o", "Refactor auth")
    _run_cli(repo, "set", "allowed_paths", "src/**")
    _run_cli(repo, "set", "forbidden_paths", ".github/**")
    _run_cli(repo, "set", "status", "active")
    _run_cli(repo, "checkpoint", "--add", "auth done")
    return repo


def test_hook_session_start_injects_context(active_repo):
    r = _hook(active_repo, {"hook_event_name": "SessionStart", "cwd": str(active_repo)})
    out = json.loads(r.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "Goal Contract" in ctx
    assert "Refactor auth" in ctx
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"


def test_hook_blocks_destructive(active_repo):
    r = _hook(
        active_repo,
        {
            "hook_event_name": "PreToolUse",
            "cwd": str(active_repo),
            "tool_name": "Bash",
            "tool_input": {"command": "git reset --hard HEAD~3"},
        },
    )
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_blocks_forbidden_path(active_repo):
    r = _hook(
        active_repo,
        {
            "hook_event_name": "PreToolUse",
            "cwd": str(active_repo),
            "tool_name": "Bash",
            "tool_input": {"command": "echo x > .github/workflows/ci.yml"},
        },
    )
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert ".github" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_hook_allows_safe_command(active_repo):
    r = _hook(
        active_repo,
        {
            "hook_event_name": "PreToolUse",
            "cwd": str(active_repo),
            "tool_name": "Bash",
            "tool_input": {"command": "npm test"},
        },
    )
    assert r.stdout.strip() == ""


def test_hook_no_false_positive_on_common_words(active_repo):
    # "production" used to trigger a false forbidden-action block; must not now.
    _run_cli(active_repo, "set", "forbidden_actions", "add production dependencies")
    r = _hook(
        active_repo,
        {
            "hook_event_name": "PreToolUse",
            "cwd": str(active_repo),
            "tool_name": "Bash",
            "tool_input": {"command": "node build.js --env production"},
        },
    )
    assert r.stdout.strip() == ""


def test_hook_stop_autocontinue_uses_additional_context(active_repo):
    _run_cli(active_repo, "autocontinue", "on", "--max", "2")
    r = _hook(active_repo, {"hook_event_name": "Stop", "cwd": str(active_repo)})
    out = json.loads(r.stdout)
    assert out["decision"] == "block"
    # guidance MUST be in additionalContext (model ignores `reason`)
    assert "additionalContext" in out["hookSpecificOutput"]
    assert "checkpoint" in out["hookSpecificOutput"]["additionalContext"].lower()


def test_hook_stop_off_by_default(active_repo):
    r = _hook(active_repo, {"hook_event_name": "Stop", "cwd": str(active_repo)})
    assert r.stdout.strip() == ""


def test_hook_stop_respects_budget(active_repo):
    _run_cli(active_repo, "autocontinue", "on", "--max", "1")
    first = _hook(active_repo, {"hook_event_name": "Stop", "cwd": str(active_repo)})
    assert json.loads(first.stdout)["decision"] == "block"
    second = _hook(active_repo, {"hook_event_name": "Stop", "cwd": str(active_repo)})
    assert second.stdout.strip() == ""  # budget exhausted


@pytest.mark.parametrize("raw", ["", "not json{", "[1,2,3]", "null"])
def test_hook_never_crashes_on_bad_input(active_repo, raw):
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=raw,
        cwd=str(active_repo),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
