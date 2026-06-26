from fastmcp import FastMCP

from . import tools
from .repository import WikiRepo


def build_server(db_path: str) -> FastMCP:
    repo = WikiRepo(db_path)
    mcp = FastMCP("wiseman")

    @mcp.tool
    def ask_wiseman(query: str, kind: str | None = None,
                    library: str | None = None, limit: int = 10) -> dict:
        """Consult the project's Wiseman wiki before coding. Returns ranked,
        sourced, version-pinned knowledge snippets relevant to the query."""
        return tools.ask_wiseman(repo, query, kind=kind, library=library, limit=limit)

    @mcp.tool
    def wiki_index() -> dict:
        """List what the Wiseman knows: page catalog, kinds, libraries+versions."""
        return tools.wiki_index(repo)

    @mcp.tool
    def get_page(slug: str) -> dict:
        """Fetch the full content of one wiki page by slug."""
        return tools.get_page(repo, slug)

    @mcp.tool
    def write_page(slug: str, kind: str, title: str, content: str,
                   library: str | None = None, version: str | None = None,
                   source: str | None = None, confidence: str = "medium",
                   tags: list[str] | None = None,
                   links: list[str] | None = None) -> dict:
        """File knowledge back into the wiki (the compounding loop). Use after
        researching something worth remembering. Provide source + version for
        library knowledge."""
        return tools.write_page(repo, slug=slug, kind=kind, title=title,
                                content=content, library=library, version=version,
                                source=source, confidence=confidence,
                                tags=tags, links=links)

    @mcp.tool
    def lint() -> dict:
        """Health-check the wiki: orphan pages, missing source/version, stale pages."""
        return tools.lint(repo)

    return mcp
