# The Universal Goal Contract (v2)

A Goal Contract is a bounded, machine-checkable definition of *what done means*
before any agent runs. `state.json` is the canonical contract; `goal.md` is a
generated, human-readable view of it (run `goalkeeper render`).

## Sections

| Section | Question it answers |
|---------|---------------------|
| `goal` | What outcome? (`id`, `title`, `objective`, `owner`, `domain`, `priority`) |
| `scope` | What may/​may-not change? (`allowed_resources`, `forbidden_resources`, `allowed_actions`, `forbidden_actions`) |
| `validators` | How is "done" proven? (typed checks — see [validator registry](../schemas/CONTRACT_V2.md)) |
| `checkpoints` | What measurable milestones, each with evidence? |
| `loop` | How long / when to pause? (`mode`, budgets, `stop_when`, `pause_when`) |
| `risk` | How dangerous? (`level`, `external_side_effects`, `approval_required_before`) |
| `evidence` | Where is proof recorded? (ledger/runs/events/artifacts paths) |
| `completion` | Accepted yet? (`status`, `accepted_by`, `completed_at`) |

`completion.status` ∈ `draft | active | paused | complete | abandoned` and gates the
hook (context is injected and auto-continue runs only while `active`/`draft`).
`completion.status=complete` can be written **only** by `goalkeeper complete`,
which requires a passing `gate`.

## Example

```jsonc
{
  "schema_version": 2,
  "goal": {
    "id": "g-20260608-auth", "title": "Auth token migration",
    "objective": "Replace legacy JWT verification with the new token API while preserving public behavior.",
    "owner": "robert", "domain": "code", "priority": "high"
  },
  "scope": {
    "allowed_resources": ["src/auth/**", "tests/auth/**"],
    "forbidden_resources": [".github/**", "package-lock.json"],
    "allowed_actions": ["edit source files", "add or update tests"],
    "forbidden_actions": ["change public API behavior", "add production dependencies"]
  },
  "validators": [
    {"id": "unit_tests", "type": "command", "command": "npm test -- tests/auth", "pass_condition": "exit_zero", "required": true},
    {"id": "no_legacy",  "type": "file_contains", "params": {"path": "src/routes/auth.ts"}, "pass_condition": "not_contains:jwt\\.decode", "required": true},
    {"id": "scope",      "type": "git_diff", "params": {"must_not_touch": [".github/**"]}, "pass_condition": "no_forbidden_paths_changed", "required": true}
  ],
  "checkpoints": [
    {"id": "cp1", "description": "Auth routes use the new token API.", "evidence_required": "command output", "status": "pending"}
  ],
  "loop":  {"mode": "goal_until_pass", "max_turns": 12, "max_wall_time_minutes": 60, "max_cost_usd": 5,
            "stop_when": ["all_required_validators_pass", "all_checkpoints_met"],
            "pause_when": ["needs_credentials", "needs_human_input", "validator_unavailable", "approval_required"]},
  "risk":  {"level": "medium", "data_sensitivity": "normal", "external_side_effects": false, "approval_required_before": []},
  "completion": {"status": "active", "accepted_by": null, "completed_at": null}
}
```

## A good contract

- has a **bounded** objective (no "make it better", no "etc.");
- has at least one **required** validator and a scope boundary;
- declares **risk** honestly (high/critical and external-side-effect work needs
  human approval before completion);
- picks a **loop mode** that matches the work (see [LOOP_MODES](./LOOP_MODES.md)).

Run `goalkeeper doctor` to check these before handing off to `/goal`.
