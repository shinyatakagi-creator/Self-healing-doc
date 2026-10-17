import json
from pathlib import Path

import pytest

from shd.chunk_code import chunk_code_dir
from shd.chunk_docs import chunk_docs_dir
from shd.detect import (DriftError, FakeDriftChecker, LLMDriftChecker, Verdict, check_drift,
                        check_references, make_complete, parse_verdict, stale_doc_ids)
from shd.embeddings import FakeEmbedder
from shd.index import DocIndex

FIXTURES = Path(__file__).parent.parent / "fixtures"
SCENARIOS = sorted(p.name for p in FIXTURES.iterdir() if p.is_dir())
GOOD = '{"is_stale": true, "reason": "path", "suggested_fix": "use v2", "confidence": "high"}'


def load(name):
    root = FIXTURES / name
    expected = json.loads((root / "expected.json").read_text())
    return chunk_code_dir(root / "src"), chunk_docs_dir(root / "docs"), expected


# --- accuracy: the deterministic docs->code reference check (no LLM) ---

REFERENCE_STALE = {"01_wrong_path_missing_param", "02_removed_param", "04_deleted_function"}


KNOWN_REFERENCE_FALSE_POSITIVES = {"09_orders_corpus", "11_stray_symbols"}  # stray paths / snake_case words in ops docs; unfixed baseline


@pytest.mark.parametrize("name", [
    pytest.param(n, marks=pytest.mark.xfail(strict=True, reason="reference check false positives, see eval/results.md"))
    if n in KNOWN_REFERENCE_FALSE_POSITIVES else n
    for n in SCENARIOS
])
def test_reference_check_per_fixture(name):
    code, docs, expected = load(name)
    flagged = {d["id"] for d in docs if check_references(d, code)}
    assert flagged == (set(expected["stale"]) if name in REFERENCE_STALE else set())


def test_reference_check_reasons():
    code, docs, _ = load("04_deleted_function")
    (delete,) = [d for d in docs if d["title"] == "Delete item"]
    assert check_references(delete, code) == ["route /v1/items/{item_id}", "name delete_item"]


def test_reference_results_are_their_own_detection_type(tmp_path):
    code, docs, _ = load("01_wrong_path_missing_param")
    results = check_drift(code, docs, DocIndex(tmp_path / "c", FakeEmbedder()), FakeDriftChecker())
    (r,) = [r for r in results if r.detection == "reference"]
    assert r.code_id is None and r.doc_id == "docs/api.md::Search endpoint" and "/v1/search" in r.reason
    assert not [r for r in results if r.detection == "llm"]  # already flagged, LLM call skipped


# --- plumbing: JSON validation, malformed output, retry-then-error (not accuracy) ---

