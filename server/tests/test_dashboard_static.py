import threading
import urllib.error
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
