"""End-to-end smoke checks for Goalkeeper and host hook wiring."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .paths import repo_root


def smoke(target: str = "core") -> dict:
    if target not in ("core", "claude", "codex"):
        raise ValueError("smoke target must be core, claude, or codex")
    with tempfile.TemporaryDirectory(prefix="goalkeeper-smoke-") as tmp:
        root = Path(tmp)
        result = _core_smoke(root)
        if target in ("claude", "codex"):
            result["hook"] = _host_hook_smoke(target, root)
            result["ok"] = result["ok"] and result["hook"]["ok"]
        if target == "codex":
            result["note"] = ("Codex runs non-managed hooks only after a one-time `/hooks` trust "
                              "(re-trust after edits); use a recent Codex (hooks GA 2026).")
        result["target"] = target
        return result


def _core_smoke(root: Path) -> dict:
    cli = repo_root() / "bin" / "goalkeeper"
    steps: list[dict] = []
    _write_fixture(root)
    _run(["git", "init", "-q"], root, steps)
    _run(["git", "-c", "commit.gpgsign=false", "config", "user.email", "t@t"], root, steps)
    _run(["git", "-c", "commit.gpgsign=false", "config", "user.name", "t"], root, steps)
    _run(["git", "-c", "commit.gpgsign=false", "add", "."], root, steps)
    _run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "init"], root, steps)
    _run([sys.executable, str(cli), "init", "--auto", "-o", "Smoke validate Python project"], root, steps)
    before = _run([sys.executable, str(cli), "gate", "--json"], root, steps, expect=(2,))
    state = json.loads((root / ".goalkeeper" / "state.json").read_text(encoding="utf-8"))
    command = state["validators"][0]["command"]
    _run([sys.executable, str(cli), "run", command], root, steps)
    _run([sys.executable, str(cli), "checkpoint", "--id", "cp1", "--evidence", f"{command} -> exit 0", "--met"], root, steps)
    after = _run([sys.executable, str(cli), "gate", "--json"], root, steps)
    before_json = _loads(before["stdout"])
    after_json = _loads(after["stdout"])
    ok = all(s["ok"] for s in steps) and before_json.get("verdict") == "INCOMPLETE" and after_json.get("verdict") == "COMPLETE"
    return {"ok": ok, "root": str(root), "steps": steps, "before_gate": before_json, "after_gate": after_json}


def _host_hook_smoke(target: str, project_root: Path) -> dict:
    hook = repo_root() / "hosts" / target / "bin" / "goalkeeper_hook.py"
    env = os.environ.copy()
    env["GOALKEEPER_CORE_HOME"] = str(repo_root())
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git reset --hard HEAD~1"},
        "cwd": str(project_root),
    }
    proc = subprocess.run(
        [sys.executable, str(hook)],
        cwd=str(project_root),
        env=env,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    out = _loads(proc.stdout)
    decision = (out.get("hookSpecificOutput") or {}).get("permissionDecision")
    return {"ok": proc.returncode == 0 and decision == "deny", "exit": proc.returncode, "stdout": out, "stderr": proc.stderr}


def _write_fixture(root: Path) -> None:
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname = \"goalkeeper-smoke\"\nversion = \"0.0.0\"\n", encoding="utf-8")


def _run(args: list[str], cwd: Path, steps: list[dict], expect: tuple[int, ...] = (0,)) -> dict:
    proc = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, check=False)
    rec = {
        "cmd": " ".join(args),
        "exit": proc.returncode,
        "ok": proc.returncode in expect,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    steps.append(rec)
    return rec


def _loads(text: str) -> dict:
    try:
        return json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
