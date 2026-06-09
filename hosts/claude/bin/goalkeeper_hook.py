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
  * PreToolUse (Edit/Write, Codex apply_patch)
        -> deny writes outside allowed scope / inside forbidden scope.
  * PostToolUse (Bash/shell tool)
        -> auto-record the command + exit code into runs.jsonl as evidence.
  * Stop
        -> gate-aware: stop, pause, continue (bounded), or auto-complete on a pass.
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

from goalkeeper_core import gate as gk_gate  # noqa: E402
from goalkeeper_core import ledger as gk_ledger  # noqa: E402
from goalkeeper_core import loop as gk_loop  # noqa: E402
from goalkeeper_core import proof as gk_proof  # noqa: E402
from goalkeeper_core.clock import now  # noqa: E402
from goalkeeper_core.matching import matches_any  # noqa: E402
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
# Write-boundary scope enforcement (Edit/Write on Claude, apply_patch on Codex)
# --------------------------------------------------------------------------- #
WRITE_TOOL_MARKERS = ("edit", "write", "apply_patch", "applypatch", "str_replace", "create_file")
_PATCH_FILE_RE = re.compile(r"^\*\*\*\s+(?:Add|Update|Delete) File:\s*(.+?)\s*$", re.MULTILINE)


def _is_write_tool(tool: str) -> bool:
    return any(t in tool for t in WRITE_TOOL_MARKERS)


def _patch_targets(body: str) -> list[str]:
    return [m.group(1).strip() for m in _PATCH_FILE_RE.finditer(body)]


def _write_paths(payload: dict) -> list[str]:
    """Target file path(s) for a write tool, across Claude (Edit/Write) and Codex
    (apply_patch) shapes. Returns [] when a path can't be determined (-> allow)."""
    ti = payload.get("tool_input") or payload.get("toolInput") or {}
    paths: list[str] = []
    if isinstance(ti, dict):
        for k in ("file_path", "filePath", "path"):
            v = ti.get(k)
            if isinstance(v, str) and v:
                paths.append(v)
        for k in ("input", "patch", "content", "command", "text"):
            v = ti.get(k)
            if isinstance(v, str) and "*** " in v:
                paths.extend(_patch_targets(v))
                break
    elif isinstance(ti, str) and "*** " in ti:
        paths.extend(_patch_targets(ti))
    return list(dict.fromkeys(paths))


def _rel_to_root(path: str, root: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(root.resolve()))
    except (ValueError, OSError):
        return path  # outside the repo (or unresolvable): keep as-is -> fails an allow-list


def _scope_write_reason(payload: dict, root: Path, state: dict) -> str:
    scope = state.get("scope", {})
    allowed = scope.get("allowed_resources", []) or []
    forbidden = scope.get("forbidden_resources", []) or []
    if not allowed and not forbidden:
        return ""  # unrestricted scope
    for raw in _write_paths(payload):
        rel = _rel_to_root(raw, root)
        if forbidden and matches_any(rel, forbidden):
            return f"write to {rel} hits forbidden scope ({', '.join(forbidden)})"
        if allowed and not matches_any(rel, allowed):
            return f"write to {rel} is outside allowed scope ({', '.join(allowed)})"
    return ""


# --------------------------------------------------------------------------- #
# PostToolUse evidence auto-capture
# --------------------------------------------------------------------------- #
def _exit_code(payload: dict):
    """Best-effort exit code from a PostToolUse payload, or None if undeterminable.

    PostToolUse cannot dependably carry an exit code (see ledger.py); when it
    can't, we record nothing rather than fabricate a pass/fail.
    """
    tr = payload.get("tool_response") or payload.get("toolResponse") or {}
    if isinstance(tr, dict):
        for k in ("exit_code", "exitCode", "returncode", "exit", "code"):
            v = tr.get(k)
            if isinstance(v, bool):
                continue
            if isinstance(v, int):
                return v
            if isinstance(v, str) and v.strip().lstrip("-").isdigit():
                return int(v)
    for k in ("exit_code", "exit", "returncode"):
        v = payload.get(k)
        if isinstance(v, int) and not isinstance(v, bool):
            return v
    return None


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
    # Only ever "deny" (or allow-by-silence): Claude Code and Codex both honor a
    # deny decision, but Codex parses-and-ignores "ask", so never emit "ask".
    _emit({"hookSpecificOutput": {
        "hookEventName": event,
        "permissionDecision": "deny",
        "permissionDecisionReason": f"[Goalkeeper] Blocked: {reason}",
    }})


def _emit_continue(reason: str) -> None:
    # Cross-host on purpose: Claude Code feeds `additionalContext` back to the
    # model (its `reason` is UI-only), while Codex builds its continuation prompt
    # from `reason`. Emitting both makes the same payload work on either host.
    _emit({"decision": "block", "reason": reason,
           "hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": reason}})


