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
