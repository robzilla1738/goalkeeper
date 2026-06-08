# Security Policy

## Threat model — read this first

Goalkeeper Loop's command blocking is a **seatbelt, not a sandbox.**

The hook's destructive-command and forbidden-path screening is best-effort
pattern matching on a single shell string. It is designed to catch *accidental*
footguns (a stray `rm -rf`, an out-of-scope edit), **not** to contain a
determined or compromised agent. It can be bypassed trivially — environment
variables, `base64`/encoding, `python -c "…"`, writing a script and then
executing it, shell expansion, and so on.

**Do not rely on this plugin as a security boundary.** For real isolation, use
your host's own controls:

- **Claude Code** — permission modes and allow/deny rules.
- **Codex** — `sandbox_mode` (`read-only` / `workspace-write`) and
  `approval_policy`.

Run untrusted or high-autonomy work in a disposable environment (container/VM)
regardless of this plugin.

## What the plugin touches

- Reads/writes only the project-local `.goalkeeper/` directory and runs commands
  you (or the agent) invoke. It has no network calls and no telemetry.
- `goalkeeper run` and the agent execute shell commands with your privileges —
  treat the contract and any seeded validations as code you are choosing to run.
- The hook reads host event JSON on stdin and writes decisions on stdout; it
  never executes the screened command itself (it only allows/denies).

## Supported versions

This is an early-stage project; security fixes land on the latest version only.

## Reporting a vulnerability

Please report suspected vulnerabilities **privately** rather than opening a
public issue:

- Use GitHub's **"Report a vulnerability"** (Security → Advisories) on
  `robzilla1738/goalkeeper`, or
- email the maintainer listed in the plugin manifests.

Include reproduction steps, affected host/version, and impact. We'll acknowledge
and work on a fix; please allow reasonable time before public disclosure.
