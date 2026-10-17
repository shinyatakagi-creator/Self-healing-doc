from dataclasses import dataclass, field
from pathlib import Path

import git

from shd.chunk_code import chunk_code_text


@dataclass
class Changes:
    changed_ids: set[str] = field(default_factory=set)  # new or modified code chunks: these get LLM pairs
    removed_ids: set[str] = field(default_factory=set)  # chunk IDs that no longer exist (deleted or renamed)
    removed_symbols: set[str] = field(default_factory=set)  # names, routes, params that existed before and are gone
    trigger_doc_ids: set[str] = field(default_factory=set)  # doc sections to run the reference check on


def changed_files(repo: git.Repo, base: str) -> dict[str, tuple[str, str]]:
    """new path -> (status letter, old path). Compares the merge-base with `base` to the working tree."""
    mb = repo.git.merge_base(base, "HEAD")
    out = {}
    for line in repo.git.diff("--name-status", "-M", mb).splitlines():
        parts = line.split("\t")
        status = parts[0][0]
        old, new = (parts[1], parts[2]) if status == "R" else (parts[1], parts[1])
        out[new] = (status, old)
    return out


def file_at(repo: git.Repo, rev: str, path: str) -> str | None:
    try:
        return repo.git.show(f"{rev}:{path}")
    except git.GitCommandError:
        return None


def _under(path: str, roots: list[str]) -> bool:
    return any(r in ("", ".") or path == r or path.startswith(r.rstrip("/") + "/") for r in roots)


def _symbols(chunks: list[dict]) -> set[str]:
    return ({c["name"].split(".")[-1] for c in chunks} | {r["path"] for c in chunks for r in c["routes"]}
            | {p["name"] for c in chunks for p in c["params"]})


def diff_changes(repo_root: str | Path, base: str, code_chunks: list[dict], doc_chunks: list[dict],
                 code_roots: list[str], doc_roots: list[str]) -> Changes:
    """Compare old (merge-base) and new chunk sets for the changed code files.
    `code_chunks`/`doc_chunks` are the current chunks of the whole tree (paths relative to repo_root).
    Removed or renamed chunks, and any name/route/param that disappeared from the code, trigger the
    reference check on the doc sections that still mention them; changed doc files are checked too."""
    repo = git.Repo(repo_root)
    mb = repo.git.merge_base(base, "HEAD")
    files = changed_files(repo, base)

    old_chunks: list[dict] = []
    for new_path, (status, old_path) in files.items():
        if status == "A" or not old_path.endswith(".py") or not _under(old_path, code_roots):
            continue
        text = file_at(repo, mb, old_path)
        if text is not None:
            old_chunks += chunk_code_text(text, old_path)

    new_by_id = {c["id"]: c for c in code_chunks}
    old_by_id = {c["id"]: c for c in old_chunks}
    changed_paths = {p for p, (st, _) in files.items() if p.endswith(".py") and st != "D"}
    ch = Changes()
    ch.removed_ids = set(old_by_id) - set(new_by_id)
    ch.changed_ids = {c["id"] for c in code_chunks if c["file"] in changed_paths
                      and (c["id"] not in old_by_id or old_by_id[c["id"]]["source"] != c["source"])}
    ch.removed_symbols = _symbols(old_chunks) - _symbols(code_chunks)

    changed_docs = {p for p in files if p.endswith(".md") and _under(p, doc_roots)}
    for d in doc_chunks:
        refs = d["refs"]
        mentioned = set(refs["paths"]) | set(refs["names"]) | set(refs["calls"])
        if mentioned & ch.removed_symbols or d["file"] in changed_docs:
            ch.trigger_doc_ids.add(d["id"])
    return ch
