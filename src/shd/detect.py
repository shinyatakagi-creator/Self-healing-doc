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
{{"is_stale": true|false, "reason": "...", "suggested_fix": "...", "confidence": "high"|"medium"|"low", "doc_claim": "...", "code_fact": "..."}}
doc_claim is a verbatim quote from the documentation section that contradicts the code. code_fact is the fact in the code that it contradicts.
Use empty strings for reason, suggested_fix, doc_claim and code_fact when is_stale is false."""

DEFAULT_MODELS = {"openai": "gpt-4o", "anthropic": "claude-sonnet-5-5", "gemini": "gemini-2.5-flash"}


class Verdict(BaseModel):
    is_stale: bool
    reason: str
    suggested_fix: str
    confidence: Literal["high", "medium", "low"]
    doc_claim: str = ""
    code_fact: str = ""


class DriftResult(BaseModel):
    code_id: str | None
    doc_id: str
    detection: Literal["reference", "llm"]
    is_stale: bool
    reason: str = ""
    suggested_fix: str = ""
    confidence: str = ""
    doc_claim: str = ""
    code_fact: str = ""
    filtered: bool = False  # LLM said stale but the flag failed the claim check and was discarded
    error: str | None = None


class DriftError(Exception):
    pass


class CallBudgetExceeded(Exception):
    pass


def budgeted(complete: Callable[[str], str], max_calls: int) -> Callable[[str], str]:
    """Counts LLM calls (retries included) and aborts the run past the cap. Embedding calls are not counted."""
    def wrapper(prompt: str) -> str:
        if wrapper.calls >= max_calls:
            raise CallBudgetExceeded(f"hit --max-calls={max_calls}")
        wrapper.calls += 1
        return complete(prompt)

    wrapper.calls = 0
    return wrapper


class DriftChecker(Protocol):
    def check(self, code_chunk: dict, doc_chunk: dict) -> Verdict: ...


def _norm(text: str) -> str:
    return " ".join(text.replace("`", "").lower().split())


def claim_is_grounded(v: Verdict, doc_chunk: dict) -> bool:
    """A stale flag only counts if it quotes the doc and names the code fact it contradicts."""
    return bool(v.doc_claim.strip() and v.code_fact.strip() and _norm(v.doc_claim) in _norm(doc_chunk["content"]))


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
            except CallBudgetExceeded:
                raise
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
        problems, claims, facts = [], [], []
        for path in refs["paths"]:
            if code_paths and path not in code_paths:
                problems.append(f"doc path {path} not in code routes {sorted(code_paths)}")
                claims.append(path)
                facts.append(f"routes are {sorted(code_paths)}")
        for name, default in re.findall(r"`(\w+)` \([^)]*default (\w+)\)", text):
            if name in params and params[name] is not None and params[name].lower() != default.lower():
                problems.append(f"default of {name} is {params[name]}, doc says {default}")
                claims.append(f"default {default}")
                facts.append(f"{name} defaults to {params[name]}")
        for name in params:
            if name not in text:
                problems.append(f"param {name} is not documented")
        if problems:
            return Verdict(is_stale=True, reason="; ".join(problems), suggested_fix="update the section to match the code",
                           confidence="high", doc_claim=claims[0] if claims else "", code_fact="; ".join(facts))
        return Verdict(is_stale=False, reason="", suggested_fix="", confidence="high")


def code_symbols(code_chunks: list[dict]) -> tuple[set[str], set[str]]:
    paths = {r["path"] for c in code_chunks for r in c["routes"]}
    names = {c["name"].split(".")[-1] for c in code_chunks} | {p["name"] for c in code_chunks for p in c["params"]}
    return paths, names


PARAM_LIST = re.compile(r"(?im)^\s*(params?|parameters|arguments|args)\b|`\w+` \((?:required|optional)")
VERSION_SEGMENT = re.compile(r"v\d+")


def _segments(path: str) -> set[str]:
    return {s for s in path.strip("/").split("/") if s and not VERSION_SEGMENT.fullmatch(s)}


def _looks_like_file(path: str) -> bool:
    return bool(re.search(r"\.\w{1,5}$", path.rsplit("/", 1)[-1]))


def check_references(doc_chunk: dict, code_chunks: list[dict]) -> list[str]:
    """Doc refs that no longer exist in the code. No LLM involved.
    A path is a route if an HTTP method precedes it, or (bare) it is not a filename and shares a
    non-version segment with a real route. A snake_case name is checked only when the section is
    anchored to code: call syntax, a parameter list, or a reference that does exist in the code.
    Config keys and file paths are not checked."""
    paths, names = code_symbols(code_chunks)
    refs = doc_chunk["refs"]
    code_segments = set().union(*(_segments(p) for p in paths)) if paths else set()
    routes = [p for p in refs["paths"] if p.startswith("/") and (
        p in refs["routes"] or (not _looks_like_file(p) and _segments(p) & code_segments))]
    missing = [f"route {p}" for p in routes if p not in paths] if paths else []
    anchored = bool(refs["calls"] or PARAM_LIST.search(doc_chunk["content"])
                    or set(routes) & paths or set(refs["names"]) & names)
    if anchored:
        missing += [f"name {n}" for n in refs["names"] if "_" in n and n not in names]
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
                filtered = v.is_stale and not claim_is_grounded(v, docs[doc_id])
                results.append(DriftResult(code_id=code["id"], doc_id=doc_id, detection="llm",
                                           **{**v.model_dump(), "is_stale": v.is_stale and not filtered},
                                           filtered=filtered))
            except DriftError as e:
                results.append(DriftResult(code_id=code["id"], doc_id=doc_id, detection="llm", is_stale=False, error=str(e)))
    return results


def stale_doc_ids(results: list[DriftResult]) -> set[str]:
    return {r.doc_id for r in results if r.is_stale}
