import argparse
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from shd.chunk_code import chunk_code_dir
from shd.chunk_docs import chunk_docs_dir
from shd.detect import DriftChecker, DriftResult, FakeDriftChecker, LLMDriftChecker, check_drift, make_complete
from shd.embeddings import Embedder, FakeEmbedder, OpenAIEmbedder
from shd.index import DocIndex
from shd.report import print_summary, write_report


def run_check(root: Path, embedder: Embedder, checker: DriftChecker) -> tuple[list[dict], list[DriftResult]]:
    code = chunk_code_dir(root / "src")
    docs = chunk_docs_dir(root / "docs")
    with tempfile.TemporaryDirectory() as tmp:
        return docs, check_drift(code, docs, DocIndex(tmp, embedder), checker)


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="shd")
    sub = ap.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="check docs against code")
    check.add_argument("--fixture", required=True, type=Path, help="folder with src/ and docs/")
    check.add_argument("--out", default="drift_report.json", type=Path)
    check.add_argument("--fake", action="store_true", help="offline fakes instead of real APIs")
    args = ap.parse_args(argv)

    embedder = FakeEmbedder() if args.fake else OpenAIEmbedder()
    checker = FakeDriftChecker() if args.fake else LLMDriftChecker(make_complete())
    docs, results = run_check(args.fixture, embedder, checker)
    print_summary(docs, results)
    write_report(results, args.out)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
