import json
from pathlib import Path

import pytest

from shd.chunk_code import chunk_code, chunk_code_dir
from shd.chunk_docs import chunk_docs, chunk_docs_dir, extract_refs

FIXTURES = Path(__file__).parent.parent / "fixtures"
SCENARIOS = sorted(p.name for p in FIXTURES.iterdir() if p.is_dir())

# scenario -> (code chunk id, route, {param: default})
CODE_TRUTH = {
    "01_wrong_path_missing_param": ("src/api.py::search", ("POST", "/v2/search"),
                                    {"query": None, "limit": "10", "include_archived": "False"}),
    "02_removed_param": ("src/api.py::search", ("POST", "/v1/search"), {"query": None, "limit": "10"}),
    "03_changed_default": ("src/api.py::search", ("POST", "/v1/search"), {"query": None, "limit": "20"}),
    "04_deleted_function": ("src/api.py::health", ("GET", "/health"), {}),
    "05_clean_match": ("src/api.py::search", ("POST", "/v2/search"),
                       {"query": None, "limit": "10", "include_archived": "False"}),
    "06_clean_reworded": ("src/api.py::search", ("POST", "/v2/search"),
                          {"query": None, "limit": "10", "include_archived": "False"}),
    "07_unrelated_docs": ("src/api.py::search", ("POST", "/v2/search"), {"query": None, "limit": "10"}),
    "08_large_corpus": ("src/api.py::search", ("POST", "/v2/search"), {"query": None, "limit": "20"}),
    "09_orders_corpus": [
        ("src/api.py::list_orders", ("GET", "/v1/orders"), {"status": "'open'", "page_size": "25"}),
        ("src/api.py::create_order", ("POST", "/v1/orders"), {"customer_id": None, "items": None}),
        ("src/api.py::cancel_order", ("DELETE", "/v1/orders/{order_id}"), {"order_id": None, "reason": "''"}),
    ],
    "11_stray_symbols": ("src/api.py::list_reports", ("GET", "/v1/reports"), {"owner": None, "page_size": "25"}),
    "12_non_function_symbols": ("src/api.py::process_batch", ("POST", "/v1/batches"), {"items": None}),
    "13_naming_terms": ("src/api.py::run_search", ("POST", "/v1/search"), {"query": None, "limit": "10"}),
    "10_prose_claim": ("src/api.py::search_notes", ("GET", "/v1/notes/search"), {"text": None, "limit": "20"}),
}


def test_every_fixture_has_truth():
    assert set(SCENARIOS) == set(CODE_TRUTH)


@pytest.mark.parametrize("name", SCENARIOS)
def test_fixture_code_chunks(name):
    truth = CODE_TRUTH[name]
    truth = truth if isinstance(truth, list) else [truth]
    chunks = {c["id"]: c for c in chunk_code_dir(FIXTURES / name / "src")}
    assert list(chunks) == [t[0] for t in truth]
    for chunk_id, route, params in truth:
        c = chunks[chunk_id]
        assert (c["routes"][0]["method"], c["routes"][0]["path"]) == route
        assert {p["name"]: p["default"] for p in c["params"]} == params


@pytest.mark.parametrize("name", SCENARIOS)
def test_fixture_doc_ids_match_expected(name):
    expected = json.loads((FIXTURES / name / "expected.json").read_text())
    ids = {c["id"] for c in chunk_docs_dir(FIXTURES / name / "docs")}
    assert ids == set(expected["stale"]) | set(expected["not_stale"])


def test_doc_refs_wrong_path_fixture():
    (c,) = chunk_docs_dir(FIXTURES / "01_wrong_path_missing_param" / "docs")
    assert c["refs"]["paths"] == ["/v1/search"]
    assert {"query", "limit"} <= set(c["refs"]["names"])


def test_doc_refs_kinds():
    refs = extract_refs("Set `API_URL` and `db.pool_size`, edit `src/a.py`, call `GET /x/{id}` or `run(a)`.")
    assert refs == {"paths": ["/x/{id}", "src/a.py"], "routes": ["/x/{id}"], "names": ["run"],
                    "calls": ["run"], "config_keys": ["API_URL", "db.pool_size"]}


def test_doc_refs_skip_shell_and_config_fences():
    text = "Use `real_name`.\n\n```bash\n`GET /x` and `fake_name`\n```\n\n```yaml\nkey: `other_name`\n```\n"
    assert extract_refs(text)["names"] == ["real_name"]
    assert extract_refs(text)["routes"] == []


def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_code_no_docstring(tmp_path):
    p = write(tmp_path, "m.py", "def f(a, b=2):\n    return a\n")
    (c,) = chunk_code(p, tmp_path)
    assert c["id"] == "m.py::f" and c["docstring"] == ""


