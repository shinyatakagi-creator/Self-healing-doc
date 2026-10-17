import json
from pathlib import Path

import pytest

from shd.chunk_code import chunk_code_dir, code_identifiers_dir
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

REFERENCE_STALE = {"01_wrong_path_missing_param", "02_removed_param", "04_deleted_function", "12_non_function_symbols", "13_naming_terms"}


@pytest.mark.parametrize("name", SCENARIOS)
def test_reference_check_per_fixture(name):
    code, docs, expected = load(name)
    ids = code_identifiers_dir(FIXTURES / name / "src")
    flagged = {d["id"] for d in docs if check_references(d, code, ids)}
    assert flagged == (set(expected["stale"]) if name in REFERENCE_STALE else set())


def test_reference_check_reasons():
    code, docs, _ = load("04_deleted_function")
    (delete,) = [d for d in docs if d["title"] == "Delete item"]
    assert check_references(delete, code, code_identifiers_dir(FIXTURES / "04_deleted_function" / "src")) == ["route /v1/items/{item_id}", "name delete_item"]


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
    from shd.detect import CallBudget, CallBudgetExceeded

    code, docs, _ = load("03_changed_default")
    checker = LLMDriftChecker(CallBudget(0).wrap(stub(GOOD)))
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


# --- reference check rules ---

def fake_doc(content, **refs):
    from shd.chunk_docs import extract_refs
    return {"id": "d.md::S", "content": content, "refs": extract_refs(content)}


def refs_missing(content):
    code, _, _ = load("01_wrong_path_missing_param")  # route /v2/search, params query/limit/include_archived
    return check_references(fake_doc(content), code)


def test_ref_bare_path_without_shared_segment_is_not_a_route():
    assert refs_missing("Logs go to `/var/log/app.log`; see `/tmp/cache`.") == []


def test_ref_bare_path_sharing_a_segment_is_a_route():
    assert refs_missing("Call `/v1/search`.") == ["route /v1/search"]


def test_ref_file_path_sharing_a_segment_is_not_a_route():
    assert refs_missing("Writes `/exports/search.csv`.") == []


def test_ref_method_prefixed_path_is_always_a_route():
    assert refs_missing("`DELETE /whatever/else`") == ["route /whatever/else"]


def test_ref_snake_case_unanchored_is_ignored():
    assert refs_missing("Set `max_workers` and `retry_count` in the config.") == []


def test_ref_snake_case_anchored_by_call_param_list_or_real_ref():
    assert refs_missing("Use `old_helper(x)`.") == ["name old_helper"]
    assert refs_missing("Params: `old_param` (required)") == ["name old_param"]
    assert refs_missing("`POST /v2/search` takes `old_param`.") == ["name old_param"]
    assert refs_missing("Takes `limit` and `old_param`.") == ["name old_param"]


def test_ref_fenced_shell_block_is_ignored():
    assert refs_missing("Run:\n\n```bash\n`DELETE /x` `old_helper(1)`\n```\n") == []


# --- verifier (plumbing) ---

from shd.detect import CallBudget, FakeVerifier, LLMVerifier


def test_verifier_yes_no_and_garbage():
    assert LLMVerifier(lambda p: "Yes, they conflict.").verify("a", "b")
    assert not LLMVerifier(lambda p: "no").verify("a", "b")
    assert not LLMVerifier(lambda p: "I am not sure").verify("a", "b")


def test_verifier_prompt_has_only_claim_and_fact():
    seen = []
    LLMVerifier(lambda p: seen.append(p) or "no").verify("default 10", "limit defaults to 20")
    assert "default 10" in seen[0] and "limit defaults to 20" in seen[0] and "directly contradict" in seen[0]


def test_verifier_api_failure_is_drift_error():
    def boom(p):
        raise RuntimeError("down")

    with pytest.raises(DriftError, match="down"):
        LLMVerifier(boom).verify("a", "b")


def test_verifier_rejection_discards_flag(tmp_path):
    code, docs, _ = load("03_changed_default")
    index = DocIndex(tmp_path / "c", FakeEmbedder())
    (r,) = check_drift(code, docs, index, Canned(claim_verdict()), verifier=FakeVerifier(False))
    assert not r.is_stale and r.verifier_rejected and not r.filtered


def test_verifier_acceptance_keeps_flag_and_filtered_flags_skip_verifier(tmp_path):
    code, docs, _ = load("03_changed_default")
    ok = check_drift(code, docs, DocIndex(tmp_path / "a", FakeEmbedder()), Canned(claim_verdict()), verifier=FakeVerifier(True))
    assert ok[0].is_stale and not ok[0].verifier_rejected

    class Boom:
        def verify(self, *a):
            raise AssertionError("verifier must not run for a filtered flag")

    (r,) = check_drift(code, docs, DocIndex(tmp_path / "b", FakeEmbedder()),
                       Canned(claim_verdict(doc_claim="nope")), verifier=Boom())
    assert r.filtered and not r.verifier_rejected