def stub(*replies):
    calls = []

    def complete(prompt):
        calls.append(prompt)
        reply = replies[min(len(calls), len(replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply

    complete.calls = calls
    return complete


CODE = {"id": "src/a.py::f", "source": "def f(): ..."}
DOC = {"id": "docs/a.md::F", "content": "## F\ntext"}


def test_plumbing_valid_json_parses():
    assert LLMDriftChecker(stub(GOOD)).check(CODE, DOC).is_stale is True


def test_plumbing_fenced_json_is_accepted():
    assert parse_verdict(f"```json\n{GOOD}\n```").confidence == "high"


@pytest.mark.parametrize("bad", ["not json", "{}", '{"is_stale": "yes"}',
                                 GOOD.replace('"high"', '"certain"')])
def test_plumbing_invalid_output_is_rejected(bad):
    with pytest.raises(Exception):
        parse_verdict(bad)


def test_plumbing_malformed_then_valid_retries_once():
    complete = stub("oops", GOOD)
    assert LLMDriftChecker(complete).check(CODE, DOC).is_stale is True
    assert len(complete.calls) == 2


def test_plumbing_malformed_twice_raises_after_exactly_one_retry():
    complete = stub("oops", "still oops", GOOD)
    with pytest.raises(DriftError):
        LLMDriftChecker(complete).check(CODE, DOC)
    assert len(complete.calls) == 2


def test_plumbing_api_failure_becomes_drift_error():
    with pytest.raises(DriftError, match="boom"):
        LLMDriftChecker(stub(RuntimeError("boom"))).check(CODE, DOC)


def test_plumbing_error_is_recorded_and_run_continues(tmp_path):
    code, docs, _ = load("03_changed_default")
    results = check_drift(code, docs, DocIndex(tmp_path / "c", FakeEmbedder()), LLMDriftChecker(stub("bad")))
    (r,) = results
    assert r.error and not r.is_stale and r.detection == "llm" and r.doc_id in {d["id"] for d in docs}


def test_plumbing_pipeline_with_fake_checker(tmp_path):
    code, docs, expected = load("03_changed_default")
    results = check_drift(code, docs, DocIndex(tmp_path / "c", FakeEmbedder()), FakeDriftChecker())
    assert stale_doc_ids(results) == set(expected["stale"])
    assert results[0].detection == "llm" and results[0].code_id == "src/api.py::search"


def test_plumbing_unknown_provider():
    with pytest.raises(ValueError):
        make_complete("nope")


# --- live: real embedder + real LLM, one test per fixture ---

@pytest.mark.live
@pytest.mark.parametrize("name", SCENARIOS)
def test_live_fixture(name, tmp_path, live_embedder):
    code, docs, expected = load(name)
    checker = LLMDriftChecker(make_complete())
    results = check_drift(code, docs, DocIndex(tmp_path / "c", live_embedder), checker)
    assert not [r for r in results if r.error], [r.error for r in results if r.error]
    assert stale_doc_ids(results) == set(expected["stale"]), [r.model_dump() for r in results if r.is_stale]


def test_plumbing_budget_aborts_run_instead_of_recording_an_error(tmp_path):
    from shd.detect import CallBudgetExceeded, budgeted

    code, docs, _ = load("03_changed_default")
    checker = LLMDriftChecker(budgeted(stub(GOOD), 0))
    with pytest.raises(CallBudgetExceeded):
        check_drift(code, docs, DocIndex(tmp_path / "c", FakeEmbedder()), checker)


# --- claim filter (plumbing) ---

def claim_verdict(**kw):
    base = dict(is_stale=True, reason="r", suggested_fix="f", confidence="high",
                doc_claim="default 10", code_fact="limit defaults to 20")
    return Verdict(**{**base, **kw})


class Canned:
    def __init__(self, verdict):
        self.verdict = verdict

    def check(self, code_chunk, doc_chunk):
        return self.verdict


def run_filter(tmp_path, verdict):
    code, docs, _ = load("03_changed_default")
    (r,) = check_drift(code, docs, DocIndex(tmp_path / "c", FakeEmbedder()), Canned(verdict))
    return r


def test_filter_accepts_grounded_claim(tmp_path):
    r = run_filter(tmp_path, claim_verdict())
    assert r.is_stale and not r.filtered and r.doc_claim == "default 10"


def test_filter_normalizes_case_backticks_whitespace(tmp_path):
    r = run_filter(tmp_path, claim_verdict(doc_claim="`LIMIT`  (optional,\n DEFAULT 10)"))
    assert r.is_stale


@pytest.mark.parametrize("kw", [
    {"doc_claim": "default 99"},  # not in the doc
    {"doc_claim": ""},
    {"code_fact": "  "},
])
def test_filter_discards_ungrounded_claim(tmp_path, kw):
    r = run_filter(tmp_path, claim_verdict(**kw))
    assert not r.is_stale and r.filtered and r.reason == "r"


def test_filter_leaves_non_stale_alone(tmp_path):
    r = run_filter(tmp_path, claim_verdict(is_stale=False, doc_claim="", code_fact=""))
    assert not r.is_stale and not r.filtered


def test_fake_checker_claims_pass_the_filter(tmp_path):
    code, docs, _ = load("03_changed_default")
    (r,) = check_drift(code, docs, DocIndex(tmp_path / "c", FakeEmbedder()), FakeDriftChecker())
    assert r.is_stale and r.doc_claim == "default 10"
