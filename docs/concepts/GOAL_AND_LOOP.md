# `/goal` and continuation

Goalkeeper is designed to sit **above** native host continuation, not replace it.
The reliable workflow is:

1. Goalkeeper writes a local contract.
2. Goalkeeper renders a native `/goal` prompt.
3. Claude Code or Codex runs the work.
4. Goalkeeper records validation evidence.
5. `goalkeeper gate` decides whether the work is complete.

## `/goal` is the primary path

Use `render --format prompt` to generate the host prompt:

```bash
goalkeeper init --auto -o "Implement billing retry handling with tests"
goalkeeper render --format prompt
```

Paste or run that output as the host's `/goal`. The prompt includes the
objective, allowed/forbidden scope, required validators, checkpoints, risk rules,
and proof requirements. During the run, validators should be executed through
Goalkeeper:

```bash
goalkeeper run "pytest -q"
goalkeeper checkpoint --id cp1 --evidence "pytest passed and diff stayed in scope" --met
goalkeeper gate
```

The model can keep coding normally, but completion is not accepted until the
gate passes and `goalkeeper complete` writes the final status.

## `/loop` is not the dependency

Goalkeeper does not require a separate `/loop` command. Host-level loops and
continuation features can be useful, but Goalkeeper's contract and gate are the
source of truth.

The optional Stop-hook continuation is controlled by:

```bash
goalkeeper autocontinue on --max 5
```

When enabled, the Stop hook runs the gate:

- if the gate passes, it stops;
- if local, agent-solvable blockers remain and turn budget remains, it asks the
  host to continue;
- if human approval, credentials, unavailable validators, or budget exhaustion
  are involved, it pauses.

Auto-continue is **off by default** because native `/goal` is the cleaner first
path. Treat Stop-hook continuation as a bounded assist, not as a promise that
every host `/loop` implementation will behave identically.

## What is seamless today

- `goalkeeper render --format prompt` creates a native `/goal` handoff.
- Hook context injection keeps the active contract visible to the host.
- Bash/shell hooks block obvious destructive commands and forbidden resources.
- `goalkeeper run`, `gate`, `complete`, and `proof` are host-independent.
- `goalkeeper smoke core` and `goalkeeper smoke codex` verify the local proof
  flow and Codex hook-denial path.

## What still needs live-session proof

- Long multi-turn Claude Code/Codex sessions using plugin skills plus Stop-hook
  continuation.
- Host-specific `/loop` behavior. Goalkeeper can cooperate with continuation,
  but it should not be documented as a universal `/loop` wrapper.
