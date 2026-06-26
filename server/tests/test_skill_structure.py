from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "skills" / "summon-wiseman" / "SKILL.md"


def test_skill_has_frontmatter_and_pipeline():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "name: summon-wiseman" in text
    assert "description:" in text
    # pipeline checkpoints from spec §8
    for marker in ["의존성", "웹", "품질 게이트", "write_page",
                   "@.wiseman/schema.md", "--rebuild"]:
        assert marker in text, f"SKILL.md must cover: {marker}"
