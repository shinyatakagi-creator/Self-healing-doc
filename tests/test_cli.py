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


def _project(root):
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text('def f(x): ...\n')
    (root / "README.md").write_text("## F\n\ntext\n")
    return [root / "src"], [root / "README.md"]


def test_paths_outside_cwd_use_git_root(tmp_path, monkeypatch):
    import git
    from shd.cli import base_dir, chunks_from_paths

    repo = tmp_path / "repo"
    repo.mkdir()
    git.Repo.init(repo)
    code, docs = _project(repo)
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    assert base_dir(code + docs) == repo.resolve()
    c, d, _ = chunks_from_paths(code, docs, base_dir(code + docs))
    assert c[0]["id"] == "src/a.py::f" and d[0]["id"] == "README.md::F"


def test_paths_outside_git_use_common_parent(tmp_path, monkeypatch):
    from shd.cli import base_dir, chunks_from_paths

    proj = tmp_path / "proj"
    proj.mkdir()
    code, docs = _project(proj)
    monkeypatch.chdir(tmp_path.parent)
    c, d, _ = chunks_from_paths(code, docs, base_dir(code + docs))
    assert c[0]["id"] == "src/a.py::f" and d[0]["id"] == "README.md::F"
