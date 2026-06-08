#!/usr/bin/env python3
"""goalkeeper CLI — argparse wiring + command dispatch over goalkeeper_core."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import SCHEMA_VERSION, __version__
from . import contract as contract_mod
from . import detect as detect_mod
from . import gate as gate_mod
from . import packets as packets_mod
from . import proof as proof_mod
from . import render as render_mod
from . import risk as risk_mod
from . import schema as schema_mod
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
        if args.template:
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
    print("Next: `goalkeeper set ...`, `goalkeeper doctor`, then `goalkeeper render --format prompt`.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state = _need_state()
    goal = state.get("goal", {})
    cps = state.get("checkpoints", [])
    met = sum(1 for c in cps if c.get("status") == "met")
    risk = state.get("risk", {})
    loop = state.get("loop", {})
    print(f"status      : {state.get('completion', {}).get('status', '?')}")
    print(f"objective   : {goal.get('objective') or '(unset)'}")
    print(f"domain      : {goal.get('domain', 'code')}  priority: {goal.get('priority', '?')}")
    print(f"checkpoints : {met}/{len(cps)} met")
    print(f"validators  : {len(state.get('validators', []))}")
    print(f"allowed     : {', '.join(state.get('scope', {}).get('allowed_resources', [])) or '(none)'}")
    print(f"forbidden   : {', '.join(state.get('scope', {}).get('forbidden_resources', [])) or '(none)'}")
    print(f"risk        : {risk.get('level', '?')}  external_side_effects: {risk.get('external_side_effects', False)}")
    print(f"loop        : {loop.get('mode')}  max_turns: {loop.get('max_turns')}")
    print(f"locked      : {contract_mod.is_locked(state)}")
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
    checks: list[tuple[str, bool, str]] = []
    errors = schema_mod.validate(state, strict=True)
    checks.append(("contract validates (strict)", not errors, "" if not errors else f"{len(errors)} error(s)"))
    obj = (get_path(state, "goal.objective") or "").strip()
    checks.append(("objective set", bool(obj), obj[:60]))
    vague = ("better", "improve", "clean up", "etc", "and so on", "as needed")
    bounded = bool(obj) and not any(v in obj.lower() for v in vague)
    checks.append(("objective is bounded", bounded, "" if bounded else "contains vague language"))
    vals = state.get("validators", [])
    checks.append(("validators present", bool(vals), f"{len(vals)}"))
    req = any(v.get("required") for v in vals)
    checks.append(("at least one required validator", req, ""))
    bounds = bool(get_path(state, "scope.allowed_resources")) or bool(get_path(state, "scope.forbidden_resources"))
    checks.append(("scope boundaries present", bounds, ""))
    checks.append(("at least one checkpoint", bool(state.get("checkpoints")), ""))
    checks.append(("diff baseline captured", bool(state.get("base_ref")), (state.get("base_ref") or "")[:12]))

    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    pct = round(100 * passed / total)
    if args.json:
        print(json.dumps({"contract_quality": pct, "passed": passed, "total": total,
                          "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks],
                          "schema_errors": errors}, indent=2))
    else:
        print(f"contract quality: {pct}% ({passed}/{total} checks)\n")
        for name, ok, detail in checks:
            line = f"  [{'PASS' if ok else 'FAIL'}] {name}"
            if detail:
                line += f"  ({detail})"
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


def cmd_gate(args: argparse.Namespace) -> int:
    state = _need_state()
    g = gate_mod.evaluate_gate(state, find_root())
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
    from .clock import now
    state["completion"]["status"] = "complete"
    state["completion"]["accepted_by"] = args.accepted_by
    state["completion"]["completed_at"] = now()
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
    if args.max is not None:
        rt["max_autocontinue_turns"] = args.max
        set_path(state, "loop.max_turns", args.max)
    if args.action == "reset":
        rt["autocontinue_turns_used"] = 0
    save_state(state)
    print(f"autocontinue {'on' if rt['autocontinue'] else 'off'}; "
          f"budget {rt.get('max_autocontinue_turns')} turns, {rt.get('autocontinue_turns_used', 0)} used")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    ledger_log(args.message)
    print("logged.")
    return 0


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
    pi.add_argument("--force", action="store_true")
    pi.set_defaults(func=cmd_init)

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
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
