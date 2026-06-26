from wiseman_mcp import tools
from wiseman_mcp.repository import WikiRepo


def test_ask_on_empty_wiki_guides_user(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    out = tools.ask_wiseman(repo, "anything")
    assert out["status"] == "empty"
    assert "summon-wiseman" in out["message"]


def test_ask_returns_results(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    repo.write_page(slug="libs/fastapi-auth", kind="library_doc", library="fastapi",
                    version="0.115.2", title="FastAPI authentication",
                    content="Use Depends() for authentication.", source="https://x",
                    now="2026-01-01T00:00:00+00:00")
    out = tools.ask_wiseman(repo, "authentication")
    assert out["status"] == "ok"
    assert out["results"][0]["slug"] == "libs/fastapi-auth"


def test_get_page_not_found(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    out = tools.get_page(repo, "missing")
    assert out["status"] == "not_found"


def test_write_page_via_tool(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    out = tools.write_page(repo, slug="clean/dry", kind="clean_code",
                           title="DRY", content="Do not repeat yourself.")
    assert out["status"] == "ok"
    assert out["page"]["slug"] == "clean/dry"


def test_lint_tool_on_empty(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    assert tools.lint(repo)["status"] == "empty"
