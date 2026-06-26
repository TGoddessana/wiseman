from wiseman_mcp.repository import WikiRepo


def test_lint_flags_orphans_and_missing_fields(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    # good library page, linked-to
    repo.write_page(slug="libs/good", kind="library_doc", library="fastapi",
                    version="1.0", title="g", content="x", source="https://x",
                    now="2026-06-01T00:00:00+00:00")
    # links to libs/good so it is not an orphan; this page itself is an orphan
    repo.write_page(slug="conventions/c", kind="project_convention", title="c",
                    content="y", links=["libs/good"],
                    now="2026-06-01T00:00:00+00:00")
    # library_doc missing source and version -> flagged, also orphan
    repo.write_page(slug="libs/bad", kind="library_doc", library="redis",
                    title="b", content="z", now="2026-06-01T00:00:00+00:00")

    report = repo.lint(stale_days=180, now="2026-06-20T00:00:00+00:00")
    assert "libs/good" not in report["orphans"]
    assert "conventions/c" in report["orphans"]
    assert "libs/bad" in report["orphans"]
    assert report["missing_source"] == ["libs/bad"]
    assert report["missing_version"] == ["libs/bad"]
    assert report["stale"] == []


def test_lint_flags_stale(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    repo.write_page(slug="old", kind="clean_code", title="o", content="x",
                    now="2025-01-01T00:00:00+00:00")
    report = repo.lint(stale_days=30, now="2026-06-20T00:00:00+00:00")
    assert report["stale"] == ["old"]
