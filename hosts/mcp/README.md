# Goalkeeper — MCP host

A dependency-free stdio MCP server that exposes Goalkeeper as first-class tools.
The agent calls `gate`/`run`/`checkpoint`/`complete` directly instead of shelling
out to the CLI and parsing stdout. This is the most portable surface: it works
even where hook support is missing or untrusted. It pairs with the hooks rather
than replacing them. The hooks force the gate; MCP lets the agent drive it.

Run it with `goalkeeper mcp` (or `python3 hosts/mcp/server.py`). It speaks
newline-delimited JSON-RPC 2.0 over stdio, with no third-party dependencies.

## Tools

| Tool | What it does |
|------|--------------|
| `goalkeeper_status` | Objective, completion status, checkpoint progress, scope, verdict + tier. |
| `goalkeeper_run` | Run a command and record exit code + bounded output as evidence. |
| `goalkeeper_checkpoint` | Set evidence on a checkpoint, optionally mark it met. |
| `goalkeeper_gate` | Verdict (COMPLETE/INCOMPLETE), tier (0-6), blockers. `rerun=true` earns tier 4. |
| `goalkeeper_complete` | Record completion (only if the gate passes) + write the proof bundle. |
| `goalkeeper_proof` | Write and return the proof bundle. |

## Register

**Claude Code** — drop `.mcp.json` (project-scoped) at the repo root, or merge its
`mcpServers` entry into your existing one:

```json
{ "mcpServers": { "goalkeeper": { "command": "goalkeeper", "args": ["mcp"] } } }
```

**Codex** — add to `~/.codex/config.toml` (or a project `.codex/config.toml` in a
trusted project):

```toml
[mcp_servers.goalkeeper]
command = "goalkeeper"
args = ["mcp"]
```

Both assume `goalkeeper` is on `PATH` (`goalkeeper install shell`). If it isn't,
use an explicit launcher instead:

```json
{ "mcpServers": { "goalkeeper": {
  "command": "python3",
  "args": ["/abs/path/to/goalkeeper/hosts/mcp/server.py"],
  "env": { "GOALKEEPER_CORE_HOME": "/abs/path/to/goalkeeper" }
} } }
```

The server works on the `.goalkeeper/` contract found from the working directory,
the same as the CLI. On a human-gated contract, `goalkeeper_complete` refuses an
`auto:` accepter; a named human has to accept.