def test_verifier_error_is_recorded_not_raised(tmp_path):
    code, docs, _ = load("03_changed_default")

    class Down:
        def verify(self, *a):
            raise DriftError("down")

    (r,) = check_drift(code, docs, DocIndex(tmp_path / "c", FakeEmbedder()), Canned(claim_verdict()), verifier=Down())
    assert r.error and not r.is_stale


def test_ref_non_function_symbols_exist_in_identifier_index():
    code, _, _ = load("12_non_function_symbols")
    ids = code_identifiers_dir(FIXTURES / "12_non_function_symbols" / "src")
    doc = fake_doc("`POST /v1/batches` runs `process_batch(items)`; see `max_batch_size`, `retry_limit`, `cache_ttl`, `flush_buffer()`.")
    assert check_references(doc, code, ids) == ["name flush_buffer"]
    assert "name max_batch_size" in check_references(doc, code)  # without identifiers: the old behavior


# --- pairing: mutual top-k ---

from shd.detect import candidate_pairs


def synthetic_code(n):
    return [{"id": f"m.py::f{i}", "name": f"f{i}", "routes": [], "params": [], "docstring": f"handles topic{i} items",
             "source": f"def f{i}(): ..."} for i in range(n)]


def test_pairing_caps_pairs_per_doc_section(tmp_path):
    code = synthetic_code(8)
    doc = {"id": "d.md::Topics", "content": "handles items for topics", "refs": {}}
    index = DocIndex(tmp_path / "c", FakeEmbedder())
    assert len(candidate_pairs(code, [doc], index, k=3, k_rev=None)) == 8  # old rule: every chunk picks the one doc
    assert len(candidate_pairs(code, [doc], DocIndex(tmp_path / "d", FakeEmbedder()), k=3, k_rev=5)) == 5


def test_pairing_keeps_fixture_10_pair(tmp_path):
    code, docs, _ = load("10_prose_claim")
    pairs = candidate_pairs(code, docs, DocIndex(tmp_path / "c", FakeEmbedder()))
    assert ("src/api.py::search_notes", "docs/notes.md::Searching notes") in {(c["id"], d["id"]) for c, d in pairs}


def test_pairing_skips_reference_flagged_docs(tmp_path):
    code, docs, _ = load("04_deleted_function")
    pairs = candidate_pairs(code, docs, DocIndex(tmp_path / "c", FakeEmbedder()), skip={"docs/api.md::Delete item"})
    assert {d["id"] for _, d in pairs} == {"docs/api.md::Health check"}


# --- context reaches both prompts ---

def test_drift_prompt_and_verifier_prompt_carry_module_context():
    seen = []
    chunk = {"id": "a.py::f", "source": "def f(): ...", "context": "MAX_BATCH = 100"}
    LLMDriftChecker(lambda p: seen.append(p) or GOOD).check(chunk, DOC)
    assert "MODULE CONTEXT" in seen[0] and "MAX_BATCH = 100" in seen[0]
    LLMVerifier(lambda p: seen.append(p) or "no").verify("claim", "fact", "MAX_BATCH = 100")
    assert "MAX_BATCH = 100" in seen[1] and "Does the first directly contradict the second" in seen[1]


def test_prompts_omit_context_block_when_empty():
    seen = []
    LLMDriftChecker(lambda p: seen.append(p) or GOOD).check({"id": "a.py::f", "source": "x", "context": ""}, DOC)
    LLMVerifier(lambda p: seen.append(p) or "no").verify("claim", "fact")
    assert "MODULE CONTEXT" not in seen[0] and "Module context" not in seen[1]


def test_check_drift_passes_context_to_verifier(tmp_path):
    code, docs, _ = load("12_non_function_symbols")
    got = []

    class Spy:
        def verify(self, claim, fact, context=""):
            got.append(context)
            return True

    check_drift(code, docs, DocIndex(tmp_path / "c", FakeEmbedder()), Canned(claim_verdict(doc_claim="`POST /v1/batches` runs")), verifier=Spy(),
                identifiers=code_identifiers_dir(FIXTURES / "12_non_function_symbols" / "src"))
    assert got and "max_batch_size = 100" in got[0] and "Settings: retry_limit: int = 3" in got[0]


# --- Stage 6: confidence, verifier rule, tiers ---

