# Playbook: recurring maintenance

Goal: weekly dependency-advisory check that files a report on failure and never
auto-upgrades without approval.

```bash
goalkeeper init --template recurring-maintenance -o "Check weekly whether dependencies have high-severity advisories"
goalkeeper doctor
```

The template uses `loop.mode = scheduled_recurring`, so the Stop hook does **not**
busy-loop — it runs one cycle and pauses. Re-invocation is owned by the host:

- **Codex automations** on a weekly cadence, or
- a cron job / the [GitHub gate workflow](../../hosts/github-actions/goalkeeper-gate.yml)
  running `goalkeeper gate --ci`.

Run each cycle in an isolated worktree. On a failing audit, the agent files a report
and (because `risk.approval_required_before` includes `upgrade dependencies`) cannot
complete an upgrade without:

```bash
goalkeeper approve "upgrade dependencies" --by robert --note "reviewed advisory GHSA-xxxx"
```
