# Wiseman Dashboard — Design Spec

**Date:** 2026-06-26
**Status:** Approved (design), pending implementation plan

## Goal

Add a **graph-centric local web dashboard** that reads a project's
`.wiseman/wiki.db` and lets a human visually explore the wiki: see pages and
their links as a graph, read page content, search, and check index/lint/log.
Launched via a **separate CLI command** (`wiseman-dash`), independent of the MCP
server.

Visualization (page↔link graph) is the primary purpose; reading and inspection
(search, page detail, lint, log) are secondary. **Read-only for now**, but the
architecture must make a later write/edit extension cheap.

## Non-Goals

- No editing/deletion of pages from the UI (read-only this iteration).
- No slash command. A dashboard is a human-facing tool you view in a browser;
  exposing it as a Claude Code slash command would route a deterministic shell
  launch through the LLM (tokens + a round-trip) for no benefit. CLI only.
- No frontend build chain (no node/bundler). No new Python runtime dependencies.
- Not exposed beyond localhost.

## Architecture

```
wiseman-dash --db <path> [--host 127.0.0.1] [--port 8765] [--no-browser]
        │
        ├─ WikiRepo(db_path)              # reuse existing read methods
        └─ ThreadingHTTPServer(host, port)
             ├─ GET /              → static/index.html
             ├─ GET /static/*      → vendored cytoscape.min.js, marked.min.js, app.js, styles.css
             └─ GET /api/*         → JSON, backed by WikiRepo
        → opens browser at http://host:port/  (unless --no-browser)
```

- **Zero new dependencies.** HTTP is served with the stdlib
  `http.server.ThreadingHTTPServer`; a local single-user dashboard does not need
  a web framework. The graph and markdown libraries are vendored as static files
  in the repo (no CDN, works offline).
- **Bind to `127.0.0.1` by default.** The dashboard exposes wiki contents; it
  must not be reachable off-host without an explicit `--host` override.
- **Reuse `WikiRepo`.** No duplication of data logic; the dashboard is a thin
  read layer over the same repository the MCP server uses.

## Components

### New package: `server/src/wiseman_mcp/dashboard/`

- `cli.py` — `wiseman-dash` entry point. Parses `--db` (required), `--host`,
  `--port`, `--no-browser`. Validates the DB path exists, constructs `WikiRepo`,
  starts the server, optionally opens the browser, runs until Ctrl-C.
- `server.py` — `ThreadingHTTPServer` + a `BaseHTTPRequestHandler` subclass.
  Routing dispatches `/`, `/static/*`, and `/api/*`. JSON responses via a small
  helper; static files served from the packaged `static/` dir via
  `importlib.resources`.
- `static/` — `index.html`, `styles.css`, `app.js`, `cytoscape.min.js`,
  `marked.min.js` (vendored).

Register the entry point in `pyproject.toml`:
```toml
[project.scripts]
wiseman-mcp  = "wiseman_mcp.cli:main"
wiseman-dash = "wiseman_mcp.dashboard.cli:main"
```

### Packaging

Static assets live inside the package (`src/wiseman_mcp/dashboard/static/`).
Ensure the wheel includes them — mirror the existing `schema.sql` handling with a
`force-include` (or equivalent hatchling package-data inclusion) so the assets
ship with the installed package and resolve via `importlib.resources`.

### `WikiRepo` additions (read-only, purely additive)

Two new methods, following existing patterns (RLock, `dict(row)`):

- `graph() -> {"nodes": [...], "edges": [...]}`
  - nodes: `{slug, title, kind, library, confidence}` for every page
  - edges: `{src, dst}` from the `links` table (both endpoints exist as pages)
- `recent_log(limit=100) -> [{ts, op, page_slug, note}]`
  - most-recent-first from the `log` table

No existing method changes.

## API (all read-only, `/api` prefix)

| Route | Returns | Backed by |
|---|---|---|
| `GET /api/graph` | `{nodes, edges}` | `graph()` (new) |
| `GET /api/page/{slug}` | full page incl. `links` | `get_page()` |
| `GET /api/search?q=&kind=&library=&limit=` | search hits | `search()` |
| `GET /api/index` | `{total, by_kind, libraries, pages}` | `index()` |
| `GET /api/lint` | `{orphans, missing_source, missing_version, stale}` | `lint()` |
| `GET /api/log?limit=` | recent log entries | `recent_log()` (new) |

The `/api` prefix reserves space for future write routes (`POST /api/page/...`)
without restructuring.

## Frontend (vendored, no build step)

Single `index.html` + vanilla `app.js`. Layout = **graph-centric three-pane**:

- **Left sidebar:** search box; `kind` filter checkboxes; index stats
  (`/api/index`); collapsible lint and log panels.
- **Center:** Cytoscape.js graph. Nodes = pages colored by `kind`; edges =
  links. Built-in `cose` layout (no extra layout plugin needed). Clicking a node
  loads its detail in the right pane and highlights it.
- **Right:** page detail — metadata (kind, version, source, confidence, tags) +
  markdown content rendered with `marked.js` + outgoing links list (clicking a
  link navigates the graph/detail).

`app.js` isolates a **data-fetching layer** (`api.getGraph()`, `api.getPage()`,
…). A future edit feature adds `api.savePage()` here plus the matching POST
route; nothing else moves.

**Library choices:** Cytoscape.js (MIT, single UMD file, built-in layouts) for
the graph; marked.js for markdown. Both vendored.

## Error Handling & Edge Cases

- Unknown slug or route → `404` with a JSON error body; frontend shows a notice.
- Port already in use → clear stderr message naming the port; suggest `--port`;
  exit non-zero.
- Empty DB → graph renders an empty state with "run `/summon-wiseman` first".
- DB file missing → CLI exits immediately with a clear error (before serving).
- Rendered markdown is HTML-escaped where appropriate to keep the XSS surface
  minimal even though content is locally authored.

## Testing

- Unit tests for `WikiRepo.graph()` and `recent_log()` (follow
  `test_repository_*.py` patterns: seed pages/links/log, assert shape).
- HTTP smoke tests: start the server on an ephemeral port against a temp DB,
  assert `GET /`, `GET /static/app.js`, `GET /api/graph`, `GET /api/index`,
  `GET /api/page/{slug}` return 200 with valid JSON/content; unknown slug → 404.
- No JS test framework (keeps the project's lightweight tone). Logic lives in the
  server/API; the frontend stays thin.

## Documentation

- README: add a "Dashboard" section showing how to launch
  (`uv run --directory <plugin>/server wiseman-dash --db .wiseman/wiki.db`, or
  `! …` inside a Claude Code session) and what it shows. Note read-only.

## Future Extension (out of scope now)

Write/edit support: add `POST /api/page/{slug}` (and maybe delete) backed by the
existing `write_page`, plus `api.savePage()` in `app.js` and edit controls in the
detail pane. The `/api` prefix and separated data layer mean no restructuring is
required.
