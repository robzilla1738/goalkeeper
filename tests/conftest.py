"""Shared pytest fixtures. Puts the repo root on sys.path so tests import
goalkeeper_core directly, and provides temp git repos + CLI/hook runners."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CLI = REPO_ROOT / "bin" / "goalkeeper"
HOOK = REPO_ROOT / "bin" / "goalkeeper_hook.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=repo, check=True,
                   capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A fresh git repo with one commit (so base_ref resolves)."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "README.md").write_text("seed\n")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def run_cli(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=repo, capture_output=True, text=True,
    )


def run_hook(repo: Path, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=repo, input=json.dumps(payload), capture_output=True, text=True,
    )


def load_state(repo: Path) -> dict:
    return json.loads((repo / ".goalkeeper" / "state.json").read_text())


@pytest.fixture
def cli(repo):
    def _run(*args):
        return run_cli(repo, *args)
    _run.repo = repo
    return _run
