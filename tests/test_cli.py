import json
from pathlib import Path

from shd.cli import main

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_cli_fake_writes_report_and_prints_status(tmp_path, capsys):
    out = tmp_path / "r.json"
    main(["check", "--fixture", str(FIXTURES / "03_changed_default"), "--out", str(out), "--fake"])
    text = capsys.readouterr().out
    assert "STALE  docs/api.md::Search endpoint" in text and "fix:" in text
    assert json.loads(out.read_text())[0]["doc_id"] == "docs/api.md::Search endpoint"


def test_cli_ok_section(tmp_path, capsys):
    main(["check", "--fixture", str(FIXTURES / "05_clean_match"), "--out", str(tmp_path / "r.json"), "--fake"])
    assert "OK     docs/api.md::Search endpoint" in capsys.readouterr().out
