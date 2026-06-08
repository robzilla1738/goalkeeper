"""Subagent packets: partition scope into disjoint write-sets.

Conservative by design: no two implementer packets may share an editable path.
The actual subagent launch is owned by the host; `run` emits the scoped prompt
and marks state. Concurrency on state.json remains experimental — `reconcile`
is the safety net, not a lock.
"""
from __future__ import annotations

from pathlib import Path

from .clock import now
from .gitio import changed_files
from .matching import matches_any
from .paths import PACKETS_FILE, gk_path


def build_packets(state: dict) -> list[dict]:
    """One implementer packet per allowed resource (disjoint by construction)."""
    allowed = state.get("scope", {}).get("allowed_resources", [])
    forbidden = state.get("scope", {}).get("forbidden_resources", []) + state.get("scope", {}).get("forbidden_actions", [])
    packets = []
    for i, res in enumerate(allowed, start=1):
        packets.append({
            "id": f"P{i}",
            "role": "implementer",
            "allowed_paths": [res],
            "forbidden": forbidden,
            "objective": f"Advance the goal only within {res}.",
            "status": "pending",
        })
    return packets


def disjoint(packets: list[dict]) -> tuple[bool, list[str]]:
    """Verify implementer write-sets do not overlap. Returns (ok, conflicts)."""
    seen: dict[str, str] = {}
    conflicts = []
    for p in packets:
        if p.get("role") != "implementer":
            continue
        for path in p.get("allowed_paths", []):
            for other_path, owner in seen.items():
                if path == other_path or matches_any(path.rstrip("/*"), [other_path]) or matches_any(other_path.rstrip("/*"), [path]):
                    conflicts.append(f"{p['id']} and {owner} both claim {path}/{other_path}")
            seen[path] = p["id"]
    return (not conflicts, conflicts)


def write_packets(state: dict, root: Path) -> list[dict]:
    packets = build_packets(state)
    ok, conflicts = disjoint(packets)
    state.setdefault("loop_runtime", {})["packets"] = packets
    md = ["# Agent Packets (generated)", "",
          "Each packet has a disjoint write-set so parallel agents never collide.", ""]
    for p in packets:
        md += [
            f"## Packet {p['id']} — {p['role']}",
            f"Allowed paths: {', '.join(p['allowed_paths'])}",
            f"Forbidden: {', '.join(p['forbidden']) or '(inherit contract)'}",
            f"Objective: {p['objective']}",
            "Done: validation passes; evidence appended to .goalkeeper/work_log.md",
            "",
            "--- subagent prompt ---",
            f"You are a scoped implementer. Work ONLY in {', '.join(p['allowed_paths'])}. "
            "Do not edit any other path. If you must change a file outside your allowed "
            "paths, STOP and report instead. When done, run the contract validations "
            "through `goalkeeper run`, record evidence, and stop.",
            "",
        ]
    if not ok:
        md += ["> WARNING: write-sets overlap; do NOT run these in parallel:", ""]
        md += [f"> - {c}" for c in conflicts]
    gk_path(PACKETS_FILE, root).write_text("\n".join(md) + "\n", encoding="utf-8")
    return packets


def list_packets(state: dict) -> list[dict]:
    return state.get("loop_runtime", {}).get("packets", [])


def mark_packet(state: dict, packet_id: str, status: str) -> dict | None:
    for p in list_packets(state):
        if p["id"] == packet_id:
            p["status"] = status
            p["updated_at"] = now()
            return p
    return None


def reconcile(state: dict, root: Path) -> dict:
    """Check combined diffs honored disjoint write-sets."""
    packets = list_packets(state)
    base = state.get("base_ref") or "HEAD"
    changed = changed_files(base, root)
    ownership: list[tuple[str, str]] = []  # (file, owning packet or "<unclaimed>")
    for f in changed:
        owner = "<unclaimed>"
        for p in packets:
            if p.get("role") == "implementer" and matches_any(f, p.get("allowed_paths", [])):
                owner = p["id"]
                break
        ownership.append((f, owner))
    unclaimed = [f for f, o in ownership if o == "<unclaimed>"]
    ok, conflicts = disjoint(packets)
    return {
        "ownership": ownership,
        "unclaimed": unclaimed,
        "disjoint": ok,
        "conflicts": conflicts,
    }
