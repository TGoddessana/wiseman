# Wiseman

Summon a project-specific **LLM wiki** — the *Wiseman* — and consult it before you code.

Wiseman analyzes your project (dependencies, installed versions, official docs,
clean-code and language best practices, and your own conventions) and builds a
codebase-specific knowledge base in `.wiseman/wiki.db` (SQLite). A bundled MCP
server lets the agent ask the Wiseman before coding and file new findings back —
so it compounds, getting smarter the more you use it.

The guiding rule: **asking the Wiseman must beat the model's own internal
knowledge** — every page is version-pinned, sourced, project-specific, and
non-obvious.

## Install

```
/plugin install wiseman
```

This registers the `wiseman` MCP server automatically (via `uv`, so `uv` must be
installed) and the `/summon-wiseman` skill.

## Use

1. In a project, run `/summon-wiseman` to build the wiki.
2. While coding, the agent consults it with the `ask_wiseman` tool (guided by the
   `@.wiseman/schema.md` manual injected into your `CLAUDE.md`).
3. New, valuable, sourced findings are filed back with `write_page` (the
   compounding loop). Run the `lint` tool occasionally to spot stale/orphan pages.

## Architecture

- `server/` — generic Python FastMCP server (`uv run wiseman-mcp --db <path>`):
  tools `ask_wiseman`, `wiki_index`, `get_page`, `write_page`, `lint`.
- `skills/summon-wiseman/` — the build pipeline skill.
- `templates/schema.md` — the wiki operating manual injected into `CLAUDE.md`.
- `.wiseman/wiki.db` (per project) — SQLite single source of truth (pages/links/
  log/meta + FTS5).

See `docs/superpowers/specs/2026-06-26-summon-wiseman-design.md` for the full design.
