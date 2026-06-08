"""Unit tests for pure-logic core modules."""
from __future__ import annotations

import json

from goalkeeper_core import autocontract, contract, gate, install, loop, quality, render, schema, state, tiers
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


def test_quality_allows_scoped_improve_objective():
    c = contract.default_contract("Improve checkout retry handling in src/payments")
    checks = {check.name: check.ok for check in quality.contract_quality_checks(c)}
    assert checks["objective is bounded"] is True


def test_quality_rejects_low_information_objectives():
    for objective in ("Improve code", "Clean up auth", "Fix stuff in src/auth"):
        c = contract.default_contract(objective)
        checks = {check.name: check.ok for check in quality.contract_quality_checks(c)}
        assert checks["objective is bounded"] is False


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


def test_auto_contract_uses_node_package_manager(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts":{"test":"vitest","lint":"eslint ."}}')
    (tmp_path / "pnpm-lock.yaml").write_text("")
    (tmp_path / "src").mkdir()
    c = autocontract.build_auto_contract("Ship feature", tmp_path)
    assert c["completion"]["status"] == "active"
    assert [v["command"] for v in c["validators"]] == ["pnpm test", "pnpm lint"]
    assert "src/**" in c["scope"]["allowed_resources"]


def test_install_target_paths_honor_env(tmp_path, monkeypatch):
    monkeypatch.setenv("GOALKEEPER_INSTALL_BIN_DIR", str(tmp_path / "bin"))
    paths = install.target_paths("shell")
    assert paths["dest"] == tmp_path / "bin" / "goalkeeper"


def test_uninstall_refuses_source_path_env(monkeypatch):
    source = install.repo_root() / "bin" / "goalkeeper"
    monkeypatch.setenv("GOALKEEPER_INSTALL_BIN_DIR", str(source.parent))
    result = install.uninstall("shell")
    assert result["ok"] is False
    assert "refusing to remove non-Goalkeeper path" in result["errors"][0]
    assert source.exists()


def test_auto_contract_falls_back_to_diff_check(tmp_path):
    c = autocontract.build_auto_contract("Ship feature", tmp_path)
    assert [v["command"] for v in c["validators"]] == ["git diff --check"]


def test_auto_contract_does_not_invent_missing_npm_test(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts":{}}')
    c = autocontract.build_auto_contract("Ship feature", tmp_path)
    assert [v["command"] for v in c["validators"]] == ["git diff --check"]


def test_stop_continues_for_unrun_local_validator(tmp_path):
    c = contract.default_contract("Ship feature", root=tmp_path)
    c["base_ref"] = "HEAD"
    c["completion"]["status"] = "active"
    c["scope"]["allowed_resources"] = ["**"]
    c["validators"] = [
        {"id": "v", "type": "command", "command": "true", "pass_condition": "exit_zero", "required": True}
    ]
    c["checkpoints"] = [
        {"id": "cp1", "description": "Validated", "evidence_required": "run output",
         "status": "pending", "evidence": ""}
    ]
    decision = loop.decide_stop(c, tmp_path)
    assert decision.action == "continue"


def test_gate_can_pass_with_empty_base_ref(tmp_path):
    (tmp_path / ".goalkeeper").mkdir()
    (tmp_path / ".goalkeeper" / "runs.jsonl").write_text(json.dumps({"cmd": "true", "exit": 0}) + "\n")
    c = contract.default_contract("Ship feature", root=tmp_path)
    c["base_ref"] = ""
    c["completion"]["status"] = "active"
    c["scope"]["allowed_resources"] = ["**"]
    c["validators"] = [
        {"id": "v", "type": "command", "command": "true", "pass_condition": "exit_zero", "required": True}
    ]
    c["checkpoints"] = [
        {"id": "cp1", "description": "Validated", "evidence_required": "run output",
         "status": "met", "evidence": "true -> exit 0"}
    ]
    assert gate.evaluate_gate(c, tmp_path)["verdict"] == "COMPLETE"


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


def test_command_validator_matches_exact_by_default(tmp_path):
    ctx = EvalContext(root=tmp_path, base_ref="HEAD",
                      runs=[{"cmd": "npm test", "exit": 0}], approvals=[], changed_files=[])
    spec = {
        "id": "v",
        "type": "command",
        "command": "npm test -- tests/auth",
        "pass_condition": "exit_zero",
        "required": True,
    }
    r = evaluate(spec, ctx)
    assert r.passed is None
    assert "not run yet" in r.evidence


def test_command_validator_prefix_match_requires_opt_in(tmp_path):
    ctx = EvalContext(root=tmp_path, base_ref="HEAD",
                      runs=[{"cmd": "npm test", "exit": 0}], approvals=[], changed_files=[])
    spec = {
        "id": "v",
        "type": "command",
        "command": "npm test -- tests/auth",
        "params": {"allow_prefix_match": True},
        "pass_condition": "exit_zero",
        "required": True,
    }
    r = evaluate(spec, ctx)
    assert r.passed is True


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
