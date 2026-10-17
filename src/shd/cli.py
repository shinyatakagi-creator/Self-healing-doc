import argparse
import os
import sys
import tempfile
from pathlib import Path

import git
from dotenv import load_dotenv

from shd.chunk_code import chunk_code, chunk_code_dir, code_identifiers_dir, code_identifiers
from shd.chunk_docs import chunk_docs, chunk_docs_dir
from shd.detect import (CallBudget, CallBudgetExceeded, DriftChecker, DriftResult, FakeDriftChecker, FakeVerifier, LLMDriftChecker, LLMVerifier,
                        Verifier, check_drift, make_complete)
from shd.embeddings import Embedder, FakeEmbedder, OpenAIEmbedder
from shd.index import DocIndex
from shd.gitdiff import diff_changes
from shd.report import print_summary, render_comment, write_report


def run_check(root: Path, embedder: Embedder, checker: DriftChecker, verifier: Verifier | None = None) -> tuple[list[dict], list[DriftResult]]:
    return run_check_chunks(chunk_code_dir(root / "src"), chunk_docs_dir(root / "docs"), embedder, checker, verifier,
                            code_identifiers_dir(root / "src"))


def run_check_chunks(code: list[dict], docs: list[dict], embedder: Embedder, checker: DriftChecker,
                     verifier: Verifier | None = None, identifiers: set[str] | None = None,
                     only_code_ids: set[str] | None = None,
                     reference_doc_ids: set[str] | None = None) -> tuple[list[dict], list[DriftResult]]:
    with tempfile.TemporaryDirectory() as tmp:
        return docs, check_drift(code, docs, DocIndex(tmp, embedder), checker, verifier=verifier, identifiers=identifiers,
                                 only_code_ids=only_code_ids, reference_doc_ids=reference_doc_ids)


def base_dir(paths: list[Path]) -> Path:
    """Chunk IDs are relative to this. The git root containing the first path if it holds all of them,
    otherwise the common parent folder."""
    resolved = [p.resolve() for p in paths]
    try:
        root = Path(git.Repo(resolved[0], search_parent_directories=True).working_tree_dir).resolve()
        if all(p.is_relative_to(root) for p in resolved):
            return root
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        pass
    return Path(os.path.commonpath([p.parent for p in resolved]))


def chunks_from_paths(code_paths: list[Path], docs_paths: list[Path], root: Path) -> tuple[list[dict], list[dict], set[str]]:
    """Files or directories; chunk IDs are relative to `root`."""
    def files(paths, pattern):
        return [f for p in paths for f in (sorted(p.rglob(pattern)) if p.is_dir() else [p])]

    code = [c for f in files(code_paths, "*.py") for c in chunk_code(f.resolve(), root)]
    docs = [c for f in files(docs_paths, "*.md") for c in chunk_docs(f.resolve(), root)]
    identifiers = set().union(*(code_identifiers(f) for f in files(code_paths, "*.py")))
    return code, docs, identifiers


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="shd")
    sub = ap.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="check docs against code")
    check.add_argument("--fixture", type=Path, help="folder with src/ and docs/")
    check.add_argument("--code", type=Path, action="append", help="code file or folder (repeatable); use with --docs")
    check.add_argument("--docs", type=Path, action="append", help="markdown file or folder (repeatable); use with --code")
    check.add_argument("--base", help="changed-only mode: compare against this branch (needs --code and --docs)")
    check.add_argument("--max-calls", type=int, help="stop after this many LLM calls (checks and verifier) and report what was checked")
    check.add_argument("--out", default="drift_report.json", type=Path)
    check.add_argument("--comment-file", type=Path, help="also write the PR comment markdown here")
    check.add_argument("--fake", action="store_true", help="offline fakes instead of real APIs")
    args = ap.parse_args(argv)
    if bool(args.fixture) == bool(args.code or args.docs) or bool(args.code) != bool(args.docs):
        ap.error("use either --fixture, or both --code and --docs")
    if args.base and args.fixture:
        ap.error("--base needs --code and --docs, not --fixture")

    if not args.fake and not os.getenv("OPENAI_API_KEY"):  # embeddings always use OpenAI
        sys.exit("error: OPENAI_API_KEY is not set")

    budget = CallBudget(args.max_calls) if args.max_calls else None
    wrap = budget.wrap if budget else (lambda f: f)
    embedder = FakeEmbedder() if args.fake else OpenAIEmbedder()
    checker = FakeDriftChecker() if args.fake else LLMDriftChecker(wrap(make_complete()))
    verifier = FakeVerifier() if args.fake else LLMVerifier(wrap(make_complete(json_mode=False)))

    only = trigger = None
    if args.fixture:
        root = args.fixture
        code, docs, identifiers = (chunk_code_dir(root / "src"), chunk_docs_dir(root / "docs"),
                                   code_identifiers_dir(root / "src"))
    else:
        root = base_dir(args.code + args.docs)
        code, docs, identifiers = chunks_from_paths(args.code, args.docs, root)
    if args.base:
        rel = lambda paths: [p.resolve().relative_to(root).as_posix() for p in paths]
        changes = diff_changes(root, args.base, code, docs, rel(args.code), rel(args.docs))
        only, trigger = changes.changed_ids, changes.trigger_doc_ids
        print(f"changed-only: {len(only)} changed chunk(s), {len(changes.removed_ids)} removed, "
              f"{len(trigger)} doc section(s) to reference-check")

    unchecked = 0
    try:
        docs, results = run_check_chunks(code, docs, embedder, checker, verifier, identifiers, only, trigger)
    except CallBudgetExceeded as e:
        results, unchecked = e.partial, e.unchecked
        print(f"stopped at --max-calls={args.max_calls}: {unchecked} comparison(s) not checked")
    print_summary(docs, results)
    write_report(results, args.out)
    print(f"\nwrote {args.out}")
    if args.comment_file:
        stats = {"changed_chunks": len(only) if only is not None else len(code),
                 "calls": budget.calls if budget else sum(1 for r in results if r.detection == "llm"), "unchecked": unchecked}
        args.comment_file.write_text(render_comment(docs, results, stats))
        print(f"wrote {args.comment_file}")


if __name__ == "__main__":
    main()
