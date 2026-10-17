import argparse
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from shd.chunk_code import chunk_code, chunk_code_dir, code_identifiers_dir, code_identifiers
from shd.chunk_docs import chunk_docs, chunk_docs_dir
from shd.detect import (DriftChecker, DriftResult, FakeDriftChecker, FakeVerifier, LLMDriftChecker, LLMVerifier,
                        Verifier, check_drift, make_complete)
from shd.embeddings import Embedder, FakeEmbedder, OpenAIEmbedder
from shd.index import DocIndex
from shd.report import print_summary, write_report


def run_check(root: Path, embedder: Embedder, checker: DriftChecker, verifier: Verifier | None = None) -> tuple[list[dict], list[DriftResult]]:
    return run_check_chunks(chunk_code_dir(root / "src"), chunk_docs_dir(root / "docs"), embedder, checker, verifier,
                            code_identifiers_dir(root / "src"))


def run_check_chunks(code: list[dict], docs: list[dict], embedder: Embedder, checker: DriftChecker,
                     verifier: Verifier | None = None, identifiers: set[str] | None = None) -> tuple[list[dict], list[DriftResult]]:
    with tempfile.TemporaryDirectory() as tmp:
        return docs, check_drift(code, docs, DocIndex(tmp, embedder), checker, verifier=verifier, identifiers=identifiers)


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
    check.add_argument("--out", default="drift_report.json", type=Path)
    check.add_argument("--fake", action="store_true", help="offline fakes instead of real APIs")
    args = ap.parse_args(argv)
    if bool(args.fixture) == bool(args.code or args.docs) or bool(args.code) != bool(args.docs):
        ap.error("use either --fixture, or both --code and --docs")

    embedder = FakeEmbedder() if args.fake else OpenAIEmbedder()
    checker = FakeDriftChecker() if args.fake else LLMDriftChecker(make_complete())
    verifier = FakeVerifier() if args.fake else LLMVerifier(make_complete(json_mode=False))
    if args.fixture:
        docs, results = run_check(args.fixture, embedder, checker, verifier)
    else:
        code, docs, identifiers = chunks_from_paths(args.code, args.docs, Path.cwd())
        docs, results = run_check_chunks(code, docs, embedder, checker, verifier, identifiers)
    print_summary(docs, results)
    write_report(results, args.out)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
