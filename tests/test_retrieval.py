import json
from pathlib import Path

import pytest

from shd.chunk_code import chunk_code_dir
from shd.chunk_docs import chunk_docs_dir
from shd.embeddings import FakeEmbedder
from shd.index import DocIndex

FIXTURES = Path(__file__).parent.parent / "fixtures"
STALE = [p.name for p in sorted(FIXTURES.iterdir())
         if p.is_dir() and json.loads((p / "expected.json").read_text())["stale"]]


def recall_at_3(scenario: str, embedder, tmp_path) -> None:
    root = FIXTURES / scenario
    expected = json.loads((root / "expected.json").read_text())["stale"]
    index = DocIndex(tmp_path / ".chroma", embedder)
    index.index_docs(chunk_docs_dir(root / "docs"))
    related = {i for c in chunk_code_dir(root / "src") for i in index.find_related_docs(c, k=3)}
    assert set(expected) <= related


def search_beats_install(embedder, tmp_path) -> None:
    index = DocIndex(tmp_path / ".chroma", embedder)
    index.index_docs(chunk_docs_dir(FIXTURES / "01_wrong_path_missing_param" / "docs"))
    index.index_docs(chunk_docs_dir(FIXTURES / "07_unrelated_docs" / "docs"))
    (code,) = chunk_code_dir(FIXTURES / "01_wrong_path_missing_param" / "src")
    assert index.find_related_docs(code, k=1) == ["docs/api.md::Search endpoint"]


@pytest.mark.parametrize("scenario", STALE)
def test_recall_at_3_fake(scenario, tmp_path):
    recall_at_3(scenario, FakeEmbedder(), tmp_path)


def test_related_doc_ranks_first_fake(tmp_path):
    search_beats_install(FakeEmbedder(), tmp_path)


def test_fake_embedder_is_deterministic_and_normalized():
    a, b = FakeEmbedder().embed(["POST /v2/search limit", "POST /v2/search limit"])
    assert a == b and abs(sum(x * x for x in a) - 1) < 1e-9


def test_reindex_is_idempotent(tmp_path):
    index = DocIndex(tmp_path / ".chroma", FakeEmbedder())
    chunks = chunk_docs_dir(FIXTURES / "04_deleted_function" / "docs")
    index.index_docs(chunks)
    index.index_docs(chunks)
    assert index.collection.count() == len(chunks)


def test_empty_index_returns_nothing(tmp_path):
    index = DocIndex(tmp_path / ".chroma", FakeEmbedder())
    (code,) = chunk_code_dir(FIXTURES / "01_wrong_path_missing_param" / "src")
    assert index.find_related_docs(code) == []


@pytest.mark.live
@pytest.mark.parametrize("scenario", STALE)
def test_recall_at_3_live(scenario, tmp_path, live_embedder):
    recall_at_3(scenario, live_embedder, tmp_path)


@pytest.mark.live
def test_related_doc_ranks_first_live(tmp_path, live_embedder):
    search_beats_install(live_embedder, tmp_path)
