#!/usr/bin/env python3
"""goalkeeper CLI — argparse wiring + command dispatch over goalkeeper_core."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import SCHEMA_VERSION, __version__
from . import autocontract as autocontract_mod
from . import contract as contract_mod
from . import detect as detect_mod
from . import gate as gate_mod
from . import hostdoctor as hostdoctor_mod
from . import install as install_mod
from . import packets as packets_mod
from . import proof as proof_mod
from . import quality as quality_mod
from . import render as render_mod
from . import risk as risk_mod
from . import schema as schema_mod
from . import smoke as smoke_mod
from . import templates as templates_mod
from .ledger import log as ledger_log
from .ledger import run_command
from .paths import GOAL_FILE, GK_DIR, LOG_FILE, STATE_FILE, find_root, gk_path
from .state import (
    coerce,
    get_path,
    load_state,
    save_state,
    set_path,
)


def _die(msg: str, code: int = 1) -> int:
    print(f"goalkeeper: error: {msg}", file=sys.stderr)
    sys.exit(code)


def _need_state() -> dict:
    state = load_state()
    if not state:
        _die("no state.json; run `goalkeeper init` first")
    return state


def _render_goal_md(state: dict, root: Path) -> None:
    gk_path(GOAL_FILE, root).write_text(render_mod.render(state, "md"), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_init(args: argparse.Namespace) -> int:
    base = Path.cwd() / GK_DIR
    base.mkdir(parents=True, exist_ok=True)
    state_path = base / STATE_FILE
    root = Path.cwd()
    if state_path.exists() and not args.force:
        print(f"{GK_DIR}/ already initialized (use --force to reset state.json).")
    else:
        _reset_runtime_evidence(base)
        if args.auto:
            state = autocontract_mod.build_auto_contract(args.objective or "", root)
        elif args.template:
            try:
                state = templates_mod.build_from_template(args.template, args.objective or "", root)
            except KeyError:
                return _die(f"unknown template {args.template!r}; choose from {templates_mod.template_names()}")
        else:
            state = contract_mod.default_contract(args.objective or "", domain=args.domain or "code", root=root)
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    state = load_state(root)
    _render_goal_md(state, root)
    _ensure(base / LOG_FILE, _log_template())
    _ensure(base / "events.jsonl", "")
    print(f"Initialized {GK_DIR}/ at {base}")
    if args.auto:
        print("Next: run the required validators with `goalkeeper run`, then mark checkpoint evidence.")
    else:
        print("Next: `goalkeeper set ...`, `goalkeeper doctor`, then `goalkeeper render --format prompt`.")
    return 0


def cmd_adopt(args: argparse.Namespace) -> int:
    root = Path.cwd()
    base = root / GK_DIR
    base.mkdir(parents=True, exist_ok=True)
    state_path = base / STATE_FILE
    if state_path.exists() and not args.force:
        return _die(f"{GK_DIR}/ already initialized (use --force to replace it)")
    _reset_runtime_evidence(base)
    state = autocontract_mod.build_auto_contract(args.objective or "", root, adopt=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    _render_goal_md(state, root)
    _ensure(base / LOG_FILE, _log_template())
    _ensure(base / "events.jsonl", "")
    print(f"Adopted current work into {GK_DIR}/ at {base}")
    print("Next: `goalkeeper status`, then run validators and record checkpoint evidence.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state = _need_state()
    goal = state.get("goal", {})
    goal = goal if isinstance(goal, dict) else {}
    cps = state.get("checkpoints", [])
    cps = cps if isinstance(cps, list) else []
    validators = state.get("validators", [])
    validators = validators if isinstance(validators, list) else []
    risk = state.get("risk", {})
    risk = risk if isinstance(risk, dict) else {}
    loop = state.get("loop", {})
    loop = loop if isinstance(loop, dict) else {}
    scope = state.get("scope", {})
    scope = scope if isinstance(scope, dict) else {}
    completion = state.get("completion", {})
    completion = completion if isinstance(completion, dict) else {}
    met = sum(1 for c in cps if isinstance(c, dict) and c.get("status") == "met")
    print(f"status      : {completion.get('status', '?')}")
    print(f"objective   : {goal.get('objective') or '(unset)'}")
    print(f"domain      : {goal.get('domain', 'code')}  priority: {goal.get('priority', '?')}")
    print(f"checkpoints : {met}/{len(cps)} met")
    print(f"validators  : {len(validators)}")
    print(f"allowed     : {', '.join(scope.get('allowed_resources', [])) or '(none)'}")
    print(f"forbidden   : {', '.join(scope.get('forbidden_resources', [])) or '(none)'}")
    print(f"risk        : {risk.get('level', '?')}  external_side_effects: {risk.get('external_side_effects', False)}")
    print(f"loop        : {loop.get('mode')}  max_turns: {loop.get('max_turns')}")
    print(f"locked      : {contract_mod.is_locked(state)}")
    print(f"next        : {_next_action(state, find_root())}")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    state = _need_state()
    field = args.field
    if field == "completion.status" and args.value == "complete":
        return _die("set completion.status=complete is not allowed; use `goalkeeper complete`")
    if contract_mod.is_locked(state) and field.split(".")[0] in contract_mod.CONTRACT_SECTIONS:
        return _die("contract is locked; `goalkeeper contract-unlock --reason ...` to amend")
    value = coerce(field, args.value)
    set_path(state, field, value)
    # Capture diff baseline when the goal first becomes active.
    if field == "completion.status" and value == "active" and not state.get("base_ref"):
        from .gitio import git_head
        state["base_ref"] = git_head()
    save_state(state)
    _render_goal_md(state, find_root())
    print(f"set {field} = {value!r}")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    state = _need_state()
    print(json.dumps(get_path(state, args.field)))
    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    root = find_root()
    stacks = detect_mod.detect_stack(root)
    if not stacks:
        print("No known stack markers detected.")
        return 0
    print("Detected stack(s): " + ", ".join(s["name"] for s in stacks))
    cmds = detect_mod.suggested_validations(root)
    print("\nSuggested validation commands:")
    for c in cmds:
        print(f"  - {c}")
    if args.apply:
        state = load_state()
        if state:
            state["validators"] = detect_mod.command_validators(cmds)
            save_state(state)
            _render_goal_md(state, root)
            print("\nApplied suggested command validators to state.json.")
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    root = find_root()
    f = detect_mod.seed_findings(root)
    if args.json:
        print(json.dumps(f, indent=2))
        return 0
    print("Project policy scan:")
    print("  policy files     : " + (", ".join(f["policy_files"]) or "(none)"))
    print("  suggested checks : " + (", ".join(f["validations"]) or "(none)"))
    print("  suggest forbid   : " + (", ".join(f["suggested_forbidden"]) or "(none)"))
    for note in f["notes"]:
        print(f"  note             : {note}")
    if args.apply:
        state = load_state()
        if state:
            if f["validations"]:
                state["validators"] = detect_mod.command_validators(f["validations"])
            if f["suggested_forbidden"]:
                cur = state.setdefault("scope", {}).setdefault("forbidden_resources", [])
                state["scope"]["forbidden_resources"] = list(dict.fromkeys(cur + f["suggested_forbidden"]))
            save_state(state)
            _render_goal_md(state, root)
            print("\nApplied suggested validators + forbidden resources to state.json.")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    state = _need_state()
    out = render_mod.render(state, args.format)
    if args.format == "md":
        _render_goal_md(state, find_root())
    if args.format == "prompt":
        print("/goal " + out)
    else:
        print(out)
    return 0


def cmd_generate_goal(args: argparse.Namespace) -> int:
    state = _need_state()
    print("/goal " + render_mod.build_goal_prompt(state))
    return 0


def cmd_checkpoint(args: argparse.Namespace) -> int:
    state = _need_state()
    cps = state.setdefault("checkpoints", [])
    if args.add:
        new_id = f"cp{len(cps) + 1}"
        cps.append({"id": new_id, "description": args.add, "evidence_required": "evidence", "status": "pending", "evidence": ""})
        save_state(state)
        _render_goal_md(state, find_root())
        print(f"added {new_id}: {args.add}")
        return 0
    if args.id:
        target = next((c for c in cps if c["id"] == args.id), None)
        if not target:
            return _die(f"no checkpoint with id {args.id}")
        if args.evidence:
            target["evidence"] = args.evidence
        if args.met:
            target["status"] = "met"
        save_state(state)
        _render_goal_md(state, find_root())
        ledger_log(f"checkpoint {args.id} {target['status']}: {target.get('evidence', '')}")
        print(f"updated {args.id} (status={target['status']})")
        return 0
    for c in cps:
        mark = "x" if c.get("status") == "met" else " "
        print(f"  [{mark}] {c['id']}: {c['description']}")
        if c.get("evidence"):
            print(f"        evidence: {c['evidence']}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    print(f"[goalkeeper] running: {args.command}", file=sys.stderr)
    rc = run_command(args.command)
    print(f"[goalkeeper] {args.command} -> exit {rc} (recorded)", file=sys.stderr)
    return rc


def cmd_validate_contract(args: argparse.Namespace) -> int:
    state = _need_state()
    errors = schema_mod.validate(state, strict=args.strict)
    if args.json:
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    else:
        if not errors:
            print(f"contract is valid (schema v{SCHEMA_VERSION}{', strict' if args.strict else ''}).")
        else:
            print(f"contract is INVALID ({len(errors)} error(s)):")
            for e in errors:
                print(f"  - {e}")
    return 0 if not errors else 2


def cmd_doctor(args: argparse.Namespace) -> int:
    state = _need_state()
    errors = schema_mod.validate(state, strict=True)
    checks = quality_mod.contract_quality_checks(state, require_active=False)

    passed = sum(1 for c in checks if c.ok)
    total = len(checks)
    pct = round(100 * passed / total)
    if args.json:
        print(json.dumps({"contract_quality": pct, "passed": passed, "total": total,
                          "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail,
                                      "blocker": c.blocker} for c in checks],
                          "schema_errors": errors}, indent=2))
    else:
        print(f"contract quality: {pct}% ({passed}/{total} checks)\n")
        for c in checks:
            line = f"  [{'PASS' if c.ok else 'FAIL'}] {c.name}"
            if c.detail:
                line += f"  ({c.detail})"
            print(line)
        if errors:
            print("\nschema errors:")
            for e in errors:
                print(f"  - {e}")
    return 0 if pct == 100 else 2


def cmd_score(args: argparse.Namespace) -> int:
    state = _need_state()
    root = find_root()
    g = gate_mod.evaluate_gate(state, root, base_override=args.base)
    report = {
        "verdict": g["verdict"],
        "completion_tier": g["tier"],
        "changed_files": len(g["changed"]),
        "blockers": [{"code": c, "detail": d} for c, d in g["blockers"]],
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"verdict        : {g['verdict']}")
        print(f"Completion tier: {g['tier']}/6")
        print(f"changed files  : {len(g['changed'])}")
        if g["blockers"]:
            print("blockers:")
            for c, d in g["blockers"]:
                print(f"  - {c}: {d}")
        else:
            print("blockers       : none")
    return 0 if g["verdict"] == "COMPLETE" else 2


def _rerun_required_commands(state: dict, root: Path) -> list[str]:
    """Re-execute every required `command` validator from a clean state, tagging
    each run so it can legitimately prove tier 4 (independent re-run)."""
    rerun: list[str] = []
    for v in state.get("validators", []):
        if not isinstance(v, dict):
            continue
        if v.get("required") and v.get("type") == "command" and v.get("command"):
            print(f"[goalkeeper] re-running: {v['command']}", file=sys.stderr)
            run_command(v["command"], root, record_extra={"rerun": True})
            rerun.append(v["command"])
    return rerun


def cmd_gate(args: argparse.Namespace) -> int:
    state = _need_state()
    root = find_root()
    if getattr(args, "rerun", False):
        ran = _rerun_required_commands(state, root)
        if not ran:
            print("[goalkeeper] --rerun: no required command validators to re-run", file=sys.stderr)
    g = gate_mod.evaluate_gate(state, root)
    if args.json:
        print(json.dumps({"verdict": g["verdict"], "tier": g["tier"],
                          "blockers": [{"code": c, "detail": d} for c, d in g["blockers"]]}, indent=2))
    elif args.ci:
        print(f"GOALKEEPER_VERDICT={g['verdict']} TIER={g['tier']}/6 BLOCKERS={len(g['blockers'])}")
        for c, d in g["blockers"]:
            print(f"::{c}:: {d}")
    else:
        print(f"Verdict: {g['verdict']}")
        print(f"Completion tier: {g['tier']}/6")
        for c, d in g["blockers"]:
            print(f"  - {c}: {d}")
    return 0 if g["verdict"] == "COMPLETE" else 2


def cmd_complete(args: argparse.Namespace) -> int:
    state = _need_state()
    root = find_root()
    g = gate_mod.evaluate_gate(state, root)
    if g["verdict"] != "COMPLETE":
        print("gate failed; cannot complete. Blockers:", file=sys.stderr)
        for c, d in g["blockers"]:
            print(f"  - {c}: {d}", file=sys.stderr)
        return 2
    if not args.accepted_by:
        return _die("--accepted-by NAME is required to accept completion")
    g = gate_mod.finalize(state, root, args.accepted_by)
    if g is None:  # gate flipped between check and write; refuse to record
        return _die("gate no longer passes; re-run `goalkeeper gate`", code=2)
    save_state(state)
    proof_mod.write_bundle(state, root, fmt="both")
    print(f"Goal marked complete (tier {g['tier']}/6). Proof bundle: .goalkeeper/proof.md")
    return 0


def cmd_proof(args: argparse.Namespace) -> int:
    state = _need_state()
    root = find_root()
    bundle = proof_mod.write_bundle(state, root, fmt=args.format)
    if args.format == "json":
        print(json.dumps(bundle, indent=2))
    else:
        print(f"Completion tier: {bundle['completion_tier']}/6  ->  {bundle['verdict']}")
        print("Proof bundle written to .goalkeeper/proof.md and proof.json")
    return 0 if bundle["verdict"] == "COMPLETE" else 2


def cmd_approve(args: argparse.Namespace) -> int:
    state = _need_state()
    entry = risk_mod.record_approval(state, args.what, args.by, args.note or "")
    save_state(state)
    ledger_log(f"APPROVAL: {entry['what']} by {entry['by']} ({entry['note']})")
    print(f"recorded approval: {entry['what']} by {entry['by']}")
    return 0


def cmd_contract_lock(args: argparse.Namespace) -> int:
    state = _need_state()
    contract_mod.lock(state)
    save_state(state)
    print(f"contract locked (hash {state['lock']['hash'][:12]}).")
    return 0


def cmd_contract_unlock(args: argparse.Namespace) -> int:
    state = _need_state()
    if not args.reason:
        return _die("--reason is required to unlock (records an amendment)")
    contract_mod.unlock(state, args.reason)
    save_state(state)
    print(f"contract unlocked; amendment recorded ({len(state['amendments'])} total).")
    return 0


def cmd_contract_diff(args: argparse.Namespace) -> int:
    state = _need_state()
    d = contract_mod.diff_against_lock(state)
    print(json.dumps(d, indent=2))
    return 0


def cmd_split(args: argparse.Namespace) -> int:
    state = _need_state()
    root = find_root()
    if args.write_packets:
        packets = packets_mod.write_packets(state, root)
        save_state(state)
        ok, conflicts = packets_mod.disjoint(packets)
        print(f"wrote {len(packets)} packet(s) to .goalkeeper/agent_packets.md")
        if not ok:
            print("WARNING: write-sets overlap:")
            for c in conflicts:
                print(f"  - {c}")
    else:
        for p in packets_mod.build_packets(state):
            print(f"  {p['id']} ({p['role']}): {', '.join(p['allowed_paths'])}")
    return 0


def cmd_packets(args: argparse.Namespace) -> int:
    state = _need_state()
    root = find_root()
    if args.action == "list":
        for p in packets_mod.list_packets(state):
            print(f"  [{p.get('status', 'pending')}] {p['id']} ({p['role']}): {', '.join(p['allowed_paths'])}")
        return 0
    if args.action == "run":
        if not args.packet_id:
            return _die("packets run requires a packet id, e.g. `packets run P1`")
        p = packets_mod.mark_packet(state, args.packet_id, "running")
        if not p:
            return _die(f"no packet {args.packet_id}")
        save_state(state)
        print(f"Packet {p['id']} scoped to: {', '.join(p['allowed_paths'])}")
        print("Launch a subagent with the prompt in .goalkeeper/agent_packets.md, "
              "then `goalkeeper packets reconcile`.")
        return 0
    if args.action == "reconcile":
        r = packets_mod.reconcile(state, root)
        print(f"disjoint write-sets: {r['disjoint']}")
        if r["conflicts"]:
            for c in r["conflicts"]:
                print(f"  conflict: {c}")
        if r["unclaimed"]:
            print("changed files not owned by any packet:")
            for f in r["unclaimed"]:
                print(f"  - {f}")
        return 0 if r["disjoint"] and not r["unclaimed"] else 2
    return _die(f"unknown packets action {args.action}")


def cmd_autocontinue(args: argparse.Namespace) -> int:
    state = _need_state()
    rt = state.setdefault("loop_runtime", {})
    rt["autocontinue"] = args.action == "on"
    # autocontinue is the explicit on/off switch for the Stop-hook gate: turning
    # it on enforces continuation; off is the kill switch (also clears loop.enforce).
    if args.action == "on":
        set_path(state, "loop.enforce", True)
    elif args.action == "off":
        set_path(state, "loop.enforce", False)
    if args.max is not None:
        rt["max_autocontinue_turns"] = args.max
        set_path(state, "loop.max_turns", args.max)
    if args.action == "reset":
        rt["autocontinue_turns_used"] = 0
    save_state(state)
    print(f"autocontinue {'on' if rt['autocontinue'] else 'off'}; "
          f"enforce {state.get('loop', {}).get('enforce')}; "
          f"budget {rt.get('max_autocontinue_turns')} turns, {rt.get('autocontinue_turns_used', 0)} used")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    ledger_log(args.message)
    print("logged.")
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    from . import mcp as mcp_mod
    return mcp_mod.serve()


def cmd_install(args: argparse.Namespace) -> int:
    try:
        result = install_mod.install(args.target, dry_run=args.dry_run)
    except ValueError as exc:
        return _die(str(exc))
    _print_action_result(result, as_json=args.json)
    return 0 if result["ok"] else 2


def cmd_uninstall(args: argparse.Namespace) -> int:
    try:
        result = install_mod.uninstall(args.target, dry_run=args.dry_run)
    except ValueError as exc:
        return _die(str(exc))
    _print_action_result(result, as_json=args.json)
    return 0 if result["ok"] else 2


def cmd_host(args: argparse.Namespace) -> int:
    if args.action != "doctor":
        return _die(f"unknown host action {args.action}")
    result = hostdoctor_mod.doctor(args.target)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"host doctor: {'OK' if result['ok'] else 'FAIL'} ({args.target})")
        for c in result["checks"]:
            status = "PASS" if c["ok"] else c["severity"].upper()
            line = f"  [{status}] {c['name']}: {c.get('detail', '')}"
            if c.get("fix") and not c["ok"]:
                line += f"  fix: {c['fix']}"
            print(line)
    return 0 if result["ok"] else 2


def cmd_smoke(args: argparse.Namespace) -> int:
    try:
        result = smoke_mod.smoke(args.target)
    except ValueError as exc:
        return _die(str(exc))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"smoke {args.target}: {'PASS' if result['ok'] else 'FAIL'}")
        before = result.get("before_gate", {}).get("verdict", "?")
        after = result.get("after_gate", {}).get("verdict", "?")
        print(f"  gate before evidence: {before}")
        print(f"  gate after evidence : {after}")
        if result.get("hook"):
            print(f"  hook deny check     : {'PASS' if result['hook']['ok'] else 'FAIL'}")
        if result.get("note"):
            print(f"  note                : {result['note']}")
    return 0 if result["ok"] else 2


# --------------------------------------------------------------------------- #
# Templates / helpers
# --------------------------------------------------------------------------- #
def _ensure(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _log_template() -> str:
    from .clock import now
    return f"""# Work Log (evidence ledger)

