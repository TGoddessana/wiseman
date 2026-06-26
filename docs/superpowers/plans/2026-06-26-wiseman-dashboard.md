# Wiseman Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `wiseman-dash`, a read-only graph-centric local web dashboard that reads `.wiseman/wiki.db` and lets a human explore the wiki in a browser.

**Architecture:** A separate CLI command starts a stdlib `ThreadingHTTPServer` that reuses the existing `WikiRepo` for data and serves a small JSON `/api/*` plus vendored static frontend (Cytoscape.js graph + marked.js markdown). Read-only now; the `/api` prefix and a separated JS data layer keep a future write extension cheap.

**Tech Stack:** Python 3.10+ stdlib `http.server` (zero new runtime deps), SQLite via existing `WikiRepo`, vendored Cytoscape.js + marked.js, vanilla JS/CSS.

## Global Constraints

- Python `>=3.10`; the only runtime dependency stays `fastmcp>=3.4,<4` — **no new runtime dependencies** (HTTP via stdlib).
- Frontend libraries are **vendored** static files (no CDN, works offline). No frontend build chain.
- Server **binds `127.0.0.1` by default**; off-host exposure only via explicit `--host`.
- **No slash command** — CLI only (dashboard is human-facing).
- Follow existing `WikiRepo` patterns: `self._lock` (RLock) around every DB access, `dict(row)` conversion. New repo methods are **read-only and purely additive**.
- All work happens under `server/`; run tests with `uv run --directory server pytest`.

---

### Task 1: `WikiRepo.graph()`

**Files:**
- Modify: `server/src/wiseman_mcp/repository.py` (add method to `WikiRepo`, after `index`)
- Test: `server/tests/test_repository_graph.py`

**Interfaces:**
- Consumes: existing `WikiRepo(db_path)`, `write_page(...)`.
- Produces: `WikiRepo.graph() -> {"nodes": list[dict], "edges": list[dict]}` where each node is `{"slug","title","kind","library","confidence"}` and each edge is `{"src","dst"}`. Edges are included **only when both endpoints exist as pages** (orphan link targets dropped).

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_repository_graph.py`:

```python
from wiseman_mcp.repository import WikiRepo


