import json
import threading
import urllib.error
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
