"""Language/stack detection and project-policy seeding (ported from v1)."""
from __future__ import annotations

import json
from pathlib import Path

PRESETS = [
    {"name": "node", "markers": ["package.json"],
     "test": "npm test", "build": "npm run build", "typecheck": "npm run typecheck", "lint": "npm run lint"},
    {"name": "python", "markers": ["pyproject.toml", "setup.py", "requirements.txt", "tox.ini"],
     "test": "pytest -q", "build": "python -m build", "typecheck": "mypy .", "lint": "ruff check ."},
    {"name": "rust", "markers": ["Cargo.toml"],
     "test": "cargo test", "build": "cargo build", "typecheck": "cargo check", "lint": "cargo clippy -- -D warnings"},
    {"name": "go", "markers": ["go.mod"],
     "test": "go test ./...", "build": "go build ./...", "typecheck": "go vet ./...", "lint": "golangci-lint run"},
    {"name": "java-maven", "markers": ["pom.xml"],
     "test": "mvn test", "build": "mvn -q package", "typecheck": "mvn -q compile", "lint": "mvn -q checkstyle:check"},
    {"name": "java-gradle", "markers": ["build.gradle", "build.gradle.kts"],
     "test": "./gradlew test", "build": "./gradlew build", "typecheck": "./gradlew compileJava", "lint": "./gradlew check"},
    {"name": "ruby-rails", "markers": ["Gemfile", "config/application.rb"],
     "test": "bundle exec rspec", "build": "bundle exec rails assets:precompile", "typecheck": "bundle exec srb tc", "lint": "bundle exec rubocop"},
]


def detect_stack(root: Path) -> list[dict]:
    return [p for p in PRESETS if any((root / m).exists() for m in p["markers"])]


def _node_scripts(root: Path) -> dict:
    pkg = root / "package.json"
    if not pkg.exists():
        return {}
    try:
        return json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
    except (json.JSONDecodeError, OSError):
        return {}


def suggested_validations(root: Path) -> list[str]:
    cmds: list[str] = []
    node_scripts = _node_scripts(root)
    for preset in detect_stack(root):
        for key in ("test", "typecheck", "build", "lint"):
            cmd = preset.get(key)
            if not cmd:
                continue
            if preset["name"] == "node":
                script = cmd.replace("npm run ", "").replace("npm ", "")
                if script != "test" and script not in node_scripts:
                    continue
            if cmd not in cmds:
                cmds.append(cmd)
    return cmds


def seed_findings(root: Path) -> dict:
    findings: dict = {
        "validations": suggested_validations(root),
        "policy_files": [],
        "notes": [],
    }
    for name in ("AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md"):
        if (root / name).exists():
            findings["policy_files"].append(name)
    wf_dir = root / ".github" / "workflows"
    if wf_dir.is_dir():
        wfs = [p.name for p in wf_dir.glob("*.y*ml")]
        if wfs:
            findings["notes"].append(f"CI workflows present ({', '.join(wfs)}); align validators with CI.")
    findings["suggested_forbidden"] = [
        d for d in (".github/**", "node_modules/**", "dist/**", "build/**", "vendor/**")
        if (root / d.split("/")[0]).exists()
    ]
    return findings


def command_validators(commands: list[str]) -> list[dict]:
    """Turn a list of shell commands into command-type validator specs."""
    out = []
    for i, cmd in enumerate(commands, start=1):
        out.append({
            "id": f"v{i}",
            "type": "command",
            "command": cmd,
            "pass_condition": "exit_zero",
            "required": True,
        })
    return out
