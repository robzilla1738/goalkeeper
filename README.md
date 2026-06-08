# goalkeeper

**Goalkeeper Loop** — a cross-compatible Claude Code + Codex plugin that adds a
**Goal Contract → verifier → ledger → subagent packet** layer on top of the
first-party `/goal`, `/loop`, hooks, skills, and subagents.

As of today, the agentic-coding landscape is mature enough that you should *not*
build a raw infinite-loop wrapper. Both Codex and Claude Code already have
first-party continuation primitives. The winning layer is a contract system that
makes long-running work **measurable, bounded, and auditable** — *contract,
don't vibe.*

The plugin lives in [`goalkeeper-loop/`](./goalkeeper-loop). See
[`goalkeeper-loop/README.md`](./goalkeeper-loop/README.md) for full docs.

## Quick start

**Claude Code (local):**

```
claude --plugin-dir ./goalkeeper-loop
/goalkeeper Refactor the auth module to the new token API while preserving behavior and passing tests.
```

**Codex (local marketplace):**

```
mkdir -p ./plugins .agents/plugins
cp -R goalkeeper-loop ./plugins/goalkeeper-loop
cp goalkeeper-loop/examples/marketplace.json .agents/plugins/marketplace.json
# restart Codex, install from the local marketplace
codex features enable goals
$goalkeeper Refactor the auth module to the new token API while preserving behavior and passing tests.
```

## The flow

```
/goalkeeper -> create Goal Contract -> generate native /goal
            -> run checkpoints -> goalkeeper-audit -> complete or pause
```

It writes project-local state under `.goalkeeper/` (`goal.md`, `state.json`,
`work_log.md`, `agent_packets.md`, `events.jsonl`).

## What's inside

- **3 skills** — `goalkeeper` (author a contract + generate `/goal`),
  `goalkeeper-split` (safe subagent packets), `goalkeeper-audit` (verify the
  diff against the contract).
- **Conservative hooks** — context injection, destructive-command blocking,
  forbidden-path enforcement, event logging; optional bounded auto-continue
  (off by default — native `/goal` is preferred).
- **A dependency-free `goalkeeper` CLI** — init/status/detect/generate-goal/
  score/checkpoint/log.
- **Agents** — Claude Code plugin agents (`agents/`) and Codex custom-agent TOML
  examples (`codex-agents/`): researcher (read-only), implementer (scoped),
  verifier (read-only).

## License

MIT © Robert Courson — see [LICENSE](./LICENSE).
