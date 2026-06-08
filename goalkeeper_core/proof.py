"""Proof bundle: a shareable audit artifact (proof.md / proof.json / artifacts/)."""
from __future__ import annotations

import json
from pathlib import Path

from .evaluation import forbidden_hits, scope_drift
from .gate import evaluate_gate
from .paths import ARTIFACTS_DIR, PROOF_JSON, PROOF_MD, gk_path


def build_bundle(state: dict, root: Path) -> dict:
    g = evaluate_gate(state, root)
    goal = state.get("goal", {})
    validations = []
    for v, r in g["results"]:
        validations.append(
            {
                "id": v.get("id"),
                "type": v.get("type"),
                "required": v.get("required", False),
                "passed": r.passed,
                "available": r.available,
                "tier": r.tier,
                "evidence": r.evidence,
            }
        )
    return {
        "objective": goal.get("objective"),
        "title": goal.get("title"),
        "domain": goal.get("domain"),
        "scope": state.get("scope", {}),
        "changed_files": g["changed"],
        "validations": validations,
        "checkpoints": [
            {"id": c.get("id"), "description": c.get("description"),
             "status": c.get("status"), "evidence": c.get("evidence", "")}
            for c in state.get("checkpoints", [])
        ],
        "out_of_scope_drift": scope_drift(state, g["changed"]),
        "forbidden_changes": forbidden_hits(state, g["changed"]),
        "human_approvals": state.get("approvals", []),
        "blockers": [{"code": c, "detail": d} for c, d in g["blockers"]],
        "completion_tier": g["tier"],
        "verdict": g["verdict"],
        "completion": state.get("completion", {}),
    }


def write_bundle(state: dict, root: Path, fmt: str = "both") -> dict:
    bundle = build_bundle(state, root)
    gk_path("", root).mkdir(parents=True, exist_ok=True)
    (gk_path(ARTIFACTS_DIR, root)).mkdir(parents=True, exist_ok=True)
    if fmt in ("json", "both"):
        gk_path(PROOF_JSON, root).write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    if fmt in ("md", "both"):
        gk_path(PROOF_MD, root).write_text(render_md(bundle), encoding="utf-8")
    return bundle


def render_md(b: dict) -> str:
    lines = [
        "# Goalkeeper Proof Bundle",
        "",
        f"**Verdict:** {b['verdict']}  ·  **Completion tier:** {b['completion_tier']}/6",
        "",
        "## Objective",
        b.get("objective") or "(unset)",
        "",
        "## Scope",
        "- allowed: " + ", ".join(b["scope"].get("allowed_resources", [])) or "- allowed: (none)",
        "- forbidden: " + ", ".join(b["scope"].get("forbidden_resources", [])) or "- forbidden: (none)",
        "",
        "## Changed files",
    ]
    lines += [f"- {f}" for f in b["changed_files"]] or ["- (none)"]
    lines += ["", "## Validations"]
    for v in b["validations"]:
        mark = {True: "PASS", False: "FAIL", None: "N/A"}[v["passed"]]
        req = "required" if v["required"] else "optional"
        lines.append(f"- [{mark}] {v['id']} ({v['type']}, {req}): {v['evidence']}")
    lines += ["", "## Checkpoints"]
    for c in b["checkpoints"]:
        lines.append(f"- [{c['status']}] {c['id']}: {c['description']} — evidence: {c['evidence'] or '(none)'}")
    if b["out_of_scope_drift"]:
        lines += ["", "## Out-of-scope drift"] + [f"- {f}" for f in b["out_of_scope_drift"]]
    if b["forbidden_changes"]:
        lines += ["", "## FORBIDDEN changes"] + [f"- {f}" for f in b["forbidden_changes"]]
    if b["human_approvals"]:
        lines += ["", "## Human approvals"]
        lines += [f"- {a.get('what')} by {a.get('by')} at {a.get('at')}" for a in b["human_approvals"]]
    if b["blockers"]:
        lines += ["", "## Open blockers"] + [f"- {x['code']}: {x['detail']}" for x in b["blockers"]]
    lines.append("")
    return "\n".join(lines)
