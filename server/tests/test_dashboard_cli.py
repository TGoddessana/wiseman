import pytest

from wiseman_mcp.dashboard import cli


def test_cli_errors_when_db_missing(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--db", str(tmp_path / "nope.db")])
    assert exc.value.code != 0
