"""Locally-runnable validators: command, git_diff, file_exists, file_contains."""
from __future__ import annotations

import re
from pathlib import Path

from ..ledger import latest_run
from ..matching import matches_any
from .base import EvalContext, Validator, ValidatorResult


class CommandValidator(Validator):
    type = "command"
    can_run_locally = True
    tier_on_pass = 3

    def evaluate(self, spec: dict, ctx: EvalContext) -> ValidatorResult:
        cmd = spec.get("command", "")
        if not cmd:
            return ValidatorResult(None, False, self.tier_on_pass, "no command specified")
        run = latest_run(cmd, ctx.runs)
        if run is None:
            return ValidatorResult(
                None, True, self.tier_on_pass,
                f"`{cmd}` not run yet (use `goalkeeper run`)",
            )
        exit_code = int(run.get("exit", 1))
        cond = spec.get("pass_condition", "exit_zero")
        passed = _check_exit(cond, exit_code)
        tier = 4 if spec.get("params", {}).get("independent_rerun") else self.tier_on_pass
        return ValidatorResult(
            passed, True, tier,
            f"`{cmd}` -> exit {exit_code} ({'pass' if passed else 'fail'} for {cond})",
            {"exit": exit_code},
        )


def _check_exit(cond: str, exit_code: int) -> bool:
    if cond in ("exit_zero", "exit_code == 0", ""):
        return exit_code == 0
    if cond in ("exit_nonzero", "exit_code != 0"):
        return exit_code != 0
    if cond.startswith("exit_eq:"):
        try:
            return exit_code == int(cond.split(":", 1)[1])
        except ValueError:
            return False
    return exit_code == 0


class GitDiffValidator(Validator):
    type = "git_diff"
    can_run_locally = True
    tier_on_pass = 2

    def evaluate(self, spec: dict, ctx: EvalContext) -> ValidatorResult:
        params = spec.get("params", {}) or {}
        cond = spec.get("pass_condition", "no_forbidden_paths_changed")
        changed = ctx.changed_files
        if cond == "no_forbidden_paths_changed" or cond.startswith("must_not_touch"):
            forbidden = params.get("must_not_touch", [])
            hits = [f for f in changed if matches_any(f, forbidden)]
            passed = not hits
            ev = "no forbidden paths changed" if passed else f"touched: {', '.join(hits)}"
            return ValidatorResult(passed, True, self.tier_on_pass, ev, {"hits": hits})
        if cond.startswith("paths_changed_within"):
            within = params.get("within", [])
            outside = [f for f in changed if within and not matches_any(f, within)]
            passed = not outside
            ev = "all changes within scope" if passed else f"outside: {', '.join(outside)}"
            return ValidatorResult(passed, True, self.tier_on_pass, ev, {"outside": outside})
        if cond.startswith("max_files:"):
            try:
                limit = int(cond.split(":", 1)[1])
            except ValueError:
                limit = 0
            passed = len(changed) <= limit
            return ValidatorResult(passed, True, self.tier_on_pass, f"{len(changed)} files changed (limit {limit})")
        return ValidatorResult(None, True, self.tier_on_pass, f"unknown git_diff condition: {cond}")


class FileExistsValidator(Validator):
    type = "file_exists"
    can_run_locally = True
    tier_on_pass = 2

    def evaluate(self, spec: dict, ctx: EvalContext) -> ValidatorResult:
        params = spec.get("params", {}) or {}
        rel = params.get("path", "")
        cond = spec.get("pass_condition", "exists")
        exists = (ctx.root / rel).exists() if rel else False
        passed = exists if cond == "exists" else (not exists)
        return ValidatorResult(passed, True, self.tier_on_pass, f"{rel} {'exists' if exists else 'absent'}")


class FileContainsValidator(Validator):
    type = "file_contains"
    can_run_locally = True
    tier_on_pass = 2

    def evaluate(self, spec: dict, ctx: EvalContext) -> ValidatorResult:
        params = spec.get("params", {}) or {}
        rel = params.get("path", "")
        cond = spec.get("pass_condition", "")
        target = ctx.root / rel if rel else None
        if not target or not target.exists():
            return ValidatorResult(False, True, self.tier_on_pass, f"{rel} not found")
        text = target.read_text(encoding="utf-8", errors="replace")
        if cond.startswith("contains:"):
            pat = cond.split(":", 1)[1]
            m = re.search(pat, text)
            return ValidatorResult(bool(m), True, self.tier_on_pass, f"/{pat}/ {'found' if m else 'absent'} in {rel}")
        if cond.startswith("not_contains:"):
            pat = cond.split(":", 1)[1]
            m = re.search(pat, text)
            return ValidatorResult(not m, True, self.tier_on_pass, f"/{pat}/ {'found' if m else 'absent'} in {rel}")
        if cond.startswith("count_eq:"):
            try:
                want = int(cond.split(":", 1)[1])
            except ValueError:
                return ValidatorResult(None, True, self.tier_on_pass, f"bad count_eq: {cond}")
            n = len(re.findall(params.get("pattern", ""), text))
            return ValidatorResult(n == want, True, self.tier_on_pass, f"count={n} (want {want}) in {rel}")
        return ValidatorResult(None, True, self.tier_on_pass, f"unknown file_contains condition: {cond}")
