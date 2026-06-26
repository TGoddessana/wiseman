from wiseman_mcp.repository import WikiRepo


def test_graph_returns_nodes_and_filtered_edges(tmp_path):
    repo = WikiRepo(str(tmp_path / "wiki.db"))
    repo.write_page(slug="a", kind="note", title="A", content="x",
                    links=["b", "ghost"], now="2026-01-01T00:00:00+00:00")
    repo.write_page(slug="b", kind="note", title="B", content="y",
                    now="2026-01-01T00:00:00+00:00")
    g = repo.graph()
    assert {n["slug"] for n in g["nodes"]} == {"a", "b"}
    node_a = next(n for n in g["nodes"] if n["slug"] == "a")
    assert node_a == {"slug": "a", "title": "A", "kind": "note",
                      "library": None, "confidence": "medium"}
    # edge to "ghost" is dropped because no page named "ghost" exists
    assert g["edges"] == [{"src": "a", "dst": "b"}]
