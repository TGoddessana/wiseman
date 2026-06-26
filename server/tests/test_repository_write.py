from wiseman_mcp.repository import WikiRepo


def test_write_then_get_roundtrip(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    assert repo.is_empty() is True
    repo.write_page(
        slug="libs/fastapi-auth",
        kind="library_doc",
        library="fastapi",
        version="0.115.2",
        title="FastAPI auth via dependencies",
        content="Use Depends() for auth. Avoid global state.",
        source="https://fastapi.tiangolo.com/",
        confidence="high",
        tags=["auth", "di"],
        links=["conventions/errors"],
        now="2026-06-26T00:00:00+00:00",
    )
    assert repo.is_empty() is False
    page = repo.get_page("libs/fastapi-auth")
    assert page is not None
    assert page["library"] == "fastapi"
    assert page["version"] == "0.115.2"
    assert page["tags"] == ["auth", "di"]
    assert page["links"] == ["conventions/errors"]
    assert page["created_at"] == "2026-06-26T00:00:00+00:00"


def test_get_missing_returns_none(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    assert repo.get_page("nope") is None


def test_upsert_preserves_created_at_and_logs(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    repo.write_page(slug="a", kind="clean_code", title="t1", content="c1",
                    now="2026-01-01T00:00:00+00:00")
    repo.write_page(slug="a", kind="clean_code", title="t2", content="c2",
                    now="2026-02-02T00:00:00+00:00")
    page = repo.get_page("a")
    assert page["title"] == "t2"
    assert page["created_at"] == "2026-01-01T00:00:00+00:00"
    assert page["updated_at"] == "2026-02-02T00:00:00+00:00"
    logs = repo.conn.execute("SELECT op FROM log WHERE op='write'").fetchall()
    assert len(logs) == 2
