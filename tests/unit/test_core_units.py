"""Unit tests for pure-logic core modules."""
from __future__ import annotations

from goalkeeper_core import contract, render, schema, state, tiers
from goalkeeper_core.adapters import get_adapter, known_domains
from goalkeeper_core.matching import matches_any
from goalkeeper_core.validators import EvalContext, evaluate, known_types


def test_matches_any():
    assert matches_any("src/auth/x.py", ["src/auth/**"])
    assert matches_any("a.lock", ["*.lock"])
    assert not matches_any("src/routes/x.py", ["src/auth/**"])


def test_dotted_path_set_get():
    s = {}
    state.set_path(s, "goal.objective", "do thing")
    assert state.get_path(s, "goal.objective") == "do thing"
    assert state.get_path(s, "goal.missing") is None


def test_coerce_types():
    assert state.coerce("scope.allowed_resources", "a, b ,c") == ["a", "b", "c"]
    assert state.coerce("loop.max_turns", "9") == 9
    assert state.coerce("loop.max_cost_usd", "2.5") == 2.5
    assert state.coerce("risk.external_side_effects", "true") is True
    assert state.coerce("goal.title", "Hi") == "Hi"


def test_default_contract_is_schema_valid():
    c = contract.default_contract("Refactor auth", domain="code")
    assert schema.validate(c) == []


def test_strict_requires_required_validator():
    c = contract.default_contract("x")
    errs = schema.validate(c, strict=True)
    assert any("required:true" in e for e in errs)


def test_schema_rejects_bad_enum():
    c = contract.default_contract("x")
    c["risk"]["level"] = "nope"
    errs = schema.validate(c)
    assert any("risk.level" in e for e in errs)


def test_known_registries_match_schema():
    assert "command" in known_types()
    assert set(known_domains()) == {"code", "research", "writing", "ops"}


def test_adapter_fallback_is_code():
    assert get_adapter("nonexistent").domain == "code"
    assert get_adapter("ops").domain == "ops"


def test_render_prompt_contains_objective_and_done():
    c = contract.default_contract("Refactor auth")
    c["scope"]["allowed_resources"] = ["src/auth/**"]
    c["validators"] = [{"id": "t", "type": "command", "command": "npm test", "pass_condition": "exit_zero", "required": True}]
    prompt = render.build_goal_prompt(c)
    assert "Refactor auth" in prompt
    assert "npm test exits 0" in prompt
    assert "src/auth/**" in prompt


def test_lock_unlock_amendment_history():
    c = contract.default_contract("x")
    contract.lock(c)
    assert contract.is_locked(c)
    contract.unlock(c, reason="scope expanded after approval")
    assert not contract.is_locked(c)
    assert c["amendments"][-1]["reason"] == "scope expanded after approval"


def _ctx(tmp_path):
    return EvalContext(root=tmp_path, base_ref="HEAD", runs=[], approvals=[], changed_files=[])


def test_command_validator_not_run_is_inconclusive(tmp_path):
    spec = {"id": "v", "type": "command", "command": "echo hi", "pass_condition": "exit_zero", "required": True}
    r = evaluate(spec, _ctx(tmp_path))
    assert r.passed is None and r.available is True


def test_command_validator_passes_from_ledger(tmp_path):
    ctx = EvalContext(root=tmp_path, base_ref="HEAD",
                      runs=[{"cmd": "echo hi", "exit": 0}], approvals=[], changed_files=[])
    spec = {"id": "v", "type": "command", "command": "echo hi", "pass_condition": "exit_zero", "required": True}
    r = evaluate(spec, ctx)
    assert r.passed is True and r.tier == 3


def test_deferred_validators_unavailable(tmp_path):
    for t in ("github_check", "ticket_state", "sql_query"):
        spec = {"id": t, "type": t, "params": {}, "pass_condition": "x", "required": True}
        r = evaluate(spec, _ctx(tmp_path))
        assert r.available is False and r.passed is None


def test_human_approval_validator(tmp_path):
    ctx = EvalContext(root=tmp_path, base_ref="HEAD", runs=[],
                      approvals=[{"what": "v", "by": "rob"}], changed_files=[])
    spec = {"id": "v", "type": "human_approval", "pass_condition": "approved:v", "required": True}
    r = evaluate(spec, ctx)
    assert r.passed is True and r.tier == 5


def test_tier_tops_out_without_human():
    c = contract.default_contract("x")
    c["validators"] = [{"id": "v", "type": "command", "command": "true", "pass_condition": "exit_zero", "required": True}]
    results = [(c["validators"][0], evaluate(c["validators"][0],
               EvalContext(root=None, base_ref="HEAD", runs=[{"cmd": "true", "exit": 0}], approvals=[], changed_files=[])))]
    # checkpoints empty + scope clean + ledger -> needs ledger_nonempty(root) which is False here,
    # so this is a structural sanity check that compute_tier runs without error.
    t = tiers.compute_tier(c, results, [], root=None)
    assert 0 <= t <= 4
