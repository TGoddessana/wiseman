from wiseman_mcp.repository import WikiRepo


def test_index_summarizes_wiki(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    repo.write_page(slug="libs/fastapi-auth", kind="library_doc", library="fastapi",
                    version="0.115.2", title="A", content="x",
                    now="2026-01-01T00:00:00+00:00")
    repo.write_page(slug="conventions/errors", kind="project_convention",
                    title="B", content="y", now="2026-01-01T00:00:00+00:00")
    idx = repo.index()
    assert idx["total"] == 2
    assert idx["by_kind"]["library_doc"] == 1
    assert idx["by_kind"]["project_convention"] == 1
    assert idx["libraries"] == [{"library": "fastapi", "version": "0.115.2", "pages": 1}]
    assert [p["slug"] for p in idx["pages"]] == ["conventions/errors", "libs/fastapi-auth"]
