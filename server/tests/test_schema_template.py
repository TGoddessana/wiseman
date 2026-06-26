from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "schema.md"


def test_schema_template_mentions_tools_and_ops():
    text = TEMPLATE.read_text(encoding="utf-8")
    for tool in ["ask_wiseman", "wiki_index", "get_page", "write_page", "lint"]:
        assert tool in text, f"schema.md must document tool {tool}"
    for op in ["query", "ingest", "lint"]:
        assert op in text.lower()