def test_graph_returns_nodes_and_filtered_edges(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    repo.write_page(slug="a", kind="note", title="A", content="x",
                    links=["b", "ghost"], now="2026-01-01T00:00:00+00:00")
    repo.write_page(slug="b", kind="note", title="B", content="y",
                    now="2026-01-01T00:00:00+00:00")
    g = repo.graph()
    assert {n["slug"] for n in g["nodes"]} == {"a", "b"}
    node_a = next(n for n in g["nodes"] if n["slug"] == "a")
    assert node_a == {"slug": "a", "title": "A", "kind": "note",
                      "library": None, "confidence": "medium"}
    # edge to "ghost" is dropped because no page named "ghost" exists
    assert g["edges"] == [{"src": "a", "dst": "b"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory server pytest tests/test_repository_graph.py -v`
Expected: FAIL with `AttributeError: 'WikiRepo' object has no attribute 'graph'`

- [ ] **Step 3: Write minimal implementation**

In `server/src/wiseman_mcp/repository.py`, add this method to `WikiRepo` (place it right after the `index` method):

```python
    def graph(self) -> dict:
        with self._lock:
            nodes = [
                {"slug": r["slug"], "title": r["title"], "kind": r["kind"],
                 "library": r["library"], "confidence": r["confidence"]}
                for r in self.conn.execute(
                    "SELECT slug, title, kind, library, confidence "
                    "FROM pages ORDER BY slug"
                ).fetchall()
            ]
            slugs = {n["slug"] for n in nodes}
            edges = [
                {"src": r["src_slug"], "dst": r["dst_slug"]}
                for r in self.conn.execute(
                    "SELECT src_slug, dst_slug FROM links "
                    "ORDER BY src_slug, dst_slug"
                ).fetchall()
                if r["src_slug"] in slugs and r["dst_slug"] in slugs
            ]
            return {"nodes": nodes, "edges": edges}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory server pytest tests/test_repository_graph.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/src/wiseman_mcp/repository.py server/tests/test_repository_graph.py
git commit -m "feat: add WikiRepo.graph() for dashboard"
```

---

### Task 2: `WikiRepo.recent_log()`

**Files:**
- Modify: `server/src/wiseman_mcp/repository.py` (add method to `WikiRepo`, after `graph`)
- Test: `server/tests/test_repository_log.py`

**Interfaces:**
- Consumes: existing `WikiRepo`, `write_page(...)` (which inserts a `log` row per write).
- Produces: `WikiRepo.recent_log(limit=100) -> list[dict]`, each `{"ts","op","page_slug","note"}`, **most recent first** (by `log.id` descending).

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_repository_log.py`:

```python
from wiseman_mcp.repository import WikiRepo


def test_recent_log_most_recent_first(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    repo.write_page(slug="a", kind="note", title="A", content="x",
                    now="2026-01-01T00:00:00+00:00")
    repo.write_page(slug="b", kind="note", title="B", content="y",
                    now="2026-01-02T00:00:00+00:00")
    log = repo.recent_log(limit=10)
    assert [e["page_slug"] for e in log] == ["b", "a"]
    assert log[0]["op"] == "write"
    assert set(log[0].keys()) == {"ts", "op", "page_slug", "note"}


def test_recent_log_respects_limit(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    for i in range(5):
        repo.write_page(slug=f"p{i}", kind="note", title=f"P{i}", content="x",
                        now="2026-01-01T00:00:00+00:00")
    assert len(repo.recent_log(limit=3)) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory server pytest tests/test_repository_log.py -v`
Expected: FAIL with `AttributeError: 'WikiRepo' object has no attribute 'recent_log'`

- [ ] **Step 3: Write minimal implementation**

In `server/src/wiseman_mcp/repository.py`, add this method to `WikiRepo` (right after `graph`):

```python
    def recent_log(self, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT ts, op, page_slug, note FROM log "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory server pytest tests/test_repository_log.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/src/wiseman_mcp/repository.py server/tests/test_repository_log.py
git commit -m "feat: add WikiRepo.recent_log() for dashboard"
```

---

### Task 3: Dashboard HTTP server + `/api` routes

**Files:**
- Create: `server/src/wiseman_mcp/dashboard/__init__.py` (empty package marker)
- Create: `server/src/wiseman_mcp/dashboard/server.py`
- Test: `server/tests/test_dashboard_server.py`

**Interfaces:**
- Consumes: `WikiRepo` and its methods `graph()`, `index()`, `lint()`, `recent_log(limit)`, `search(q, kind, library, limit)`, `get_page(slug)`.
- Produces:
  - `dashboard.server.make_handler(repo) -> type` — a `BaseHTTPRequestHandler` subclass bound to `repo`.
  - `dashboard.server.serve(repo, host="127.0.0.1", port=8765) -> ThreadingHTTPServer` — constructed (not yet serving); caller runs `.serve_forever()`.
  - Routes: `GET /` → `static/index.html`; `GET /static/<name>` → vendored asset; `GET /api/graph|index|lint`; `GET /api/log?limit=`; `GET /api/search?q=&kind=&library=&limit=`; `GET /api/page/<slug>` (slug may contain `/`). Unknown slug or route → `404` with JSON `{"error": ...}`.

Note: `GET /` and `GET /static/*` are wired here but their tests live in Task 5 (the static files do not exist until then). Task 3 tests cover the `/api/*` routes and 404 behavior only.

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_dashboard_server.py`:

```python
import json
import threading
import urllib.request

from wiseman_mcp.repository import WikiRepo
from wiseman_mcp.dashboard import server as dash


def _seeded_repo(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    repo.write_page(slug="a", kind="note", title="A", content="# hello",
                    links=["b"], now="2026-01-01T00:00:00+00:00")
    repo.write_page(slug="b", kind="note", title="B", content="y",
                    now="2026-01-01T00:00:00+00:00")
    return repo


def _start(repo):
    httpd = dash.serve(repo, host="127.0.0.1", port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, httpd.server_address[1]


def _get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as r:
        return r.status, json.loads(r.read())


def test_api_graph(tmp_path):
    httpd, port = _start(_seeded_repo(tmp_path))
    try:
        status, body = _get(port, "/api/graph")
        assert status == 200
        assert {n["slug"] for n in body["nodes"]} == {"a", "b"}
        assert {"src": "a", "dst": "b"} in body["edges"]
    finally:
        httpd.shutdown()


def test_api_index_and_page(tmp_path):
    httpd, port = _start(_seeded_repo(tmp_path))
    try:
        _, idx = _get(port, "/api/index")
        assert idx["total"] == 2
        _, page = _get(port, "/api/page/a")
        assert page["title"] == "A"
        assert page["links"] == ["b"]
    finally:
        httpd.shutdown()


def test_api_unknown_page_is_404(tmp_path):
    httpd, port = _start(_seeded_repo(tmp_path))
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/page/nope")
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as e:
            assert e.code == 404
            assert "error" in json.loads(e.read())
    finally:
        httpd.shutdown()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory server pytest tests/test_dashboard_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'wiseman_mcp.dashboard'`

- [ ] **Step 3: Write minimal implementation**

Create `server/src/wiseman_mcp/dashboard/__init__.py` (empty file):

```python
```

Create `server/src/wiseman_mcp/dashboard/server.py`:

```python
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import urlparse, parse_qs, unquote

_STATIC = resources.files("wiseman_mcp.dashboard").joinpath("static")


def _read_static(name: str) -> bytes:
    return _STATIC.joinpath(name).read_bytes()


class _Handler(BaseHTTPRequestHandler):
    repo = None  # bound by make_handler

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status: int = 200) -> None:
        self._send(json.dumps(obj).encode("utf-8"),
                   "application/json; charset=utf-8", status)

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message}, status=status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path, qs = parsed.path, parse_qs(parsed.query)
        try:
            if path == "/":
                self._send(_read_static("index.html"), "text/html; charset=utf-8")
            elif path.startswith("/static/"):
                self._serve_static(path[len("/static/"):])
            elif path == "/api/graph":
                self._json(self.repo.graph())
            elif path == "/api/index":
                self._json(self.repo.index())
            elif path == "/api/lint":
                self._json(self.repo.lint())
            elif path == "/api/log":
                self._json(self.repo.recent_log(limit=int(qs.get("limit", ["100"])[0])))
            elif path == "/api/search":
                self._json(self.repo.search(
                    qs.get("q", [""])[0],
                    kind=qs.get("kind", [None])[0],
                    library=qs.get("library", [None])[0],
                    limit=int(qs.get("limit", ["10"])[0]),
                ))
            elif path.startswith("/api/page/"):
                slug = unquote(path[len("/api/page/"):])
                page = self.repo.get_page(slug)
                if page is None:
                    self._error(404, f"page not found: {slug}")
                else:
                    self._json(page)
            else:
                self._error(404, f"not found: {path}")
        except Exception as exc:  # surface as JSON 500 rather than a stack dump
            self._error(500, str(exc))

    def _serve_static(self, rel: str) -> None:
        if not rel or ".." in rel or rel.startswith("/"):
            self._error(404, "not found")
            return
        try:
            body = _read_static(rel)
        except (FileNotFoundError, OSError, IsADirectoryError):
            self._error(404, f"not found: {rel}")
            return
        ctype = mimetypes.guess_type(rel)[0] or "application/octet-stream"
        self._send(body, ctype)

    def log_message(self, *args) -> None:  # keep the console quiet
        pass


def make_handler(repo):
    return type("BoundHandler", (_Handler,), {"repo": repo})


def serve(repo, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(repo))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory server pytest tests/test_dashboard_server.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add server/src/wiseman_mcp/dashboard/__init__.py server/src/wiseman_mcp/dashboard/server.py server/tests/test_dashboard_server.py
git commit -m "feat: add dashboard HTTP server with /api routes"
```

---

### Task 4: `wiseman-dash` CLI + packaging

**Files:**
- Create: `server/src/wiseman_mcp/dashboard/cli.py`
- Modify: `server/pyproject.toml` (add console script + static force-include)
- Test: `server/tests/test_dashboard_cli.py`

**Interfaces:**
- Consumes: `WikiRepo`, `dashboard.server.serve(repo, host, port)`.
- Produces: `dashboard.cli.main(argv=None) -> None`. Args: `--db` (required), `--host` (default `127.0.0.1`), `--port` (int, default `8765`), `--no-browser` (flag). Exits non-zero (`SystemExit`) when the DB path is missing or the port cannot be bound. Console script `wiseman-dash`.

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_dashboard_cli.py`:

```python
import pytest

from wiseman_mcp.dashboard import cli


def test_cli_errors_when_db_missing(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--db", str(tmp_path / "nope.db")])
    assert exc.value.code != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory server pytest tests/test_dashboard_cli.py -v`
Expected: FAIL with `ImportError`/`ModuleNotFoundError` (no `cli` in `dashboard`)

- [ ] **Step 3: Write minimal implementation**

Create `server/src/wiseman_mcp/dashboard/cli.py`:

```python
import argparse
import sys
import webbrowser
from pathlib import Path

from ..repository import WikiRepo
from . import server as dash_server


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="wiseman-dash")
    parser.add_argument("--db", required=True, help="Path to the project's wiki.db")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true",
                        help="Do not open a browser window")
    args = parser.parse_args(argv)

    db_path = Path(args.db).expanduser()
    if not db_path.exists():
        parser.error(f"db not found: {db_path} (run /summon-wiseman first)")

    repo = WikiRepo(str(db_path))
    try:
        httpd = dash_server.serve(repo, host=args.host, port=args.port)
    except OSError as exc:
        print(f"wiseman-dash: cannot bind {args.host}:{args.port}: {exc}",
              file=sys.stderr)
        print("try a different --port", file=sys.stderr)
        raise SystemExit(1)

    url = f"http://{args.host}:{args.port}/"
    print(f"wiseman-dash serving {db_path} at {url}  (Ctrl-C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nwiseman-dash: shutting down")
        httpd.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory server pytest tests/test_dashboard_cli.py -v`
Expected: PASS

- [ ] **Step 5: Register the console script and package the static dir**

In `server/pyproject.toml`, change the `[project.scripts]` block to:

```toml
[project.scripts]
wiseman-mcp  = "wiseman_mcp.cli:main"
wiseman-dash = "wiseman_mcp.dashboard.cli:main"
```

And change the force-include block to also ship the static assets:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/wiseman_mcp/schema.sql" = "wiseman_mcp/schema.sql"
"src/wiseman_mcp/dashboard/static" = "wiseman_mcp/dashboard/static"
```

- [ ] **Step 6: Verify the console script resolves**

Run: `uv run --directory server wiseman-dash --help`
Expected: argparse usage text listing `--db`, `--host`, `--port`, `--no-browser` (exit 0).

- [ ] **Step 7: Commit**

```bash
git add server/src/wiseman_mcp/dashboard/cli.py server/pyproject.toml server/tests/test_dashboard_cli.py
git commit -m "feat: add wiseman-dash CLI and package static assets"
```

---

### Task 5: Frontend (vendored libs + index.html, styles.css, app.js)

**Files:**
- Create: `server/src/wiseman_mcp/dashboard/static/cytoscape.min.js` (vendored, downloaded)
- Create: `server/src/wiseman_mcp/dashboard/static/marked.min.js` (vendored, downloaded)
- Create: `server/src/wiseman_mcp/dashboard/static/index.html`
- Create: `server/src/wiseman_mcp/dashboard/static/styles.css`
- Create: `server/src/wiseman_mcp/dashboard/static/app.js`
- Test: `server/tests/test_dashboard_static.py`

**Interfaces:**
- Consumes: the `/` and `/static/<name>` routes from Task 3, and the `/api/*` JSON shapes.
- Produces: a working browser UI (graph-centric three-pane). Cytoscape global `cytoscape`, marked global `marked` (`marked.parse`). `app.js` isolates a `const api = {...}` fetch layer (future write methods land here).

- [ ] **Step 1: Vendor the libraries (pinned versions)**

Run:

```bash
mkdir -p server/src/wiseman_mcp/dashboard/static
curl -fsSL https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.2/cytoscape.min.js \
  -o server/src/wiseman_mcp/dashboard/static/cytoscape.min.js
curl -fsSL https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js \
  -o server/src/wiseman_mcp/dashboard/static/marked.min.js
```

Verify both files are non-empty JS:

```bash
wc -c server/src/wiseman_mcp/dashboard/static/cytoscape.min.js \
      server/src/wiseman_mcp/dashboard/static/marked.min.js
head -c 80 server/src/wiseman_mcp/dashboard/static/cytoscape.min.js
```

Expected: cytoscape ~400KB+, marked ~30KB+, and the `head` output looks like minified JS (not an HTML error page).

- [ ] **Step 2: Write `index.html`**

Create `server/src/wiseman_mcp/dashboard/static/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Wiseman Dashboard</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
  <div id="app">
    <aside id="sidebar">
      <h1>Wiseman</h1>
      <input id="search" type="search" placeholder="search the wiki…">
      <div id="filters"></div>
      <div id="stats"></div>
      <details id="lint-box"><summary>lint</summary><div id="lint"></div></details>
      <details id="log-box"><summary>log</summary><div id="log"></div></details>
    </aside>
    <main id="graph"></main>
    <section id="detail"><p class="empty">Click a node to read its page.</p></section>
  </div>
  <script src="/static/cytoscape.min.js"></script>
  <script src="/static/marked.min.js"></script>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Write `styles.css`**

Create `server/src/wiseman_mcp/dashboard/static/styles.css`:

```css
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, -apple-system, sans-serif; }
#app { display: grid; grid-template-columns: 240px 1fr 360px; height: 100vh; }
#sidebar { padding: 12px; border-right: 1px solid #ddd; overflow-y: auto; }
#sidebar h1 { font-size: 18px; margin: 0 0 12px; }
#search { width: 100%; padding: 6px; margin-bottom: 12px; }
#filters label { display: block; font-size: 13px; margin: 2px 0; cursor: pointer; }
#stats { margin: 12px 0; font-size: 13px; }
#stats .stat { font-weight: bold; margin-bottom: 4px; }
#graph { width: 100%; height: 100%; }
#detail { padding: 16px; border-left: 1px solid #ddd; overflow-y: auto; }
#detail .empty { color: #999; }
#detail .meta { color: #666; font-size: 13px; margin: 4px 0; }
.tag { background: #eee; border-radius: 3px; padding: 1px 6px; font-size: 12px; }
.content { margin-top: 12px; line-height: 1.5; }
.content pre { background: #f6f6f6; padding: 8px; overflow-x: auto; }
.content code { background: #f6f6f6; padding: 1px 4px; border-radius: 3px; }
details summary { cursor: pointer; margin-top: 8px; font-weight: bold; }
.lint-row, .log-row { font-size: 12px; margin: 2px 0; word-break: break-all; }
.links a { cursor: pointer; }
```

- [ ] **Step 4: Write `app.js`**

Create `server/src/wiseman_mcp/dashboard/static/app.js`:

```javascript
// Data-fetching layer. Future write features add methods here only.
const api = {
  getGraph: () => fetch("/api/graph").then((r) => r.json()),
  getIndex: () => fetch("/api/index").then((r) => r.json()),
  getPage: (slug) => fetch("/api/page/" + encodeURI(slug)).then((r) => r.json()),
  getLint: () => fetch("/api/lint").then((r) => r.json()),
  getLog: () => fetch("/api/log").then((r) => r.json()),
  search: (q) => fetch("/api/search?q=" + encodeURIComponent(q)).then((r) => r.json()),
};

const PALETTE = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
                 "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac"];
const KIND_COLORS = {};
function colorForKind(kind) {
  if (!(kind in KIND_COLORS)) {
    KIND_COLORS[kind] = PALETTE[Object.keys(KIND_COLORS).length % PALETTE.length];
  }
  return KIND_COLORS[kind];
}

let cy = null;
const activeKinds = new Set();

async function init() {
  const [graph, index] = await Promise.all([api.getGraph(), api.getIndex()]);
  renderStats(index);
  renderFilters(index);
  renderGraph(graph);
  wireSearch();
  wireLintLog();
}

function renderGraph(graph) {
  const elements = [
    ...graph.nodes.map((n) => ({
      data: { id: n.slug, label: n.title || n.slug, kind: n.kind },
    })),
    ...graph.edges.map((e) => ({ data: { source: e.src, target: e.dst } })),
  ];
  cy = cytoscape({
    container: document.getElementById("graph"),
    elements,
    style: [
      { selector: "node", style: {
          "background-color": (ele) => colorForKind(ele.data("kind")),
          label: "data(label)", "font-size": 8, color: "#222",
          "text-valign": "bottom", "text-wrap": "ellipsis", "text-max-width": 80 } },
      { selector: "edge", style: {
          width: 1, "line-color": "#bbb", "target-arrow-color": "#bbb",
          "target-arrow-shape": "triangle", "curve-style": "bezier" } },
      { selector: ".hidden", style: { display: "none" } },
      { selector: ".highlight", style: { "border-width": 3, "border-color": "#333" } },
    ],
    layout: { name: "cose", animate: false },
  });
  cy.on("tap", "node", (evt) => loadDetail(evt.target.id()));
}

async function loadDetail(slug) {
  const page = await api.getPage(slug);
  const el = document.getElementById("detail");
  if (page.error) { el.innerHTML = `<p class="empty">${page.error}</p>`; return; }
  const meta = [page.kind, page.library, page.version, page.confidence]
    .filter(Boolean).join(" · ");
  const tags = (page.tags || []).map((t) => `<span class="tag">${t}</span>`).join(" ");
  const links = (page.links || [])
    .map((l) => `<li><a data-slug="${l}">${l}</a></li>`).join("");
  el.innerHTML = `
    <h2>${page.title || page.slug}</h2>
    <div class="meta">${meta}</div>
    ${page.source ? `<div class="source"><a href="${page.source}" target="_blank" rel="noopener">source</a></div>` : ""}
    <div class="tags">${tags}</div>
    <article class="content">${marked.parse(page.content || "")}</article>
    ${links ? `<h3>links</h3><ul class="links">${links}</ul>` : ""}`;
  el.querySelectorAll("a[data-slug]").forEach((a) =>
    a.addEventListener("click", (e) => { e.preventDefault(); focusNode(a.dataset.slug); }));
  cy.elements().removeClass("highlight");
  cy.getElementById(slug).addClass("highlight");
}

function focusNode(slug) {
  const node = cy.getElementById(slug);
  if (node.nonempty()) { cy.center(node); loadDetail(slug); }
}

function renderStats(index) {
  document.getElementById("stats").innerHTML =
    `<div class="stat">${index.total} pages</div>` +
    Object.entries(index.by_kind)
      .map(([k, n]) => `<div class="stat-row">${k}: ${n}</div>`).join("");
}

function renderFilters(index) {
  const box = document.getElementById("filters");
  Object.keys(index.by_kind).forEach((kind) => {
    activeKinds.add(kind);
    const label = document.createElement("label");
    label.innerHTML =
      `<input type="checkbox" checked> <span style="color:${colorForKind(kind)}">●</span> ${kind}`;
    label.querySelector("input").addEventListener("change", (e) => {
      if (e.target.checked) activeKinds.add(kind); else activeKinds.delete(kind);
      applyFilter();
    });
    box.appendChild(label);
  });
}

function applyFilter() {
  cy.nodes().forEach((n) => n.toggleClass("hidden", !activeKinds.has(n.data("kind"))));
}

function wireSearch() {
  const input = document.getElementById("search");
  let t;
  input.addEventListener("input", () => {
    clearTimeout(t);
    t = setTimeout(async () => {
      const q = input.value.trim();
      cy.elements().removeClass("highlight");
      if (!q) return;
      const hits = await api.search(q);
      const slugs = new Set(hits.map((h) => h.slug));
      cy.nodes().forEach((n) => { if (slugs.has(n.id())) n.addClass("highlight"); });
    }, 200);
  });
}

function wireLintLog() {
  document.getElementById("lint-box").addEventListener("toggle", async (e) => {
    if (!e.target.open) return;
    const lint = await api.getLint();
    document.getElementById("lint").innerHTML = Object.entries(lint)
      .map(([k, v]) => `<div class="lint-row"><b>${k}</b>: ${v.length ? v.join(", ") : "—"}</div>`)
      .join("");
  });
  document.getElementById("log-box").addEventListener("toggle", async (e) => {
    if (!e.target.open) return;
    const log = await api.getLog();
    document.getElementById("log").innerHTML = log
      .map((l) => `<div class="log-row">${l.ts.slice(0, 10)} ${l.op} ${l.page_slug || ""}</div>`)
      .join("");
  });
}

init();
```

- [ ] **Step 5: Write the static-serving smoke test**

Create `server/tests/test_dashboard_static.py`:

```python
import threading
import urllib.request

from wiseman_mcp.repository import WikiRepo
from wiseman_mcp.dashboard import server as dash


def _start(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    httpd = dash.serve(repo, host="127.0.0.1", port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def _raw(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as r:
        return r.status, r.read()


def test_index_and_assets_served(tmp_path):
    httpd, port = _start(tmp_path)
    try:
        status, html = _raw(port, "/")
        assert status == 200
        assert b"Wiseman" in html
        assert _raw(port, "/static/app.js")[0] == 200
        assert _raw(port, "/static/styles.css")[0] == 200
        assert _raw(port, "/static/cytoscape.min.js")[0] == 200
        assert _raw(port, "/static/marked.min.js")[0] == 200
    finally:
        httpd.shutdown()


def test_static_traversal_blocked(tmp_path):
    httpd, port = _start(tmp_path)
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/static/../server.py")
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        httpd.shutdown()
```

- [ ] **Step 6: Run the static tests**

Run: `uv run --directory server pytest tests/test_dashboard_static.py -v`
Expected: PASS (2 passed)

Note: `urllib` may normalize `/static/../server.py` to `/server.py` client-side; either way the result is a 404, which the test asserts.

- [ ] **Step 7: Manual visual check**

Run (using this repo's own DB if present, else any project's `.wiseman/wiki.db`):

```bash
uv run --directory server wiseman-dash --db ../.wiseman/wiki.db --no-browser
```

Then open the printed URL. Expected: three-pane layout, a graph of nodes, clicking a node shows rendered markdown on the right, kind filters toggle nodes, lint/log expanders load. Stop with Ctrl-C. (If no DB exists yet, the graph is empty — that is the documented empty state.)

- [ ] **Step 8: Commit**

```bash
git add server/src/wiseman_mcp/dashboard/static server/tests/test_dashboard_static.py
git commit -m "feat: add vendored graph dashboard frontend"
```

---

### Task 6: README documentation

**Files:**
- Modify: `README.md` (add a "Dashboard" subsection; extend the Architecture list)

**Interfaces:**
- Consumes: the `wiseman-dash` CLI from Task 4.
- Produces: user-facing docs. No test.

- [ ] **Step 1: Add the Dashboard section**

In `README.md`, insert this section immediately after the `## Use` section (before `## Architecture`):

```markdown
## Dashboard

Explore the wiki visually in a browser — a graph of pages and their links, with
page contents, search, and lint/log panels. It is **read-only**.

```
uv run --directory <plugin>/server wiseman-dash --db .wiseman/wiki.db
```

Inside a Claude Code session you can launch it with the `!` prefix. Options:
`--host` (default `127.0.0.1`), `--port` (default `8765`), `--no-browser`. The
server binds to localhost only and uses no external network (graph/markdown
libraries are vendored).
```

- [ ] **Step 2: Extend the Architecture list**

In `README.md`, in the `## Architecture` bullet list, add this bullet after the `server/` bullet:

```markdown
- `server/` (dashboard) — `wiseman-dash --db <path>`: read-only local web UI
  (stdlib HTTP + vendored Cytoscape.js graph), `/api/*` over the same `WikiRepo`.
```

- [ ] **Step 3: Run the full test suite**

Run: `uv run --directory server pytest -q`
Expected: all tests pass (existing suite + the new graph/log/server/cli/static tests).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document the wiseman-dash dashboard"
```

---

## Self-Review

**Spec coverage:**
- Separate CLI command (`wiseman-dash`) → Task 4. ✓
- Reuse `WikiRepo`, additive read methods `graph()` + `recent_log()` → Tasks 1, 2. ✓
- stdlib `ThreadingHTTPServer`, 127.0.0.1 default → Task 3 + Task 4 (`--host`). ✓
- All six `/api` routes + `/` + `/static/*` → Task 3. ✓
- Vendored Cytoscape.js + marked.js, three-pane layout, kind colors/filters, detail markdown, search highlight, lint/log → Task 5. ✓
- Packaging static assets → Task 4 Step 5. ✓
- Error handling: 404 JSON, port-in-use message, missing DB, empty-DB state, path-traversal block → Tasks 3, 4, 5. ✓
- Tests for repo methods + HTTP smoke + static + 404 → Tasks 1, 2, 3, 5. ✓
- README docs → Task 6. ✓
- No slash command (explicit non-goal) → not implemented, by design. ✓

**Placeholder scan:** No TBD/TODO; every code step has full content. ✓

**Type consistency:** `graph()` returns `{"nodes","edges"}` with node keys `slug/title/kind/library/confidence` and edge keys `src/dst` — consumed identically in `server.py` and `app.js`. `recent_log(limit)` keys `ts/op/page_slug/note` — consumed in `/api/log` and `app.js`. `make_handler`/`serve` signatures match across `server.py`, `cli.py`, and all tests. ✓