Created: {now()}

## Evidence
<!-- append: command, exit code, key output, file:line references -->

## Parking lot (out-of-scope ideas; do NOT act on these mid-goal)
<!-- capture tempting tangents here instead of doing them -->
"""


def _print_action_result(result: dict, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(result, indent=2))
        return
    print(f"{result['action']}: {'OK' if result['ok'] else 'FAIL'}" + (" (dry-run)" if result["dry_run"] else ""))
    for step in result["steps"]:
        status = "PASS" if step["ok"] else "FAIL"
        print(f"  [{status}] {step['target']}: {step.get('detail') or step.get('error')}")
        print(f"        {step['source']} -> {step['dest']}")


def _reset_runtime_evidence(base: Path) -> None:
    for name in ("runs.jsonl", "events.jsonl", "work_log.md", "proof.md", "proof.json", "agent_packets.md"):
        path = base / name
        if path.exists() or path.is_symlink():
            path.unlink()
    artifacts = base / "artifacts"
    if artifacts.is_dir():
        shutil.rmtree(artifacts)


def _next_action(state: dict, root: Path) -> str:
    completion = state.get("completion", {})
    completion = completion if isinstance(completion, dict) else {}
    status = completion.get("status")
    if status not in ("active", "complete"):
        return "goalkeeper set completion.status active"
    g = gate_mod.evaluate_gate(state, root)
    if g["verdict"] == "COMPLETE":
        if status != "complete":
            return "goalkeeper complete --accepted-by <name>"
        return "goalkeeper proof"
    code, detail = g["blockers"][0] if g["blockers"] else ("unknown", "run goalkeeper gate")
    if code in ("validator_missing", "required_validator_missing"):
        return "goalkeeper detect --apply"
    if code == "validator_inconclusive":
        return f"goalkeeper run <required command>  ({detail})"
    if code == "checkpoint_unmet":
        return f"goalkeeper checkpoint --id {detail} --evidence \"...\" --met"
    if code == "checkpoint_no_evidence":
        return f"goalkeeper checkpoint --id {detail} --evidence \"...\""
    if code == "scope_missing":
        return "goalkeeper set scope.allowed_resources \"src/**,tests/**\""
    if code == "approval_required":
        return "goalkeeper approve <what> --by <name>"
    return f"resolve gate blocker: {code}: {detail}"


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="goalkeeper", description="Evidence-first control plane for agentic work.")
    p.add_argument("--version", action="version", version=f"goalkeeper {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="scaffold .goalkeeper state files")
    pi.add_argument("-o", "--objective", default="")
    pi.add_argument("--template", help=f"one of {templates_mod.template_names()}")
    pi.add_argument("--domain", help="code|research|writing|ops")
    pi.add_argument("--auto", action="store_true", help="inspect the repo and create an active code contract")
    pi.add_argument("--force", action="store_true")
    pi.set_defaults(func=cmd_init)

    padopt = sub.add_parser("adopt", help="create a contract around the current git diff")
    padopt.add_argument("-o", "--objective", default="")
    padopt.add_argument("--force", action="store_true")
    padopt.set_defaults(func=cmd_adopt)

    sub.add_parser("status", help="print status summary").set_defaults(func=cmd_status)

    pset = sub.add_parser("set", help="set a nested field (dotted path)")
    pset.add_argument("field"); pset.add_argument("value")
    pset.set_defaults(func=cmd_set)

    pget = sub.add_parser("get", help="get a nested field (dotted path)")
    pget.add_argument("field"); pget.set_defaults(func=cmd_get)

    pd = sub.add_parser("detect", help="detect stack & suggest validators")
    pd.add_argument("--apply", action="store_true"); pd.set_defaults(func=cmd_detect)

    pseed = sub.add_parser("seed", help="mine repo policy to seed the contract")
    pseed.add_argument("--apply", action="store_true"); pseed.add_argument("--json", action="store_true")
    pseed.set_defaults(func=cmd_seed)

    prender = sub.add_parser("render", help="render goal.md | /goal prompt | json")
    prender.add_argument("--format", choices=["md", "prompt", "json"], default="md")
    prender.set_defaults(func=cmd_render)

    sub.add_parser("generate-goal", help="print native /goal command").set_defaults(func=cmd_generate_goal)

    pc = sub.add_parser("checkpoint", help="manage checkpoints")
    pc.add_argument("--add"); pc.add_argument("--id"); pc.add_argument("--evidence")
    pc.add_argument("--met", action="store_true"); pc.set_defaults(func=cmd_checkpoint)

    pr = sub.add_parser("run", help="run a validation command and record it")
    pr.add_argument("command"); pr.set_defaults(func=cmd_run)

    pvc = sub.add_parser("validate-contract", help="validate state.json against the schema")
    pvc.add_argument("--strict", action="store_true"); pvc.add_argument("--json", action="store_true")
    pvc.set_defaults(func=cmd_validate_contract)

    pdoc = sub.add_parser("doctor", help="check contract quality & consistency")
    pdoc.add_argument("--json", action="store_true"); pdoc.set_defaults(func=cmd_doctor)

    psc = sub.add_parser("score", help="score diff + validators, show completion tier")
    psc.add_argument("--base", default=None); psc.add_argument("--json", action="store_true")
    psc.set_defaults(func=cmd_score)

    pg = sub.add_parser("gate", help="exit 0 only when the contract is complete")
    pg.add_argument("--ci", action="store_true"); pg.add_argument("--json", action="store_true")
    pg.add_argument("--rerun", action="store_true",
                    help="re-execute required command validators from a clean state (earns tier 4)")
    pg.set_defaults(func=cmd_gate)

    pcomp = sub.add_parser("complete", help="mark complete (only after gate passes)")
    pcomp.add_argument("--accepted-by", dest="accepted_by"); pcomp.set_defaults(func=cmd_complete)

    pp = sub.add_parser("proof", help="write a proof bundle")
    pp.add_argument("--format", choices=["md", "json", "both"], default="both")
    pp.set_defaults(func=cmd_proof)

    pap = sub.add_parser("approve", help="record a human approval")
    pap.add_argument("what"); pap.add_argument("--by", required=True); pap.add_argument("--note")
    pap.set_defaults(func=cmd_approve)

    sub.add_parser("contract-lock", help="freeze the contract").set_defaults(func=cmd_contract_lock)
    pul = sub.add_parser("contract-unlock", help="unlock + record amendment")
    pul.add_argument("--reason"); pul.set_defaults(func=cmd_contract_unlock)
    sub.add_parser("contract-diff", help="show pending contract changes vs lock").set_defaults(func=cmd_contract_diff)

    psp = sub.add_parser("split", help="partition scope into disjoint packets")
    psp.add_argument("--write-packets", action="store_true", dest="write_packets")
    psp.set_defaults(func=cmd_split)

    ppk = sub.add_parser("packets", help="list | run <id> | reconcile")
    ppk.add_argument("action", choices=["list", "run", "reconcile"])
    ppk.add_argument("packet_id", nargs="?"); ppk.set_defaults(func=cmd_packets)

    pa = sub.add_parser("autocontinue", help="toggle bounded Stop auto-continue")
    pa.add_argument("action", choices=["on", "off", "reset"]); pa.add_argument("--max", type=int)
    pa.set_defaults(func=cmd_autocontinue)

    pl = sub.add_parser("log", help="append a line to work_log.md")
    pl.add_argument("message"); pl.set_defaults(func=cmd_log)

    sub.add_parser("mcp", help="run the stdio MCP server (gate/run/checkpoint/complete tools)").set_defaults(func=cmd_mcp)

    pins = sub.add_parser("install", help="install Goalkeeper shell/host entrypoints")
    pins.add_argument("target", choices=["shell", "claude", "codex", "all"])
    pins.add_argument("--dry-run", action="store_true")
    pins.add_argument("--json", action="store_true")
    pins.set_defaults(func=cmd_install)

    pun = sub.add_parser("uninstall", help="remove Goalkeeper-installed entrypoints")
    pun.add_argument("target", choices=["shell", "claude", "codex", "all"])
    pun.add_argument("--dry-run", action="store_true")
    pun.add_argument("--json", action="store_true")
    pun.set_defaults(func=cmd_uninstall)

    phost = sub.add_parser("host", help="host diagnostics")
    phost.add_argument("action", choices=["doctor"])
    phost.add_argument("target", nargs="?", default="all", choices=["shell", "claude", "codex", "all"])
    phost.add_argument("--json", action="store_true")
    phost.set_defaults(func=cmd_host)

    psmoke = sub.add_parser("smoke", help="run an isolated end-to-end smoke check")
    psmoke.add_argument("target", nargs="?", default="core", choices=["core", "claude", "codex"])
    psmoke.add_argument("--json", action="store_true")
    psmoke.set_defaults(func=cmd_smoke)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
