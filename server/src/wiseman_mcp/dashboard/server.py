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
