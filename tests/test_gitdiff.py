import git
import pytest

from shd.chunk_code import chunk_code_dir, code_identifiers_dir
from shd.chunk_docs import chunk_docs_dir
from shd.detect import FakeDriftChecker, check_drift
from shd.embeddings import FakeEmbedder
from shd.gitdiff import changed_files, diff_changes
from shd.index import DocIndex

API = '''from fastapi import FastAPI

app = FastAPI()


@app.post("/v1/search")
def search(query: str, limit: int = 10):
    """Search."""
    ...


@app.get("/v1/health")
def health():
    """Liveness."""
    return {"ok": True}
'''
DOCS = '''# API

## Search endpoint

`POST /v1/search`

Params: `query` (required), `limit` (optional, default 10)

## Health check

`GET /v1/health` returns ok.
'''


@pytest.fixture
def repo(tmp_path):
    r = git.Repo.init(tmp_path, initial_branch="main")
    r.config_writer().set_value("user", "name", "t").release()
    r.config_writer().set_value("user", "email", "t@t").release()
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "api.py").write_text(API)
    (tmp_path / "docs" / "api.md").write_text(DOCS)
    r.git.add("-A")
    r.git.commit("-m", "base")
    r.git.checkout("-b", "feature")
    return r


def commit(repo, msg="change"):
    repo.git.add("-A")
    repo.git.commit("-m", msg)


def run(repo, tmp_path):
    root = tmp_path
    code, docs = chunk_code_dir(root / "src"), chunk_docs_dir(root / "docs")
    # chunk_*_dir ids are relative to the parent of src/docs, which is the repo root here
    ch = diff_changes(root, "main", code, docs, ["src"], ["docs"])
    res = check_drift(code, docs, DocIndex(tmp_path / ".idx", FakeEmbedder()), FakeDriftChecker(),
                      identifiers=code_identifiers_dir(root / "src"),
                      only_code_ids=ch.changed_ids, reference_doc_ids=ch.trigger_doc_ids)
    return ch, res


def test_only_the_modified_function_is_rechecked(repo, tmp_path):
    (tmp_path / "src" / "api.py").write_text(API.replace("limit: int = 10", "limit: int = 20"))
    commit(repo)
    ch, res = run(repo, tmp_path)
    assert ch.changed_ids == {"src/api.py::search"} and not ch.removed_ids
    assert {r.code_id for r in res} == {"src/api.py::search"}
    assert [r.doc_id for r in res if r.is_stale] == ["docs/api.md::Search endpoint"]


def test_unchanged_branch_checks_nothing(repo, tmp_path):
    ch, res = run(repo, tmp_path)
    assert not ch.changed_ids and not ch.trigger_doc_ids and res == []


def test_deleted_function_triggers_reference_check(repo, tmp_path):
    (tmp_path / "src" / "api.py").write_text(API.split('@app.get("/v1/health")')[0])
    commit(repo)
    ch, res = run(repo, tmp_path)
    assert ch.removed_ids == {"src/api.py::health"} and not ch.changed_ids
    assert "/v1/health" in ch.removed_symbols and "docs/api.md::Health check" in ch.trigger_doc_ids
    assert [(r.detection, r.doc_id) for r in res] == [("reference", "docs/api.md::Health check")]


def test_renamed_function_triggers_reference_check(repo, tmp_path):
    (tmp_path / "src" / "api.py").write_text(API.replace("def health", "def liveness").replace("/v1/health", "/v1/live"))
    commit(repo)
    ch, res = run(repo, tmp_path)
    assert ch.removed_ids == {"src/api.py::health"} and ch.changed_ids == {"src/api.py::liveness"}
    assert any(r.detection == "reference" and r.doc_id == "docs/api.md::Health check" for r in res)


def test_removed_param_triggers_docs_that_mention_it(repo, tmp_path):
    (tmp_path / "src" / "api.py").write_text(API.replace(", limit: int = 10", ""))
    commit(repo)
    ch, _ = run(repo, tmp_path)
    assert "limit" in ch.removed_symbols and "docs/api.md::Search endpoint" in ch.trigger_doc_ids


def test_moved_function_is_not_a_removed_symbol(repo, tmp_path):
    body = API.split('@app.get("/v1/health")')
    (tmp_path / "src" / "api.py").write_text(body[0])
    (tmp_path / "src" / "more.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n\n@app.get(\"/v1/health\")" + body[1])
    commit(repo)
    ch, _ = run(repo, tmp_path)
    assert ch.removed_ids == {"src/api.py::health"} and "/v1/health" not in ch.removed_symbols


def test_changed_doc_file_is_reference_checked(repo, tmp_path):
    (tmp_path / "docs" / "api.md").write_text(DOCS.replace("`GET /v1/health` returns ok.", "`GET /v1/status` returns ok."))
    commit(repo)
    ch, res = run(repo, tmp_path)
    assert ch.trigger_doc_ids == {"docs/api.md::Search endpoint", "docs/api.md::Health check"}
    assert [(r.detection, r.doc_id) for r in res] == [("reference", "docs/api.md::Health check")]


def test_changed_files_reports_status_and_renames(repo, tmp_path):
    (tmp_path / "src" / "api.py").rename(tmp_path / "src" / "routes.py")
    (tmp_path / "docs" / "new.md").write_text("## x\n\ntext\n")
    commit(repo)
    files = changed_files(repo, "main")
    assert files["src/routes.py"] == ("R", "src/api.py") and files["docs/new.md"][0] == "A"


def test_cli_base_mode_and_budget(repo, tmp_path, monkeypatch):
    from shd.cli import main
    from shd.report import MARKER

    (tmp_path / "src" / "api.py").write_text(API.replace("limit: int = 10", "limit: int = 20"))
    commit(repo)
    monkeypatch.chdir(tmp_path)
    main(["check", "--base", "main", "--code", "src", "--docs", "docs", "--out", "r.json", "--comment-file", "c.md",
          "--max-calls", "30", "--fake"])
    text = (tmp_path / "c.md").read_text()
    assert MARKER in text and "docs/api.md::Search endpoint" in text and "1 changed code chunk(s)" in text


def test_budget_stop_returns_partial_results(repo, tmp_path):
    from shd.detect import CallBudget, LLMDriftChecker
    GOOD = '{"is_stale": false, "reason": "", "suggested_fix": "", "confidence": "low"}'
    (tmp_path / "src" / "api.py").write_text(API.replace("limit: int = 10", "limit: int = 20").replace('return {"ok": True}', 'return {"ok": False}'))
    commit(repo)
    code, docs = chunk_code_dir(tmp_path / "src"), chunk_docs_dir(tmp_path / "docs")
    ch = diff_changes(tmp_path, "main", code, docs, ["src"], ["docs"])
    from shd.detect import CallBudgetExceeded
    checker = LLMDriftChecker(CallBudget(1).wrap(lambda p: GOOD))
    with pytest.raises(CallBudgetExceeded) as e:
        check_drift(code, docs, DocIndex(tmp_path / ".idx", FakeEmbedder()), checker, only_code_ids=ch.changed_ids)
    assert len(e.value.partial) == 1 and e.value.unchecked >= 1
