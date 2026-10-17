import json
import os
import re
from typing import Callable, Literal, Protocol

from pydantic import BaseModel, ValidationError

from shd.index import DocIndex

PROMPT = """You check whether documentation accurately describes code.

CODE ({code_id}):
{code}

DOCUMENTATION SECTION ({doc_id}):
{doc}

Flag the documentation as stale ONLY for factual mismatches with the code: wrong or missing route paths,
parameters that were added, removed or renamed, changed default values, names that no longer exist,
or removed behavior. Do NOT flag wording, style, ordering or level of detail. If the documentation
describes the same behavior in different words, it is not stale. Omitting minor detail is not a mismatch.

Respond with JSON only:
{{"is_stale": true|false, "reason": "...", "suggested_fix": "...", "confidence": "high"|"medium"|"low"}}
Use empty strings for reason and suggested_fix when is_stale is false."""

DEFAULT_MODELS = {"openai": "gpt-4o", "anthropic": "claude-sonnet-5-5", "gemini": "gemini-2.5-flash"}


class Verdict(BaseModel):
    is_stale: bool
    reason: str
    suggested_fix: str
    confidence: Literal["high", "medium", "low"]


class DriftResult(BaseModel):
    code_id: str | None
    doc_id: str
    detection: Literal["reference", "llm"]
    is_stale: bool
    reason: str = ""
    suggested_fix: str = ""
    confidence: str = ""
    error: str | None = None


class DriftError(Exception):
    pass


class DriftChecker(Protocol):
    def check(self, code_chunk: dict, doc_chunk: dict) -> Verdict: ...


def parse_verdict(text: str) -> Verdict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return Verdict.model_validate_json(text)


class LLMDriftChecker:
    """`complete` takes a prompt and returns the model's raw text."""

    def __init__(self, complete: Callable[[str], str]):
        self.complete = complete

    def check(self, code_chunk: dict, doc_chunk: dict) -> Verdict:
        prompt = PROMPT.format(code_id=code_chunk["id"], code=code_chunk["source"],
                               doc_id=doc_chunk["id"], doc=doc_chunk["content"])
        last = ""
        for attempt in range(2):  # retry once on malformed output
            try:
                text = self.complete(prompt if attempt == 0 else prompt + "\n\nYour last reply was not valid JSON in the required shape. Reply with the JSON object only.")
            except Exception as e:  # API/network failure must not crash the run
                raise DriftError(f"LLM call failed: {e}") from e
            try:
                return parse_verdict(text)
            except (ValidationError, json.JSONDecodeError) as e:
                last = f"{e.__class__.__name__}: {str(e)[:200]}"
        raise DriftError(f"malformed LLM output after retry: {last}")


def make_complete(provider: str | None = None) -> Callable[[str], str]:
    provider = (provider or os.getenv("LLM_PROVIDER") or "openai").lower()
    if provider not in DEFAULT_MODELS:
        raise ValueError(f"unknown LLM_PROVIDER: {provider}")
    model = os.getenv("LLM_MODEL") or DEFAULT_MODELS[provider]
    if provider == "openai":
        from openai import OpenAI

        client = OpenAI()
        return lambda p: client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": p}],
            response_format={"type": "json_object"}, temperature=0,
        ).choices[0].message.content
    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic()
        return lambda p: client.messages.create(
            model=model, max_tokens=1024, messages=[{"role": "user", "content": p}],
        ).content[0].text
    if provider == "gemini":
        from google import genai

        client = genai.Client()
        return lambda p: client.models.generate_content(
            model=model, contents=p, config={"response_mime_type": "application/json"},
        ).text


class FakeDriftChecker:
    """Rule-based stand-in for tests (plumbing only, not a measure of accuracy)."""

    def check(self, code_chunk: dict, doc_chunk: dict) -> Verdict:
        text = doc_chunk["content"]
        code_paths = {r["path"] for r in code_chunk["routes"]}
        params = {p["name"]: p["default"] for p in code_chunk["params"]}
        refs = doc_chunk["refs"]
        if not (set(refs["paths"]) & code_paths or set(refs["names"]) & (set(params) | {code_chunk["name"]})):
            return Verdict(is_stale=False, reason="", suggested_fix="", confidence="high")
        problems = []
        for path in refs["paths"]:
            if code_paths and path not in code_paths:
                problems.append(f"doc path {path} not in code routes {sorted(code_paths)}")
        for name, default in re.findall(r"`(\w+)` \([^)]*default (\w+)\)", text):
            if name in params and params[name] is not None and params[name].lower() != default.lower():
                problems.append(f"default of {name} is {params[name]}, doc says {default}")
        for name in params:
            if name not in text:
                problems.append(f"param {name} is not documented")
        if problems:
            return Verdict(is_stale=True, reason="; ".join(problems), suggested_fix="update the section to match the code", confidence="high")
        return Verdict(is_stale=False, reason="", suggested_fix="", confidence="high")


def code_symbols(code_chunks: list[dict]) -> tuple[set[str], set[str]]:
    paths = {r["path"] for c in code_chunks for r in c["routes"]}
    names = {c["name"].split(".")[-1] for c in code_chunks} | {p["name"] for c in code_chunks for p in c["params"]}
    return paths, names


def check_references(doc_chunk: dict, code_chunks: list[dict]) -> list[str]:
    """Doc refs that no longer exist in the code. No LLM involved.
    ponytail: bare `/x` paths count as routes (a doc mentioning `/var/log` would be flagged),
    and only names with an underscore are checked so words like `limit` or `true` never are.
    Config keys and file paths are not checked."""
    paths, names = code_symbols(code_chunks)
    missing = []
    if paths:
        missing += [f"route {p}" for p in doc_chunk["refs"]["paths"] if p.startswith("/") and p not in paths]
    missing += [f"name {n}" for n in doc_chunk["refs"]["names"] if "_" in n and n not in names]
    return missing


def check_drift(code_chunks: list[dict], doc_chunks: list[dict], index: DocIndex,
                checker: DriftChecker, k: int = 3) -> list[DriftResult]:
    results: list[DriftResult] = []
    flagged: set[str] = set()
    for doc in doc_chunks:
        if missing := check_references(doc, code_chunks):
            flagged.add(doc["id"])
            results.append(DriftResult(
                code_id=None, doc_id=doc["id"], detection="reference", is_stale=True,
                reason="doc references no longer in code: " + ", ".join(missing),
                suggested_fix="remove or update these references", confidence="high",
            ))

    index.index_docs(doc_chunks)
    docs = {d["id"]: d for d in doc_chunks}
    for code in code_chunks:
        for doc_id in index.find_related_docs(code, k):
            if doc_id in flagged:  # already known stale, skip the LLM call
                continue
            try:
                v = checker.check(code, docs[doc_id])
                results.append(DriftResult(code_id=code["id"], doc_id=doc_id, detection="llm", **v.model_dump()))
            except DriftError as e:
                results.append(DriftResult(code_id=code["id"], doc_id=doc_id, detection="llm", is_stale=False, error=str(e)))
    return results


def stale_doc_ids(results: list[DriftResult]) -> set[str]:
    return {r.doc_id for r in results if r.is_stale}