def test_code_nested_and_async(tmp_path):
    p = write(tmp_path, "m.py", (
        "def outer():\n    def inner(x=1):\n        pass\n\n"
        "async def go(*args, k=3, **kw):\n    pass\n\n"
        "class C:\n    def meth(self, z): ...\n"
    ))
    chunks = {c["id"]: c for c in chunk_code(p, tmp_path)}
    assert set(chunks) == {"m.py::outer", "m.py::outer.inner", "m.py::go", "m.py::C.meth"}
    assert chunks["m.py::go"]["is_async"] and not chunks["m.py::outer"]["is_async"]
    assert {q["name"]: q["default"] for q in chunks["m.py::go"]["params"]} == {"args": None, "k": "3", "kw": None}
    assert [q["name"] for q in chunks["m.py::C.meth"]["params"]] == ["z"]


def test_code_async_route(tmp_path):
    p = write(tmp_path, "m.py", '@router.delete("/items/{id}", status_code=204)\nasync def rm(id: int): ...\n')
    (c,) = chunk_code(p, tmp_path)
    assert c["routes"] == [{"method": "DELETE", "path": "/items/{id}"}]


def test_docs_no_headings(tmp_path):
    p = write(tmp_path, "notes.md", "Just text with `foo`.\n")
    (c,) = chunk_docs(p, tmp_path)
    assert c["id"] == "notes.md::(preamble)" and c["refs"]["names"] == ["foo"]


def test_docs_skips_empty_and_ignores_fenced_hashes(tmp_path):
    p = write(tmp_path, "d.md", "# Top\n\n## A\n\n```bash\n# not a heading\n```\n\n## B\n\n## C\n\ntext\n")
    assert [c["id"] for c in chunk_docs(p, tmp_path)] == ["d.md::A", "d.md::C"]


def test_code_identifiers_cover_non_function_symbols(tmp_path):
    from shd.chunk_code import code_identifiers

    p = write(tmp_path, "m.py", (
        "import os.path as osp\nfrom x import thing\n\n"
        "limit_total = 5\nclass Box:\n    size: int = 1\n    label = 'a'\n\n"
        "    def __init__(self, width):\n        self.width = width\n\n"
        "def f(a, *rest, flag=False, **kw):\n    return g(retries=3)\n"
    ))
    assert {"limit_total", "Box", "size", "label", "width", "f", "a", "rest", "flag", "kw", "retries", "osp", "thing"} <= code_identifiers(p)


def test_code_identifiers_do_not_include_plain_loads(tmp_path):
    from shd.chunk_code import code_identifiers

    p = write(tmp_path, "m.py", "def f():\n    return undefined_name + other.attr\n")
    assert {"undefined_name", "attr", "other"}.isdisjoint(code_identifiers(p))


# --- module context ---

def test_module_context_contents_and_exclusion(tmp_path):
    p = write(tmp_path, "m.py", (
        "import os\n\nMAX_ITEMS = 100\nname: str = 'x'\n\n"
        "class Box:\n    size: int = 1\n    label = 'a'\n\n    def grow(self, by: int = 2) -> int:\n        return by\n\n"
        "def target(a):\n    return a\n\n"
        "async def other(b, *, flag=False) -> None:\n    secret_body_text = 1\n"
    ))
    chunks = {c["id"]: c for c in chunk_code(p, tmp_path)}
    ctx = chunks["m.py::target"]["context"]
    assert "MAX_ITEMS = 100" in ctx and "name: str = 'x'" in ctx
    assert "Box: size: int = 1" in ctx and "Box: label = 'a'" in ctx
    assert "class Box" in ctx and "def Box.grow(self, by: int=2) -> int" in ctx
    assert "async def other(b, *, flag=False) -> None" in ctx
    assert "def target" not in ctx and "secret_body_text" not in ctx and "return by" not in ctx


def test_module_context_is_capped(tmp_path):
    from shd.chunk_code import CONTEXT_CAP

    p = write(tmp_path, "m.py", "".join(f"def func_{i}(a, b, c): ...\n" for i in range(300)) + "VALUE = 7\n")
    ctx = chunk_code(p, tmp_path)[0]["context"]
    assert len(ctx) <= CONTEXT_CAP and "VALUE = 7" in ctx  # assignments are kept first


def test_doc_refs_plain_call_syntax_only():
    refs = extract_refs("Run purge_cache() now. Plain old_name and Foo_bar() or other(x) stay out.")
    assert refs["names"] == ["purge_cache"] and refs["calls"] == ["purge_cache"]
