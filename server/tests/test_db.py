from pathlib import Path
from wiseman_mcp import db


def _tables(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r["name"] for r in rows}


def test_ensure_db_creates_tables_and_fts(tmp_path):
    p = tmp_path / "nested" / "wiki.db"
    conn = db.ensure_db(str(p))
    assert p.exists()
    names = _tables(conn)
    assert {"pages", "links", "log", "meta"}.issubset(names)
    # FTS5 virtual table is registered too
    fts = conn.execute(
        "SELECT name FROM sqlite_master WHERE name='pages_fts'"
    ).fetchone()
    assert fts is not None


def test_ensure_db_is_idempotent(tmp_path):
    p = str(tmp_path / "wiki.db")
    db.ensure_db(p).close()
    # second call must not raise (IF NOT EXISTS everywhere)
    conn = db.ensure_db(p)
    assert "pages" in _tables(conn)
