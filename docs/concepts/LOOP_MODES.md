# Loop modes

`loop.mode` tells the Stop hook how to drive continuation after a host turn. The
hook reuses the completion **gate**, so it never pushes past a passing gate.

Enforcement is on by default for gated work (templates and `init --auto`/`adopt`
set `loop.enforce: true`). Re-bound or disable it:

```bash
goalkeeper autocontinue on --max 5    # raise the per-contract turn budget
goalkeeper autocontinue off           # kill switch (or GOALKEEPER_NO_STOP=1)
```

| Mode | Continue while incomplete | Done (stop) | Pause |
|------|---------------------------|-------------|-------|
| `goal_until_pass` | budget left | gate passes | needs creds/human; required validator unavailable; budget out |
| `repair_until_pass` | re-target failing validators | failing validators now pass + gate | non-code failure (missing dep) |
| `research_until_covered` | until coverage checkpoints met | all checkpoints met with sources | source unavailable; needs judgement |
| `watch_until_event` | until the watched signal fires | `stop_when` event observed | event source down; time/budget out |
| `scheduled_recurring` | does **not** auto-continue in-session | one cycle's gate passes | always pauses after a cycle; re-armed by the host scheduler |
| `human_review_loop` | produce review-ready output, then pause | a `human_approval`/`rubric` validator passes (tier 5) | awaiting human approval |
| `multi_agent_packet_loop` | until packets reconcile | `packets reconcile` clean + combined gate | write-set conflict or human input |

## Budgets

`loop.max_turns`, `loop.max_wall_time_minutes`, and `loop.max_cost_usd` bound the
loop. The turn budget is always enforced (tracked in `loop_runtime.autocontinue_turns_used`);
wall time and cost are enforced only where the host exposes elapsed/cost signals.

## Cross-host scheduling

For `scheduled_recurring` and long `watch_until_event`, the hook **pauses** rather
than busy-looping. Re-invocation is owned by the host — Codex automations, a cron
job running `goalkeeper gate --ci`, or the [GitHub gate workflow](../../hosts/github-actions/goalkeeper-gate.yml).
Goalkeeper integrates with host continuation instead of reinventing scheduling.

See [`/goal` and continuation](./GOAL_AND_LOOP.md) for the practical host
integration model and the limits of `/loop`-style behavior.
