# Writing an adapter

An adapter makes the contract real for a domain. It is a ~40-line module selected
by `goal.domain`. Core stays domain-neutral; adapters provide defaults and
presentation.

## Interface (`goalkeeper_core/adapters/base.py`)

```python
class Adapter:
    domain: str
    def default_template(self) -> dict: ...          # partial v2 contract overlay
    def supported_validator_types(self) -> list[str]: ...
    def render_prompt_extras(self, contract) -> str: ...   # clauses appended to /goal
    def verify_extras(self, contract, results) -> list[tuple[str, str]]: ...  # extra gate blockers
    def default_risk(self) -> dict: ...
```

Register it in `goalkeeper_core/adapters/__init__.py`:

```python
ADAPTERS = {a.domain: a for a in (CodeAdapter(), ResearchAdapter(), WritingAdapter(), OpsAdapter(), MyAdapter())}
```

`get_adapter(domain)` falls back to `code` for unknown domains, preserving default
behavior.

## Shipped adapters

| domain | validators it favors | loop default | risk default |
|--------|----------------------|--------------|--------------|
| `code` | command, git_diff, file_contains, github_check | goal_until_pass | low |
| `research` | file_exists, file_contains, rubric, human_approval | research_until_covered | low |
| `writing` | file_exists, file_contains, rubric, human_approval | human_review_loop | low |
| `ops` | command, http_check, ticket_state, human_approval | watch_until_event | high, external side effects |

`verify_extras` lets a domain add gate blockers — e.g. `research` blocks completion
if a met checkpoint lacks a cited source.
