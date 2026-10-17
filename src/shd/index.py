from pathlib import Path

import chromadb
from chromadb.config import Settings

from shd.embeddings import Embedder


def code_query(chunk: dict) -> str:
    """Text we embed for a code chunk: what a doc section about it would mention."""
    routes = " ".join(f"{r['method']} {r['path']}" for r in chunk["routes"])
    params = " ".join(p["name"] for p in chunk["params"])
    return f"{routes} {chunk['name']} {params} {chunk['docstring']}".strip()


class DocIndex:
    def __init__(self, path: str | Path, embedder: Embedder):
        client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
        self.collection = client.get_or_create_collection("docs", metadata={"hnsw:space": "cosine"})
        self.code = client.get_or_create_collection("code", metadata={"hnsw:space": "cosine"})
        self.embedder = embedder

    def index_docs(self, doc_chunks: list[dict]) -> None:
        if not doc_chunks:
            return
        self.collection.upsert(
            ids=[c["id"] for c in doc_chunks],
            embeddings=self.embedder.embed([c["content"] for c in doc_chunks]),
            documents=[c["content"] for c in doc_chunks],
        )

    def find_related_docs(self, code_chunk: dict, k: int = 3) -> list[str]:
        n = min(k, self.collection.count())
        if n == 0:
            return []
        result = self.collection.query(query_embeddings=self.embedder.embed([code_query(code_chunk)]), n_results=n)
        return result["ids"][0]

    def index_code(self, code_chunks: list[dict]) -> None:
        if not code_chunks:
            return
        self.code.upsert(
            ids=[c["id"] for c in code_chunks],
            embeddings=self.embedder.embed([code_query(c) for c in code_chunks]),
            documents=[c["source"] for c in code_chunks],
        )

    def find_related_code(self, doc_chunk: dict, k: int = 5) -> list[str]:
        n = min(k, self.code.count())
        if n == 0:
            return []
        result = self.code.query(query_embeddings=self.embedder.embed([doc_chunk["content"]]), n_results=n)
        return result["ids"][0]
