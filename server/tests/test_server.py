import asyncio

from fastmcp import Client

from wiseman_mcp import server


def test_build_server_registers_five_tools(tmp_path):
    mcp = server.build_server(str(tmp_path / "wiki.db"))

    async def names():
        async with Client(mcp) as c:
            return {t.name for t in await c.list_tools()}

    got = asyncio.run(names())
    assert got == {"ask_wiseman", "wiki_index", "get_page", "write_page", "lint"}


def test_write_then_ask_through_mcp(tmp_path):
    mcp = server.build_server(str(tmp_path / "wiki.db"))

    async def scenario():
        async with Client(mcp) as c:
            await c.call_tool("write_page", {
                "slug": "libs/fastapi-auth", "kind": "library_doc",
                "library": "fastapi", "version": "0.115.2",
                "title": "FastAPI authentication",
                "content": "Use Depends() for authentication.",
                "source": "https://x",
            })
            res = await c.call_tool("ask_wiseman", {"query": "authentication"})
            return res.data

    data = asyncio.run(scenario())
    assert data["status"] == "ok"
    assert data["results"][0]["slug"] == "libs/fastapi-auth"


def test_cli_parses_db_and_builds(tmp_path, monkeypatch):
    from wiseman_mcp import cli
    started = {}
    monkeypatch.setattr("wiseman_mcp.server.FastMCP.run",
                        lambda self, *a, **k: started.setdefault("ran", True))
    cli.main(["--db", str(tmp_path / "wiki.db")])
    assert started.get("ran") is True
    assert (tmp_path / "wiki.db").exists()
