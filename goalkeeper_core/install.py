"""Conservative installer for local Goalkeeper entrypoints and host packages."""
from __future__ import annotations

import os
from pathlib import Path

from .paths import repo_root

TARGETS = ("shell", "claude", "codex")


def install(target: str, dry_run: bool = False) -> dict:
    targets = _expand_target(target)
    steps = [_install_one(t, dry_run=dry_run) for t in targets]
    return _summary("install", dry_run, steps)


def uninstall(target: str, dry_run: bool = False) -> dict:
    targets = _expand_target(target)
    steps = [_uninstall_one(t, dry_run=dry_run) for t in targets]
    return _summary("uninstall", dry_run, steps)


def target_paths(target: str) -> dict:
    root = repo_root()
    home = Path.home()
    if target == "shell":
        bin_dir = Path(os.environ.get("GOALKEEPER_INSTALL_BIN_DIR", str(home / ".local" / "bin")))
        return {"source": root / "bin" / "goalkeeper", "dest": bin_dir / "goalkeeper"}
    if target == "claude":
        dest = Path(os.environ.get("GOALKEEPER_CLAUDE_PLUGIN_DIR", str(home / ".claude" / "skills" / "goalkeeper")))
        return {"source": root / "hosts" / "claude", "dest": dest}
    if target == "codex":
        dest = Path(os.environ.get("GOALKEEPER_CODEX_PLUGIN_DIR", str(home / ".codex" / "plugins" / "goalkeeper")))
        return {"source": root / "hosts" / "codex", "dest": dest}
    raise ValueError(f"unknown install target {target!r}")


def _expand_target(target: str) -> list[str]:
    if target == "all":
        return list(TARGETS)
    if target not in TARGETS:
        raise ValueError(f"unknown target {target!r}; choose shell, claude, codex, all")
    return [target]


def _install_one(target: str, dry_run: bool) -> dict:
    paths = target_paths(target)
    source = paths["source"]
    dest = paths["dest"]
    step = {"target": target, "source": str(source), "dest": str(dest), "ok": False, "action": "link"}
    if not source.exists():
        step.update({"error": f"source missing: {source}"})
        return step
    if dest.exists() or dest.is_symlink():
        if is_goalkeeper_link(dest, source):
            step.update({"ok": True, "detail": "already installed"})
            return step
        step.update({"error": f"destination already exists and is not a Goalkeeper link: {dest}"})
        return step
    if not dry_run:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.symlink_to(source, target_is_directory=source.is_dir())
    step.update({"ok": True, "detail": "would link" if dry_run else "linked"})
    return step


def _uninstall_one(target: str, dry_run: bool) -> dict:
    paths = target_paths(target)
    source = paths["source"]
    dest = paths["dest"]
    step = {"target": target, "source": str(source), "dest": str(dest), "ok": False, "action": "unlink"}
    if not dest.exists() and not dest.is_symlink():
        step.update({"ok": True, "detail": "not installed"})
        return step
    if not is_goalkeeper_link(dest, source):
        step.update({"error": f"refusing to remove non-Goalkeeper path: {dest}"})
        return step
    if not dry_run:
        dest.unlink()
    step.update({"ok": True, "detail": "would remove" if dry_run else "removed"})
    return step


def is_goalkeeper_link(dest: Path, source: Path) -> bool:
    try:
        return dest.is_symlink() and dest.exists() and dest.resolve() == source.resolve()
    except OSError:
        return False


def _summary(action: str, dry_run: bool, steps: list[dict]) -> dict:
    errors = [s["error"] for s in steps if s.get("error")]
    return {"action": action, "dry_run": dry_run, "ok": not errors, "steps": steps, "errors": errors}
