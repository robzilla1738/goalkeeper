"""Validators that cannot run in a hermetic, dependency-free environment.

These degrade to `available=False, passed=None` so the gate treats them as a
`validator_unavailable` pause rather than a false pass. Evidence can be supplied
manually (via `goalkeeper run`/`log`/`approve`). http_check is the one type that
*can* use stdlib urllib, gated behind GOALKEEPER_ALLOW_NET=1 to keep CI hermetic.
"""
from __future__ import annotations

import os
import urllib.request

from .base import EvalContext, Validator, ValidatorResult


class HttpCheckValidator(Validator):
    type = "http_check"
    can_run_locally = False  # opt-in only
    tier_on_pass = 4

    def evaluate(self, spec: dict, ctx: EvalContext) -> ValidatorResult:
        if os.environ.get("GOALKEEPER_ALLOW_NET") != "1":
            return self._deferred("http_check disabled (set GOALKEEPER_ALLOW_NET=1 to enable)")
        params = spec.get("params", {}) or {}
        url = params.get("url")
        if not url:
            return ValidatorResult(None, False, self.tier_on_pass, "no url specified")
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
                status = resp.getcode()
                body = resp.read(4096).decode("utf-8", errors="replace")
        except Exception as exc:  # network errors -> unavailable, not a fail
            return self._deferred(f"http_check could not reach {url}: {exc}")
        cond = spec.get("pass_condition", "status_match")
        if cond == "status_match":
            want = params.get("expect_status", 200)
            return ValidatorResult(status == want, True, self.tier_on_pass, f"{url} -> {status} (want {want})")
        if cond == "body_contains":
            needle = params.get("contains", "")
            return ValidatorResult(needle in body, True, self.tier_on_pass, f"{url} body {'contains' if needle in body else 'missing'} {needle!r}")
        return ValidatorResult(None, True, self.tier_on_pass, f"unknown http condition: {cond}")


class _ManualValidator(Validator):
    """External-reality validators with no local driver: always deferred/manual."""

    can_run_locally = False

    def evaluate(self, spec: dict, ctx: EvalContext) -> ValidatorResult:
        return self._deferred(
            f"{self.type} requires an external system; supply evidence manually "
            f"(e.g. `goalkeeper approve {spec.get('id', self.type)} --by <name>`)"
        )


class GithubCheckValidator(_ManualValidator):
    type = "github_check"
    tier_on_pass = 6


class TicketStateValidator(_ManualValidator):
    type = "ticket_state"
    tier_on_pass = 6


class SqlQueryValidator(_ManualValidator):
    type = "sql_query"
    tier_on_pass = 4
