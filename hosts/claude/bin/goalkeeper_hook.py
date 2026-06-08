#!/usr/bin/env python3
"""goalkeeper_hook.py - conservative cross-host hook for Goalkeeper.

Reads a hook event as JSON on stdin and writes a hook response as JSON on
stdout. Defensive: the same script serves Claude Code and Codex; unknown event
shapes are handled gracefully and never crash the host (any internal error
exits 0 = "do nothing").

Behavior:
  * SessionStart / UserPromptSubmit / subagent start
        -> inject the active .goalkeeper Goal Contract summary as context.
  * PreToolUse (Bash/shell tool)
        -> block obvious destructive commands and forbidden-resource access.
  * Stop
        -> gate-aware: ask core whether to stop, pause, or continue (bounded).
  * Every event appended to .goalkeeper/events.jsonl.
"""
import json
import os
import re
import sys


def _bootstrap():
    here = os.path.dirname(os.path.realpath(__file__))
    override = os.environ.get("GOALKEEPER_CORE_HOME")
    candidates = [override] if override else []
    cur = here
    for _ in range(8):
        candidates.append(cur)
        cur = os.path.dirname(cur)
    for root in candidates:
        if root and os.path.isfile(os.path.join(root, "goalkeeper_core", "__init__.py")):
            if root not in sys.path:
                sys.path.insert(0, root)
            return
    sys.path.insert(0, os.path.abspath(os.path.join(here, "..")))


_bootstrap()

from pathlib import Path  # noqa: E402

from goalkeeper_core import loop as gk_loop  # noqa: E402
from goalkeeper_core.clock import now  # noqa: E402
from goalkeeper_core.paths import GK_DIR  # noqa: E402
from goalkeeper_core.state import load_state, save_state  # noqa: E402


# --------------------------------------------------------------------------- #
# Locating project state
# --------------------------------------------------------------------------- #
def _project_root(payload: dict) -> Path:
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


def _log_event(root: Path, record: dict) -> None:
    try:
        path = _gk(root, "events.jsonl")
        if not path.parent.is_dir():
            return
        record["ts"] = now()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass


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
# Context injection
# --------------------------------------------------------------------------- #
def _contract_summary(state: dict) -> str:
    if not state or state.get("completion", {}).get("status") in ("complete", "abandoned"):
        return ""
    goal = state.get("goal", {})
    scope = state.get("scope", {})
    lines = ["[Goalkeeper] Active Goal Contract is in effect (.goalkeeper/)."]
    if goal.get("objective"):
        lines.append(f"Objective: {goal['objective']}")
    if scope.get("allowed_resources"):
        lines.append("Allowed: " + ", ".join(scope["allowed_resources"]))
    if scope.get("forbidden_resources"):
        lines.append("Forbidden paths: " + ", ".join(scope["forbidden_resources"]))
    if scope.get("forbidden_actions"):
        lines.append("Forbidden actions: " + ", ".join(scope["forbidden_actions"]))
    vals = [v.get("command") or v.get("id") for v in state.get("validators", [])]
    if vals:
        lines.append("Validators (must pass): " + ", ".join(str(v) for v in vals))
    cps = state.get("checkpoints", [])
    if cps:
        met = sum(1 for c in cps if c.get("status") == "met")
        lines.append(f"Checkpoints: {met}/{len(cps)} met. Record evidence in .goalkeeper/work_log.md.")
    risk = state.get("risk", {})
    if risk.get("level") in ("high", "critical") or risk.get("external_side_effects"):
        lines.append(f"Risk: {risk.get('level')} (external side effects: {risk.get('external_side_effects')}). "
                     "Get approval before irreversible/external actions.")
    lines.append("Stay inside allowed scope. Capture tangents in the work_log parking lot. "
                 "Do not claim done without evidence.")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Destructive / forbidden command screening
# --------------------------------------------------------------------------- #
DESTRUCTIVE_PATTERNS = [
    r"\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rf][a-zA-Z]*\b.*\s+/(?:\s|$)",
    r"\brm\s+-rf?\s+(--no-preserve-root|/|~|\$HOME|\*)\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-zA-Z]*f[a-zA-Z]*d",
    r"\bgit\s+checkout\s+--\s+\.",
    r"\bgit\s+push\s+.*--force\b",
    r"\bgit\s+push\s+.*-f\b",
    r"\bmkfs(\.\w+)?\b",
    r"\bdd\s+if=.*\bof=/dev/",
    r":\(\)\s*\{.*\};:",
    r"\bchmod\s+-R\s+777\s+/",
    r">\s*/dev/sd[a-z]",
    r"\btruncate\s+-s\s*0\b",
]
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
    for fp in state.get("scope", {}).get("forbidden_resources", []):
        token = fp.strip().rstrip("/*").rstrip("/")
        if token and token in cmd:
            return f"command references forbidden path: {fp}"
    return ""


# --------------------------------------------------------------------------- #
# Response builders
# --------------------------------------------------------------------------- #
def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()


def _emit_context(event: str, text: str) -> None:
    if not text:
        return
    _emit({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})


def _emit_deny(event: str, reason: str) -> None:
    _emit({"hookSpecificOutput": {
        "hookEventName": event,
        "permissionDecision": "deny",
        "permissionDecisionReason": f"[Goalkeeper] Blocked: {reason}",
    }})


def _emit_continue(reason: str) -> None:
    _emit({"decision": "block", "reason": reason,
           "hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": reason}})


# --------------------------------------------------------------------------- #
# Event handlers
# --------------------------------------------------------------------------- #
def handle_session_or_prompt(event: str, state: dict) -> None:
    _emit_context(event, _contract_summary(state))


def handle_pretooluse(event: str, root: Path, state: dict, payload: dict) -> None:
    tool = _tool_name(payload).lower()
    cmd = _command_text(payload)
    if not cmd:
        return
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
    # Only act when autocontinue is explicitly enabled (native /goal is preferred).
    rt = state.get("loop_runtime", {})
    if not rt.get("autocontinue"):
        return
    decision = gk_loop.decide_stop(state, root)
    if decision.action == "stop":
        return
    if decision.action == "pause":
        _log_event(root, {"event": event, "decision": "pause"})
        _emit_context(event, decision.reason)
        return
    # continue (bounded by the turn budget tracked in loop_runtime)
    used = int(rt.get("autocontinue_turns_used", 0))
    budget = int(state.get("loop", {}).get("max_turns", 0))
    if used >= budget:
        return
    rt["autocontinue_turns_used"] = used + 1
    save_state(state, root)
    _log_event(root, {"event": event, "autocontinue": used + 1, "budget": budget})
    _emit_continue(decision.reason)


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
    try:
        state = load_state(root)
    except Exception:
        state = {}
    event = _event_name(payload)
    _log_event(root, {"event": event or "unknown", "tool": _tool_name(payload)})

    el = event.lower()
    if el in ("sessionstart", "userpromptsubmit", "subagentstart"):
        handle_session_or_prompt(event, state)
    elif el == "pretooluse":
        handle_pretooluse(event, root, state, payload)
    elif el == "stop":
        handle_stop(event, root, state)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # never crash the host
        sys.exit(0)
