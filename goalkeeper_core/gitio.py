"""Git helpers + changed-file computation (ported from the v1 CLI)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .paths import GK_DIR, find_root


def git(*args: str, root: Path | None = None) -> str:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=str(root or find_root()),
            capture_output=True,
            text=True,
            check=False,
        )
        return out.stdout
    except FileNotFoundError:
        return ""


def git_ok(*args: str, root: Path | None = None) -> bool:
    """True if the git command exits 0 (used to probe repo state)."""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=str(root or find_root()),
            capture_output=True,
            text=True,
            check=False,
        )
        return out.returncode == 0
    except FileNotFoundError:
        return False


def git_head(root: Path | None = None) -> str:
    """Current HEAD sha, or '' if no commits / not a repo."""
    return git("rev-parse", "HEAD", root=root).strip()


def changed_files(base_ref: str, root: Path | None = None) -> list[str]:
    """Files changed since base_ref, including uncommitted + untracked work.

    Uses a three-dot diff against the merge-base when base_ref is a real commit
    so unrelated changes on the base branch are not counted, then layers on the
    working tree via `git status --porcelain`. The plugin's own .goalkeeper/
    state files are always excluded so they never look like scope drift.
    """
    root = root or find_root()
    files: set[str] = set()

    if base_ref and git_ok("rev-parse", "--verify", "--quiet", base_ref, root=root):
        diff = git("diff", "--name-only", f"{base_ref}...HEAD", root=root)
        if not diff.strip():
            diff = git("diff", "--name-only", base_ref, root=root)
        files.update(ln.strip() for ln in diff.splitlines() if ln.strip())

    porcelain = git("status", "--porcelain", "--untracked-files=all", root=root)
    for ln in porcelain.splitlines():
        path = ln[3:].strip() if len(ln) > 3 else ln.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            files.add(path)

    return sorted(f for f in files if not f.startswith(GK_DIR + "/") and f != GK_DIR)
