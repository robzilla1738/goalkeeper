"""Automatic code-contract generation from repo facts."""
from __future__ import annotations

import json
from pathlib import Path

from .contract import default_contract
from .detect import command_validators, seed_findings
from .gitio import changed_files, git_head
from .matching import matches_any


def build_auto_contract(objective: str, root: Path, adopt: bool = False) -> dict:
    """Build a practical code contract from local repo evidence."""
    state = default_contract(objective or _default_objective(adopt), domain="code", root=root)
    findings = seed_findings(root)
    commands = _validation_commands(root)
    if not commands:
        commands = _safe_seed_validations(root, findings)
    if not commands:
        commands = ["git diff --check"]
    state["validators"] = command_validators(commands)
    allowed_resources = _allowed_resources(root, adopt=adopt)
    state["scope"]["allowed_resources"] = allowed_resources
    state["scope"]["forbidden_resources"] = _forbidden_resources(root, findings, allowed_resources if adopt else [])
    state["scope"]["allowed_actions"] = ["edit source files", "add or update tests", "update documentation"]
    state["scope"]["forbidden_actions"] = ["unrelated refactors", "destructive git operations"]
    state["checkpoints"] = [
        {
            "id": "cp1",
            "description": "Required validators pass and the change stays within the declared scope.",
            "evidence_required": "goalkeeper run output + git diff review",
            "status": "pending",
            "evidence": "",
        }
    ]
    state["completion"]["status"] = "active"
    state["loop"]["mode"] = "goal_until_pass"
    state["loop"]["max_turns"] = 8 if adopt else 12
    state.setdefault("loop_runtime", {})["auto_generated"] = True
    if adopt:
        state["loop_runtime"]["adopted_existing_diff"] = True
    notes = findings.get("notes", [])
    if findings.get("policy_files"):
        notes.append("Policy files found: " + ", ".join(findings["policy_files"]))
    if notes:
        state.setdefault("evidence", {})["auto_notes"] = notes
    return state


def _default_objective(adopt: bool) -> str:
    if adopt:
        return "Complete the current code changes with recorded validation evidence."
    return "Complete the requested code work with recorded validation evidence."


def _validation_commands(root: Path) -> list[str]:
    commands: list[str] = []
    if (root / "package.json").exists():
        commands.extend(_node_commands(root))
    if any((root / marker).exists() for marker in ("pyproject.toml", "setup.py", "requirements.txt", "tox.ini")):
        commands.extend(_python_commands(root))
    if (root / "Cargo.toml").exists():
        commands.extend(["cargo test", "cargo check"])
    if (root / "go.mod").exists():
        commands.extend(["go test ./...", "go vet ./..."])
    return list(dict.fromkeys(commands))


def _node_commands(root: Path) -> list[str]:
    scripts = _node_scripts(root)
    runner = _node_runner(root)
    commands: list[str] = []
    for script in ("test", "typecheck", "lint", "build"):
        if script not in scripts:
            continue
        if runner == "npm":
            commands.append("npm test" if script == "test" else f"npm run {script}")
        else:
            commands.append(f"{runner} {script}")
    return commands


def _node_scripts(root: Path) -> dict:
    try:
        data = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    scripts = data.get("scripts", {})
    return scripts if isinstance(scripts, dict) else {}


def _node_runner(root: Path) -> str:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "bun.lockb").exists() or (root / "bun.lock").exists():
        return "bun"
    return "npm"


def _python_commands(root: Path) -> list[str]:
    target = "src" if (root / "src").is_dir() else "."
    commands = [f"python3 -m compileall -q {target}"]
    if (root / "tests").is_dir():
        commands.append("pytest -q")
    return commands


def _safe_seed_validations(root: Path, findings: dict) -> list[str]:
    commands = list(findings.get("validations", []))
    if not (root / "package.json").exists():
        return commands
    scripts = _node_scripts(root)
    filtered: list[str] = []
    for command in commands:
        if command == "npm test" and "test" not in scripts:
            continue
        if command.startswith("npm run ") and command.removeprefix("npm run ") not in scripts:
            continue
        filtered.append(command)
    return filtered


def _allowed_resources(root: Path, adopt: bool = False) -> list[str]:
    if adopt:
        adopted = _resources_from_changed_files(root)
        if adopted:
            return adopted
    candidates = [
        "src/**",
        "app/**",
        "lib/**",
        "packages/**",
        "goalkeeper_core/**",
        "tests/**",
        "docs/**",
    ]
    found = [pat for pat in candidates if (root / pat.split("/", 1)[0]).exists()]
    return found or ["**"]


def _resources_from_changed_files(root: Path) -> list[str]:
    base = git_head(root) or "HEAD"
    resources: list[str] = []
    for path in changed_files(base, root):
        if path.startswith(".goalkeeper/"):
            continue
        parts = path.split("/")
        if len(parts) == 1:
            resources.append(path)
        else:
            resources.append(parts[0] + "/**")
    return list(dict.fromkeys(resources))


def _forbidden_resources(root: Path, findings: dict, adopted_allowed: list[str] | None = None) -> list[str]:
    forbidden = list(findings.get("suggested_forbidden", []))
    if adopted_allowed:
        forbidden = [pat for pat in forbidden if not _patterns_overlap(pat, adopted_allowed)]
    for pat in (".git/**", ".goalkeeper/**"):
        if pat not in forbidden:
            forbidden.append(pat)
    return forbidden


def _patterns_overlap(pattern: str, patterns: list[str]) -> bool:
    sample = _sample_path(pattern)
    if matches_any(sample, patterns):
        return True
    return any(matches_any(_sample_path(pat), [pattern]) for pat in patterns)


def _sample_path(pattern: str) -> str:
    pattern = pattern.strip()
    if pattern.endswith("/**"):
        return pattern[:-3].rstrip("/")
    return pattern.rstrip("*").rstrip("/") or pattern
