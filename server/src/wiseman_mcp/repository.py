from datetime import datetime, timezone

from . import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_page(row) -> dict:
    page = dict(row)
    page["tags"] = [t for t in (page.get("tags") or "").split(",") if t]
    return page


class WikiRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = db.ensure_db(db_path)

    def is_empty(self) -> bool:
        n = self.conn.execute("SELECT COUNT(*) AS n FROM pages").fetchone()["n"]
        return n == 0

    def write_page(self, *, slug, kind, title, content, library=None,
                   version=None, source=None, confidence="medium",
                   tags=None, links=None, now=None) -> dict:
        ts = now or _now()
        tags_str = ",".join(tags or [])
        self.conn.execute(
            """
            INSERT INTO pages (slug, kind, library, version, title, content,
                               source, confidence, tags, created_at, updated_at)
            VALUES (:slug,:kind,:library,:version,:title,:content,
                    :source,:confidence,:tags,:ts,:ts)
            ON CONFLICT(slug) DO UPDATE SET
              kind=excluded.kind, library=excluded.library,
              version=excluded.version, title=excluded.title,
              content=excluded.content, source=excluded.source,
              confidence=excluded.confidence, tags=excluded.tags,
              updated_at=excluded.updated_at
            """,
            {"slug": slug, "kind": kind, "library": library, "version": version,
             "title": title, "content": content, "source": source,
             "confidence": confidence, "tags": tags_str, "ts": ts},
        )
        self.conn.execute("DELETE FROM links WHERE src_slug = ?", (slug,))
        for dst in (links or []):
            self.conn.execute(
                "INSERT OR IGNORE INTO links (src_slug, dst_slug) VALUES (?, ?)",
                (slug, dst),
            )
        self.conn.execute(
            "INSERT INTO log (ts, op, page_slug, note) VALUES (?, 'write', ?, ?)",
            (ts, slug, title),
        )
        self.conn.commit()
        return self.get_page(slug)

    def get_page(self, slug: str):
        row = self.conn.execute(
            "SELECT * FROM pages WHERE slug = ?", (slug,)
        ).fetchone()
        if row is None:
            return None
        page = _row_to_page(row)
        link_rows = self.conn.execute(
            "SELECT dst_slug FROM links WHERE src_slug = ? ORDER BY dst_slug", (slug,)
        ).fetchall()
        page["links"] = [r["dst_slug"] for r in link_rows]
        return page

    @staticmethod
    def _fts_query(query: str) -> str:
        toks = [t for t in "".join(
            c if (c.isalnum() or c.isspace()) else " " for c in query
        ).split() if t]
        return " OR ".join(f'"{t}"' for t in toks)

    def search(self, query, kind=None, library=None, limit=10):
        match = self._fts_query(query)
        if not match:
            return []
        sql = [
            "SELECT p.slug, p.title, p.kind, p.library, p.version, p.source,",
            "       p.confidence,",
            "       snippet(pages_fts, 1, '«', '»', '…', 24) AS snippet,",
            "       bm25(pages_fts) AS score",
            "FROM pages_fts JOIN pages p ON p.id = pages_fts.rowid",
            "WHERE pages_fts MATCH :match",
        ]
        params = {"match": match, "limit": limit}
        if kind:
            sql.append("AND p.kind = :kind")
            params["kind"] = kind
        if library:
            sql.append("AND p.library = :library")
            params["library"] = library
        sql.append("ORDER BY score LIMIT :limit")
        rows = self.conn.execute("\n".join(sql), params).fetchall()
        return [dict(r) for r in rows]

    def index(self):
        total = self.conn.execute("SELECT COUNT(*) AS n FROM pages").fetchone()["n"]
        by_kind = {
            r["kind"]: r["n"]
            for r in self.conn.execute(
                "SELECT kind, COUNT(*) AS n FROM pages GROUP BY kind"
            ).fetchall()
        }
        libraries = [
            {"library": r["library"], "version": r["version"], "pages": r["n"]}
            for r in self.conn.execute(
                """SELECT library, version, COUNT(*) AS n FROM pages
                   WHERE library IS NOT NULL
                   GROUP BY library, version ORDER BY library"""
            ).fetchall()
        ]
        pages = [
            {"slug": r["slug"], "title": r["title"], "kind": r["kind"],
             "library": r["library"]}
            for r in self.conn.execute(
                "SELECT slug, title, kind, library FROM pages ORDER BY slug"
            ).fetchall()
        ]
        return {"total": total, "by_kind": by_kind,
                "libraries": libraries, "pages": pages}
