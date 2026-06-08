# Contract schema v2 reference

The published JSON Schema is [`schema/goalkeeper.contract.schema.json`](../../schema/goalkeeper.contract.schema.json)
(Draft 2020-12). Goalkeeper enforces it in-process with a dependency-free
structural validator: `goalkeeper validate-contract [--strict]`.

## Validator registry

Each validator is `{id, type, command|params, pass_condition, required}`.

| type | runs locally? | tier on pass | `pass_condition` |
|------|---------------|-------------|------------------|
| `command` | yes | 3 (4 if `params.independent_rerun`) | `exit_zero` · `exit_nonzero` · `exit_eq:N` |
| `git_diff` | yes | 2 | `no_forbidden_paths_changed` · `paths_changed_within` · `max_files:N` |
| `file_exists` | yes | 2 | `exists` · `absent` |
| `file_contains` | yes | 2 | `contains:REGEX` · `not_contains:REGEX` · `count_eq:N` |
| `http_check` | opt-in (`GOALKEEPER_ALLOW_NET=1`) | 4 | `status_match` · `body_contains` |
| `github_check` | deferred/manual | 6 | `pr_merged` · `checks_green` · `review_approved` |
| `ticket_state` | deferred/manual | 6 | `state_eq:done` |
| `sql_query` | deferred/manual | 4 | `rowcount_eq:N` · `scalar_eq:V` |
| `rubric` | records a judgment | 5 | `score_gte:N` |
| `human_approval` | checks `approvals[]` | 5 | `approved:WHAT` |

**Deferred** validators (`github_check`, `ticket_state`, `sql_query`, and
`http_check` when net is disabled) return *unavailable* rather than importing a
third-party driver. A required-but-unavailable validator is a `validator_unavailable`
**pause**, not a false pass — supply its evidence manually (`goalkeeper run` /
`goalkeeper approve`).

## Strict cross-field rules (`--strict`)

Enforced in addition to the structural schema:

- at least one validator is `required: true`;
- `high`/`critical` risk requires a `human_approval`/`rubric` validator **or** a
  non-empty `risk.approval_required_before`;
- every `risk.approval_required_before` action appears in `scope.allowed_actions`
  (when that list is non-empty);
- validator and checkpoint ids are unique;
- `loop.mode == watch_until_event` requires at least one `loop.pause_when` event.

## Runtime fields

Alongside the contract, `state.json` carries non-contract bookkeeping:
`base_ref`, `host`, `created_at`/`updated_at`, `loop_runtime`, `lock`,
`approvals`, `amendments`. These are permitted by the schema
(`additionalProperties: true`) and are not part of contract hashing/locking.
