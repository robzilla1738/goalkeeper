# Verifier tiers (0–6)

Not every goal is equally provable. Goalkeeper grades completion on a ladder so a
"done" claim is never falsely confident. `score`, `gate`, and `proof` always print
`Completion tier: N/6`.

| Tier | Name | Example | Strength |
|------|------|---------|----------|
| 0 | Claim | Agent says "done" | Not acceptable |
| 1 | Ledger | Agent recorded what it did | Weak |
| 2 | Artifact | Diff/doc/screenshot/query result exists; scope clean | Better |
| 3 | Deterministic | Test exits 0, file contains X, value matches | Strong |
| 4 | Independent re-run | Audit re-runs the check from a clean state / live reality | Stronger |
| 5 | Human acceptance | A named reviewer signs off | Required for subjective/high-risk work |
| 6 | External reality | Production metric, CI status, ticket state, customer confirmation | Strongest |

## How the tier is computed

Tiers are **monotone gates**: you can only claim tier N when every gate up to N
holds *and* there is evidence at tier N.

- **1** required validators were recorded and the ledger is non-empty;
- **2** scope is clean (no forbidden/out-of-scope drift) and met checkpoints carry evidence;
- **3** all locally-runnable required validators passed and none are required-but-unavailable;
- **4** a required validator proved at tier ≥ 4 (independent re-run / live http);
- **5** a required `human_approval`/`rubric` validator passed, or completion was accepted by a named human;
- **6** a required external validator passed with external evidence.

A pure local-code contract correctly tops out at **3–4** — it cannot, by itself,
prove tier 6. That is the point: the tier tells you *how much* to trust "done".

```
Verdict: INCOMPLETE
Completion tier: 3/6
- checkpoint_no_evidence: cp3
- scope_drift: src/routes/public.ts
```