from shd.detect import names_code_element, tier_doc_ids
from shd.report import doc_statuses


def test_empty_confidence_is_low_when_not_stale():
    v = parse_verdict('{"is_stale": false, "reason": "", "suggested_fix": "", "confidence": ""}')
    assert v.confidence == "low" and not v.is_stale


def test_empty_confidence_still_invalid_when_stale():
    with pytest.raises(Exception):
        parse_verdict('{"is_stale": true, "reason": "r", "suggested_fix": "f", "confidence": ""}')


def test_empty_confidence_does_not_cost_a_retry():
    complete = stub('{"is_stale": false, "reason": "", "suggested_fix": "", "confidence": ""}')
    assert LLMDriftChecker(complete).check(CODE, DOC).confidence == "low"
    assert len(complete.calls) == 1


def test_prompts_describe_new_rules():
    seen = []
    LLMVerifier(lambda p: seen.append(p) or "no").verify("claim", "fact")
    LLMDriftChecker(lambda p: seen.append(p) or GOOD).check(CODE, DOC)
    assert "NOT a contradiction" in seen[0] and "says 10 and the code default is 20" in seen[0]
    assert 'empty confidence is read as "low"' in seen[1]


@pytest.mark.parametrize("claim,expected", [
    ("`limit` (optional, default 10)", True),
    ("`POST /v1/search` creates", True),
    ("POST to /v1/search with text", True),
    ("Call `old_helper(x)` first", True),
    ("By default the search returns at most ten results", False),
    ("Large result sets are split into pages and/or truncated", False),
    ("", False),
])
def test_names_code_element(claim, expected):
    assert names_code_element(claim) is expected


def tiered(tmp_path, claim):
    code, docs, _ = load("03_changed_default")
    (r,) = check_drift(code, docs, DocIndex(tmp_path / "c", FakeEmbedder()),
                       Canned(claim_verdict(doc_claim=claim)))
    return r


def test_llm_flag_naming_code_element_is_stale_tier(tmp_path):
    r = tiered(tmp_path, "`limit` (optional, default 10)")
    assert r.is_stale and r.tier == "stale"


def test_llm_flag_with_prose_claim_is_review_tier(tmp_path):
    r = tiered(tmp_path, "default 10")
    assert r.is_stale and r.tier == "review"


def test_reference_flags_are_stale_tier_and_unflagged_have_no_tier(tmp_path):
    code, docs, _ = load("01_wrong_path_missing_param")
    res = check_drift(code, docs, DocIndex(tmp_path / "c", FakeEmbedder()), FakeDriftChecker())
    assert [r.tier for r in res] == ["stale"]
    code, docs, _ = load("05_clean_match")
    (ok,) = check_drift(code, docs, DocIndex(tmp_path / "d", FakeEmbedder()), FakeDriftChecker())
    assert ok.tier is None


def test_tier_doc_ids_and_report_status():
    from shd.detect import DriftResult

    res = [DriftResult(code_id="c", doc_id="a", detection="llm", is_stale=True, tier="review"),
           DriftResult(code_id="c", doc_id="b", detection="llm", is_stale=True, tier="stale"),
           DriftResult(code_id="c", doc_id="b", detection="llm", is_stale=True, tier="review"),
           DriftResult(code_id="c", doc_id="c", detection="llm", is_stale=False)]
    assert tier_doc_ids(res, "stale") == {"b"} and tier_doc_ids(res, "review") == {"a"}
    status = {r["doc_id"]: r["status"] for r in doc_statuses([{"id": i} for i in "abcd"], res)}
    assert status == {"a": "REVIEW", "b": "STALE", "c": "OK", "d": "OK"}


# --- naming terms and plain-prose rules ---

def test_ref_naming_terms_are_skipped_even_when_anchored():
    text = "Use `snake_case`, `camel_case` and `kebab_case` names; `POST /v2/search` takes `old_param`."
    assert refs_missing(text) == ["name old_param"]


def test_ref_naming_term_defined_in_code_is_not_special(tmp_path):
    code, _, _ = load("01_wrong_path_missing_param")
    assert check_references(fake_doc("`POST /v2/search` and `snake_case`"), code, {"snake_case"}) == []


def test_ref_plain_prose_underscore_names_are_not_references():
    assert refs_missing("`POST /v2/search` is fast. Never write old_param or other_thing in prose.") == []


def test_ref_plain_call_syntax_counts_without_backticks():
    assert refs_missing("After a search, run purge_cache() to free memory.") == ["name purge_cache"]


def test_ref_plain_call_syntax_with_naming_term_is_skipped():
    assert refs_missing("Do not call snake_case() anywhere; `POST /v2/search` stays.") == []
