#!/usr/bin/env python3
"""
goalkeeper_hook.py - conservative cross-compatible hook for the Goalkeeper Loop.

Reads a hook event as JSON on stdin and writes a hook response as JSON on
stdout. It is written defensively so the same script can serve Claude Code
hooks and Codex hooks; unknown event shapes are handled gracefully and never
crash the host (any internal error exits 0 = "do nothing").

Behavior (all conservative, opt-in for anything risky):

  * SessionStart / UserPromptSubmit / subagent start
        -> inject the active .goalkeeper Goal Contract summary as context.
  * PreToolUse (Bash/shell tool)
        -> block obvious destructive commands (rm -rf, git reset --hard,
           git clean -fdx, mkfs, dd, etc.).
        -> block commands that touch configured forbidden paths/actions.
  * Stop / SubagentStop
        -> by default do nothing (native /goal is the preferred loop).
        -> if state.json enables `autocontinue` AND there is remaining turn
           budget, ask the host to continue (bounded).
  * Every event is appended to .goalkeeper/events.jsonl.

This script reads but never writes the contract; it only updates the
autocontinue counter in state.json when it actually issues a continue.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

GK_DIR = ".goalkeeper"


# --------------------------------------------------------------------------- #
# Locating project state
# --------------------------------------------------------------------------- #
def _project_root(payload: dict) -> Path:
    # Honor explicit host-provided project dir first.
    for key in ("cwd", "project_dir", "projectDir", "workspace_root"):
        val = payload.get(key)
        if val and Path(val).is_dir():
            start = Path(val)
            break
    else:
        start = Path(
            os.environ.get("CLAUDE_PROJECT_DIR")
            or os.environ.get("CODEX_PROJECT_DIR")
            or os.getcwd()
        )
    start = start.resolve()
    for cand in [start, *start.parents]:
        if (cand / GK_DIR).is_dir():
            return cand
    return start


def _gk(root: Path, name: str = "") -> Path:
    base = root / GK_DIR
    return base / name if name else base


def _load_state(root: Path) -> dict:
    p = _gk(root, "state.json")
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(root: Path, state: dict) -> None:
    try:
        p = _gk(root, "state.json")
        state["updated_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat(
            timespec="seconds"
        )
        p.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Event-name + tool extraction (host-agnostic)
# --------------------------------------------------------------------------- #
def _event_name(payload: dict) -> str:
    for key in ("hook_event_name", "hookEventName", "event", "type", "hook"):
        val = payload.get(key)
        if isinstance(val, str) and val:
            return val
    return ""


def _tool_name(payload: dict) -> str:
    for key in ("tool_name", "toolName", "tool"):
        val = payload.get(key)
        if isinstance(val, str) and val:
            return val
    return ""


def _command_text(payload: dict) -> str:
    ti = payload.get("tool_input") or payload.get("toolInput") or {}
    if isinstance(ti, dict):
        for key in ("command", "cmd", "script", "content"):
            val = ti.get(key)
            if isinstance(val, str):
                return val
    if isinstance(ti, str):
        return ti
    return ""


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
def _log_event(root: Path, record: dict) -> None:
    try:
        path = _gk(root, "events.jsonl")
        if not path.parent.is_dir():
            return
        record["ts"] = _now()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Context injection
# --------------------------------------------------------------------------- #
def _contract_summary(root: Path, state: dict) -> str:
    if not state or state.get("status") in ("complete", "abandoned"):
        return ""
    lines = ["[Goalkeeper] Active Goal Contract is in effect (.goalkeeper/)."]
    obj = state.get("objective")
    if obj:
        lines.append(f"Objective: {obj}")
    if state.get("allowed_paths"):
        lines.append("Allowed paths: " + ", ".join(state["allowed_paths"]))
    if state.get("forbidden_paths"):
        lines.append("Forbidden paths: " + ", ".join(state["forbidden_paths"]))
    if state.get("forbidden_actions"):
        lines.append("Forbidden actions: " + ", ".join(state["forbidden_actions"]))
    if state.get("validations"):
        lines.append("Validations (must pass): " + ", ".join(state["validations"]))
    cps = state.get("checkpoints", [])
    if cps:
        open_cps = [c for c in cps if not c.get("met")]
        lines.append(
            f"Checkpoints: {len(cps) - len(open_cps)}/{len(cps)} met. "
            "Record evidence in .goalkeeper/work_log.md."
        )
    lines.append(
        "Stay inside allowed scope. Capture tangents in the work_log parking "
        "lot instead of acting on them. Do not claim done without evidence."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Destructive / forbidden command screening
# --------------------------------------------------------------------------- #
DESTRUCTIVE_PATTERNS = [
    r"\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rf][a-zA-Z]*\b.*\s+/(?:\s|$)",  # rm -rf /
    r"\brm\s+-rf?\s+(--no-preserve-root|/|~|\$HOME|\*)\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-zA-Z]*f[a-zA-Z]*d",
    r"\bgit\s+checkout\s+--\s+\.",
    r"\bgit\s+push\s+.*--force\b",
    r"\bgit\s+push\s+.*-f\b",
    r"\bmkfs(\.\w+)?\b",
    r"\bdd\s+if=.*\bof=/dev/",
    r":\(\)\s*\{.*\};:",  # fork bomb
    r"\bchmod\s+-R\s+777\s+/",
    r">\s*/dev/sd[a-z]",
    r"\btruncate\s+-s\s*0\b",
]

# These are *blocked by default* because they are rarely intentional mid-goal.
DESTRUCTIVE_DESC = {
    r"\bgit\s+reset\s+--hard\b": "git reset --hard discards uncommitted work",
    r"\bgit\s+clean\s+-[a-zA-Z]*f[a-zA-Z]*d": "git clean -fd deletes untracked files",
    r"\bgit\s+push\s+.*(--force|-f)\b": "force-push can destroy remote history",
}


def _destructive_reason(cmd: str) -> str:
    for pat in DESTRUCTIVE_PATTERNS:
        if re.search(pat, cmd):
            for dpat, desc in DESTRUCTIVE_DESC.items():
                if re.search(dpat, cmd):
                    return desc
            return f"matches a destructive command pattern ({pat})"
    return ""


def _forbidden_reason(cmd: str, state: dict) -> str:
    # Path-based blocking only. We deliberately do NOT try to infer "forbidden
    # actions" from free-text keywords — that produced false positives (any
    # command containing a common word got blocked) and false negatives.
    # Forbidden *actions* are enforced by goalkeeper-audit reading the diff,
    # not by guessing intent from a shell string.
    for fp in state.get("forbidden_paths", []):
        token = fp.strip().rstrip("/*").rstrip("/")
        if token and token in cmd:
            return f"command references forbidden path: {fp}"
    return ""


# --------------------------------------------------------------------------- #
# Response builders (Claude Code hook JSON schema)
# --------------------------------------------------------------------------- #
def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()


def _emit_context(event: str, text: str) -> None:
    if not text:
        return
    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": text,
            }
        }
    )


def _emit_deny(event: str, reason: str) -> None:
    msg = f"[Goalkeeper] Blocked: {reason}"
    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": event,
                "permissionDecision": "deny",
                "permissionDecisionReason": msg,
            }
        }
    )


def _emit_continue(reason: str) -> None:
    # For Stop hooks, decision=block tells the host to keep going. The `reason`
    # field is ignored by the model, so the actual guidance must be surfaced via
    # hookSpecificOutput.additionalContext. We emit both for safety/portability.
    _emit(
        {
            "decision": "block",
            "reason": reason,
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": reason,
            },
        }
    )


# --------------------------------------------------------------------------- #
# Event handlers
# --------------------------------------------------------------------------- #
def handle_session_or_prompt(event: str, root: Path, state: dict) -> None:
    _emit_context(event, _contract_summary(root, state))


def handle_pretooluse(event: str, root: Path, state: dict, payload: dict) -> None:
    tool = _tool_name(payload).lower()
    cmd = _command_text(payload)
    if not cmd:
        return
    # Only screen shell-ish tools.
    if tool and not any(t in tool for t in ("bash", "shell", "exec", "command")):
        return
    reason = _destructive_reason(cmd)
    if not reason and state:
        reason = _forbidden_reason(cmd, state)
    if reason:
        _log_event(root, {"event": event, "blocked": True, "reason": reason, "cmd": cmd[:200]})
        _emit_deny(event, reason)


def handle_stop(event: str, root: Path, state: dict) -> None:
    if not state:
        return
    if not state.get("autocontinue"):
        return
    if state.get("status") not in ("active", "draft"):
        return
    used = int(state.get("autocontinue_turns_used", 0))
    budget = int(state.get("max_autocontinue_turns", 0))
    if used >= budget:
        return
    # All checkpoints met? Then let it stop.
    cps = state.get("checkpoints", [])
    if cps and all(c.get("met") for c in cps):
        return
    state["autocontinue_turns_used"] = used + 1
    _save_state(root, state)
    open_cps = [c["id"] for c in cps if not c.get("met")]
    reason = (
        f"[Goalkeeper] Bounded auto-continue {used + 1}/{budget}. "
        f"Goal not yet complete. Remaining checkpoints: "
        f"{', '.join(open_cps) or 'see goal.md'}. "
        "Continue working inside the allowed scope; record evidence in "
        ".goalkeeper/work_log.md. Stop if you need credentials/human input."
    )
    _log_event(root, {"event": event, "autocontinue": used + 1, "budget": budget})
    _emit_continue(reason)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    root = _project_root(payload)
    state = _load_state(root)
    event = _event_name(payload)

    # Always log (best-effort) the event arrival.
    _log_event(root, {"event": event or "unknown", "tool": _tool_name(payload)})

    el = event.lower()
    if el in ("sessionstart", "userpromptsubmit", "subagentstart", "subagentstop_start"):
        handle_session_or_prompt(event, root, state)
    elif el in ("pretooluse",):
        handle_pretooluse(event, root, state, payload)
    elif el in ("stop", "subagentstop"):
        # Only the top-level Stop drives auto-continue.
        if el == "stop":
            handle_stop(event, root, state)
    # All other events: log only, no output.
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # never crash the host
        sys.exit(0)
