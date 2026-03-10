# Beads MCP Plugin Trial Evaluation

**Issue:** kimberlygarmoe-p56
**Duration:** 2026-03-04 through 2026-04-04
**Decision:** Keep or remove the beads Claude Code plugin

## Method

Use `bd remember "mcp-trial: <observation>"` after sessions where beads is used.
Review with `bd memories mcp-trial` at end of trial.

## Evaluation Criteria

| # | Criterion | What to observe |
|---|-----------|-----------------|
| 1 | Reliability | MCP server crashes, hangs, connection drops, restart frequency |
| 2 | Speed | Issue creation/listing/updating: faster, slower, or same as CLI |
| 3 | Conflict-free | Problems with existing CLI hooks (bd prime, etc.) |
| 4 | Data consistency | Issues created via MCP matching bd list via CLI, sync gaps |
| 5 | Net friction | Overall workflow friction: reduced or increased |

## Decision Rule

Score each criterion: **keep** / **neutral** / **remove**.
- 3+ "keep" → keep plugin
- Otherwise → remove plugin

## Installation

```
/plugin marketplace add steveyegge/beads
/plugin install beads
```

Restart Claude Code after install.
