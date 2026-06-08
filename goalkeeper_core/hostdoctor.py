"""Host and install diagnostics for local Goalkeeper use."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .install import TARGETS, is_goalkeeper_link, target_paths
from .paths import repo_root


def doctor(target: str = "all") -> dict:
    targets = list(TARGETS) if target == "all" else [target]
    checks: list[dict] = []
    root = repo_root()
    checks.extend(_base_checks(root))
    for t in targets:
        checks.extend(_host_checks(t, root))
    errors = [c for c in checks if not c["ok"] and c["severity"] == "error"]
    warnings = [c for c in checks if not c["ok"] and c["severity"] == "warning"]
    return {
        "ok": not errors,
        "target": target,
        "checks": checks,
        "errors": [_format_issue(c) for c in errors],
        "warnings": [_format_issue(c) for c in warnings],
    }


def _base_checks(root: Path) -> list[dict]:
    return [
        _check("python", True, f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
        _check("repo_root", (root / "goalkeeper_core").is_dir(), str(root), fix="run from a Goalkeeper checkout"),
        _check("git", shutil.which("git") is not None, shutil.which("git") or "missing", fix="install git"),
        _check("goalkeeper_cli", (root / "bin" / "goalkeeper").exists(), str(root / "bin" / "goalkeeper")),
    ]


def _host_checks(target: str, root: Path) -> list[dict]:
    if target not in TARGETS:
        return [_check(f"{target}_target", False, "unknown target", severity="error")]
    checks: list[dict] = []
    paths = target_paths(target)
    checks.append(_check(f"{target}_source", paths["source"].exists(), str(paths["source"]), severity="error"))
    checks.append(_check(f"{target}_installed", _installed(paths["dest"], paths["source"]), str(paths["dest"]),
                         severity="warning", fix=f"goalkeeper install {target}"))
    if target == "shell":
        checks.append(_check("goalkeeper_on_path", shutil.which("goalkeeper") is not None,
                             shutil.which("goalkeeper") or "missing", severity="warning",
                             fix="goalkeeper install shell"))
        return checks
    checks.extend(_manifest_checks(target, paths["source"]))
    checks.append(_hook_exec_check(target, paths["source"], root))
    binary = shutil.which("claude" if target == "claude" else "codex")
    checks.append(_check(f"{target}_binary", binary is not None, binary or "missing", severity="warning",
                         fix=f"install {'Claude Code' if target == 'claude' else 'Codex'} or skip this host"))
    return checks


def _manifest_checks(target: str, source: Path) -> list[dict]:
    files = [source / "hooks" / "hooks.json"]
    if target == "claude":
        files.append(source / ".claude-plugin" / "plugin.json")
    if target == "codex":
        files.append(source / ".codex-plugin" / "plugin.json")
    checks = []
    for path in files:
        ok = False
        detail = str(path)
        try:
            json.loads(path.read_text(encoding="utf-8"))
            ok = True
        except Exception as exc:
            detail = f"{path}: {exc}"
        checks.append(_check(f"{target}_{path.name}", ok, detail, severity="error"))
    return checks


def _hook_exec_check(target: str, source: Path, root: Path) -> dict:
    hook = source / "bin" / "goalkeeper_hook.py"
    if not hook.exists():
        return _check(f"{target}_hook_exec", False, str(hook), severity="error")
    env = os.environ.copy()
    env["GOALKEEPER_CORE_HOME"] = str(root)
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input="{}",
        text=True,
        capture_output=True,
        env=env,
        cwd=str(root),
        check=False,
    )
    ok = proc.returncode == 0
    detail = f"exit {proc.returncode}"
    if proc.stderr:
        detail += f"; stderr: {proc.stderr.strip()[:200]}"
    return _check(f"{target}_hook_exec", ok, detail, severity="error", fix="check GOALKEEPER_CORE_HOME")


def _installed(dest: Path, source: Path) -> bool:
    return is_goalkeeper_link(dest, source)


def _check(name: str, ok: bool, detail: str = "", severity: str = "error", fix: str = "") -> dict:
    return {"name": name, "ok": ok, "severity": severity, "detail": detail, "fix": fix}


def _format_issue(check: dict) -> str:
    msg = f"{check['name']}: {check.get('detail', '')}"
    if check.get("fix"):
        msg += f" (fix: {check['fix']})"
    return msg
