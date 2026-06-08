# Goalkeeper — GitHub Actions host

Bring the completion gate to where teams already work: PRs and CI.

## Composite action

```yaml
- name: Goalkeeper gate
  uses: robzilla1738/goalkeeper/hosts/github-actions@main
  with:
    working-directory: .
```

The action runs `goalkeeper gate --ci`, writes a verdict + completion tier to the
job summary, and exits non-zero unless the contract is `COMPLETE`.

## Reusable workflow

[`goalkeeper-gate.yml`](./goalkeeper-gate.yml) runs the gate on every pull request
and posts a sticky verdict comment, e.g.:

> ### Goalkeeper verdict: **INCOMPLETE**
>
> Completion tier: **3/6**
>
> **Needs review:**
> - **checkpoint_no_evidence**: cp3
> - **scope_drift**: src/routes/public.ts

Copy it into a consuming repo's `.github/workflows/` (the repo must contain a
`.goalkeeper/` contract and have `bin/goalkeeper` available — vendored, installed,
or via `GOALKEEPER_CORE_HOME`).
