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
}


def test_every_fixture_has_truth():
    assert set(SCENARIOS) == set(CODE_TRUTH)


@pytest.mark.parametrize("name", SCENARIOS)
def test_fixture_code_chunks(name):
    chunk_id, route, params = CODE_TRUTH[name]
    chunks = {c["id"]: c for c in chunk_code_dir(FIXTURES / name / "src")}
    assert list(chunks) == [chunk_id]
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
    assert refs == {"paths": ["/x/{id}", "src/a.py"], "names": ["run"], "config_keys": ["API_URL", "db.pool_size"]}


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