# --------------------------------------------------------------------------- #
# Event handlers
# --------------------------------------------------------------------------- #
def handle_session_or_prompt(event: str, state: dict) -> None:
    _emit_context(event, _contract_summary(state))


def handle_pretooluse(event: str, root: Path, state: dict, payload: dict) -> None:
    tool = _tool_name(payload).lower()
    # Write tools (Edit/Write on Claude, apply_patch on Codex): enforce scope at
    # the write boundary -- deny edits outside allowed / inside forbidden paths.
    if _is_write_tool(tool):
        if state:
            reason = _scope_write_reason(payload, root, state)
            if reason:
                _log_event(root, {"event": event, "blocked": True, "reason": reason, "tool": tool})
                _emit_deny(event, reason)
        return
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


def handle_posttooluse(event: str, root: Path, state: dict, payload: dict) -> None:
    """Auto-capture shell commands into runs.jsonl so the gate has evidence even
    when the agent never wrapped a command in `goalkeeper run`."""
    if not state:
        return
    tool = _tool_name(payload).lower()
    if tool and not any(t in tool for t in ("bash", "shell", "exec", "command")):
        return
    cmd = _command_text(payload)
    if not cmd or re.search(r"\bgoalkeeper\s+run\b", cmd):
        return  # `goalkeeper run` already records itself
    code = _exit_code(payload)
    if code is None:
        return  # exit undeterminable -> don't fabricate evidence
    try:
        gk_ledger.record_run(cmd, code, root, source="posttooluse")
    except OSError:
        pass


def _enforcement_on(state: dict) -> bool:
    """Whether the Stop gate is active for this contract.

    On when the contract opts in (`loop.enforce`, set by templates and
    init --auto/adopt) or the explicit `autocontinue` switch is set.
    `GOALKEEPER_NO_STOP=1` is a hard kill switch regardless.
    """
    if os.environ.get("GOALKEEPER_NO_STOP"):
        return False
    loop = state.get("loop", {})
    rt = state.get("loop_runtime", {})
    return bool((isinstance(loop, dict) and loop.get("enforce")) or rt.get("autocontinue"))


def _finalize_or_prompt(event: str, root: Path, state: dict, g: dict) -> None:
    """Gate passed on an active goal: auto-record completion, or ask a human."""
    loop = state.get("loop", {})
    auto = isinstance(loop, dict) and loop.get("auto_complete", True)
    if auto and not gk_loop.requires_human_signoff(state):
        fg = gk_gate.finalize(state, root, "auto:goalkeeper")
        if fg:
            save_state(state, root)
            gk_proof.write_bundle(state, root, fmt="both")
            _log_event(root, {"event": event, "auto_complete": True, "tier": fg["tier"]})
            _emit_context(event, f"[Goalkeeper] Gate passed (tier {fg['tier']}/6); completion "
                                 "recorded (auto:goalkeeper) and proof bundle written to "
                                 ".goalkeeper/proof.md.")
            return
    _log_event(root, {"event": event, "gate": "COMPLETE", "awaiting_human": True})
    _emit_context(event, f"[Goalkeeper] Gate passed (tier {g['tier']}/6). This contract needs a "
                         "named human to accept: run `goalkeeper complete --accepted-by <name>`.")


def handle_stop(event: str, root: Path, state: dict) -> None:
    if not state or not _enforcement_on(state):
        return
    decision = gk_loop.decide_stop(state, root)
    g = decision.gate
    if decision.action == "stop":
        # Gate passed (or the goal is no longer active). If it's an active goal
        # whose gate passed, close the loop instead of silently stopping.
        if g and g.get("verdict") == "COMPLETE" and \
                state.get("completion", {}).get("status") in ("active", "draft"):
            _finalize_or_prompt(event, root, state, g)
        return
    if decision.action == "pause":
        _log_event(root, {"event": event, "decision": "pause"})
        _emit_context(event, decision.reason)
        return
    # continue (bounded by the turn budget tracked in loop_runtime)
    rt = state.setdefault("loop_runtime", {})
    used = int(rt.get("autocontinue_turns_used", 0))
    budget = int(state.get("loop", {}).get("max_turns", 0))
    if used >= budget:
        _log_event(root, {"event": event, "decision": "pause", "reason": "turn budget exhausted"})
        _emit_context(event, f"[Goalkeeper] Turn budget exhausted ({used}/{budget}); pausing. "
                             "Raise it with `goalkeeper autocontinue on --max N` if more turns are warranted.")
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
    elif el == "posttooluse":
        handle_posttooluse(event, root, state, payload)
    elif el == "stop":
        handle_stop(event, root, state)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # never crash the host
        sys.exit(0)
