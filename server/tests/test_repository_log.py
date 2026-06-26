from wiseman_mcp.repository import WikiRepo


def test_recent_log_most_recent_first(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    repo.write_page(slug="a", kind="note", title="A", content="x",
                    now="2026-01-01T00:00:00+00:00")
    repo.write_page(slug="b", kind="note", title="B", content="y",
                    now="2026-01-02T00:00:00+00:00")
    log = repo.recent_log(limit=10)
    assert [e["page_slug"] for e in log] == ["b", "a"]
    assert log[0]["op"] == "write"
    assert set(log[0].keys()) == {"ts", "op", "page_slug", "note"}


def test_recent_log_respects_limit(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    for i in range(5):
        repo.write_page(slug=f"p{i}", kind="note", title=f"P{i}", content="x",
                        now="2026-01-01T00:00:00+00:00")
    assert len(repo.recent_log(limit=3)) == 3
