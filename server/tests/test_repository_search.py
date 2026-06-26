from wiseman_mcp.repository import WikiRepo


def _seed(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    repo.write_page(slug="libs/fastapi-auth", kind="library_doc", library="fastapi",
                    version="0.115.2", title="FastAPI authentication",
                    content="Use Depends() for authentication and security.",
                    source="https://x", tags=["auth"], now="2026-01-01T00:00:00+00:00")
    repo.write_page(slug="libs/sqlalchemy-session", kind="library_doc", library="sqlalchemy",
                    version="2.0.0", title="SQLAlchemy session scope",
                    content="Use a session per request. Avoid sharing sessions.",
                    source="https://y", tags=["db"], now="2026-01-01T00:00:00+00:00")
    return repo


def test_search_returns_relevant_first(tmp_path):
    repo = _seed(tmp_path)
    results = repo.search("authentication")
    assert results
    assert results[0]["slug"] == "libs/fastapi-auth"
    assert "snippet" in results[0]
    assert results[0]["library"] == "fastapi"


def test_search_filters_by_library(tmp_path):
    repo = _seed(tmp_path)
    results = repo.search("session", library="sqlalchemy")
    assert [r["slug"] for r in results] == ["libs/sqlalchemy-session"]


def test_search_handles_punctuation_without_error(tmp_path):
    repo = _seed(tmp_path)
    # must not raise an FTS5 syntax error
    assert repo.search("auth() & security:") is not None
