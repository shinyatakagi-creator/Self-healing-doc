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


def test_cli_code_and_docs_paths(tmp_path, monkeypatch, capsys):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text('from fastapi import FastAPI\napp = FastAPI()\n\n@app.post("/v2/search")\ndef search(query, limit=20): ...\n')
    (tmp_path / "README.md").write_text("## Search\n\n`POST /v1/search` takes `query`.\n")
    monkeypatch.chdir(tmp_path)
    main(["check", "--code", "src", "--docs", "README.md", "--out", "r.json", "--fake"])
    out = capsys.readouterr().out
    assert "STALE  README.md::Search" in out and "1 sections" in out


def test_cli_requires_one_mode():
    import pytest
    with pytest.raises(SystemExit):
        main(["check", "--code", "src"])
