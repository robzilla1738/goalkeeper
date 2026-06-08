# Playbook: code refactor

Goal: replace a legacy implementation while preserving public behavior.

```bash
goalkeeper init --template code-refactor -o "Replace legacy JWT verification with the new token API while preserving public behavior"
goalkeeper set scope.allowed_resources "src/auth/**,tests/auth/**"
goalkeeper set scope.forbidden_resources ".github/**,package-lock.json"
goalkeeper detect --apply            # writes command validators from package.json
goalkeeper doctor                    # gate the contract before any work
goalkeeper set completion.status active
goalkeeper render --format prompt    # -> paste into /goal

# …agent works; validations recorded as they run…
goalkeeper run "npm test -- tests/auth"
goalkeeper run "npm run typecheck"
goalkeeper checkpoint --id cp1 --evidence "rg jwt.decode src/routes/auth -> no matches" --met

goalkeeper gate                      # exit 0 only when complete; shows tier
goalkeeper complete --accepted-by robert
goalkeeper proof                     # shareable audit bundle
```

Completion tier for pure code work tops out at **3–4** (deterministic / independent
re-run). Add a `human_approval` validator if the change is high-risk and needs a
named reviewer (tier 5).
