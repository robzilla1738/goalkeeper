# Risk classes and approval gates

Some goals are harmless. Some can break systems or send messages to real people.
Goalkeeper makes that explicit and enforces it at the completion gate.

## Risk fields

```jsonc
"risk": {
  "level": "low | medium | high | critical",
  "data_sensitivity": "normal | internal | confidential | regulated",
  "external_side_effects": true,
  "approval_required_before": ["deploy", "send", "delete"]
}
```

## Enforcement (in `gate`)

- **High / critical** risk cannot `complete` without a recorded human approval.
- **External side effects** require an `external_side_effects` approval before the
  gate passes.
- Each action in **`approval_required_before`** must have a matching approval.
- **Critical** additionally requires an explicit sandbox/permissions declaration
  (`risk.sandbox_declared: true`).

Record approvals with:

```
goalkeeper approve deploy --by alice --note "change window 2026-06-09 02:00 UTC"
```

Approvals are appended to `state.json` `approvals[]` and to the work-log ledger,
and surface in the proof bundle.

## Seatbelt, not a sandbox

The hook blocks obvious destructive and forbidden-path `Bash` commands, but this
is best-effort pattern matching on the shell string and can be bypassed
(env vars, base64, `python -c`, writing then executing a script). Rely on your
host's permission/sandbox modes for real isolation. Approval gates are about
*deliberate* irreversible actions, not containment.
