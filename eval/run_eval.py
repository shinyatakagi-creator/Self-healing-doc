"""Run every fixture through the real pipeline (live APIs) and print a results table.

    python eval/run_eval.py --runs 3 --max-calls 60 --out eval/baseline.md
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from shd.cli import run_check
from shd.detect import CallBudgetExceeded, DEFAULT_MODELS, LLMDriftChecker, budgeted, make_complete, stale_doc_ids
from shd.embeddings import OpenAIEmbedder

FIXTURES = Path(__file__).parent.parent / "fixtures"


def ratio(num: int, den: int) -> str:
    return f"{num / den:.2f} ({num}/{den})" if den else "n/a (0/0)"


def prf(tp: int, fp: int, fn: int) -> tuple[str, str]:
    return ratio(tp, tp + fp), ratio(tp, tp + fn)


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--max-calls", type=int, default=50, help="cap on LLM calls across all runs")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--label", default="Eval baseline", help="heading for this run in the output")
    ap.add_argument("--append", action="store_true", help="append to --out instead of overwriting")
    args = ap.parse_args()

    complete = budgeted(make_complete(), args.max_calls)
    checker, embedder = LLMDriftChecker(complete), OpenAIEmbedder()
    scenarios = sorted(p for p in FIXTURES.iterdir() if p.is_dir())

    passes = Counter()
    errors = Counter()
    filtered = Counter()  # scenario -> discarded flags
    filtered_true = 0  # discarded flags on docs that really were stale
    wrong = defaultdict(Counter)  # scenario -> "FP doc" / "FN doc" -> runs
    reasons: dict[str, str] = {}
    expected_n = {}
    tot = {k: Counter() for k in ("overall", "reference", "llm")}
    try:
        for _ in range(args.runs):
            for sc in scenarios:
                expected = json.loads((sc / "expected.json").read_text())["stale"]
                docs, results = run_check(sc, embedder, checker)
                expected, got = set(expected), stale_doc_ids(results)
                ref = {r.doc_id for r in results if r.detection == "reference" and r.is_stale}
                llm = {r.doc_id for r in results if r.detection == "llm" and r.is_stale}
                expected_n[sc.name] = len(expected)
                passes[sc.name] += got == expected
                errors[sc.name] += sum(1 for r in results if r.error)
                dropped = {r.doc_id for r in results if r.filtered}
                filtered[sc.name] += len(dropped)
                filtered_true += len(dropped & expected)
                for d in got - expected:
                    wrong[sc.name][f"FP {d}"] += 1
                    reasons.setdefault(f"{sc.name} FP {d}", next(r.reason for r in results if r.doc_id == d and r.is_stale))
                for d in expected - got:
                    wrong[sc.name][f"FN {d}"] += 1
                # LLM recall only counts stale docs the reference check did not already catch
                for key, flagged, truth in (("overall", got, expected), ("reference", ref, expected), ("llm", llm, expected - ref)):
                    tot[key]["tp"] += len(flagged & truth)
                    tot[key]["fp"] += len(flagged - expected)
                    tot[key]["fn"] += len(truth - flagged)
    except CallBudgetExceeded as e:
        sys.exit(f"aborted: {e}. No table written; raise --max-calls to finish.")

    provider = os.getenv("LLM_PROVIDER", "openai")
    lines = [
        f"## {args.label}",
        "",
        f"{date.today()} | provider `{provider}` model `{os.getenv('LLM_MODEL') or DEFAULT_MODELS[provider]}` | "
        f"embedder `text-embedding-3-small` | runs {args.runs} | LLM calls used {complete.calls}/{args.max_calls}",
        "",
        "| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors | Filtered |",
        "|---|---|---|---|---|---|",
    ]
    for sc in scenarios:
        n = sc.name
        w = "; ".join(f"{k} ({v}/{args.runs})" for k, v in wrong[n].items()) or "-"
        lines.append(f"| {n} | {expected_n[n]} | {passes[n]}/{args.runs} | {w} | {errors[n]} | {filtered[n]} |")
    lines += ["", "| Check | Precision | Recall |", "|---|---|---|"]
    notes = {"overall": "overall", "reference": "reference check", "llm": "LLM check (recall over stale docs the reference check missed)"}
    for k, label in notes.items():
        p, r = prf(tot[k]["tp"], tot[k]["fp"], tot[k]["fn"])
        lines.append(f"| {label} | {p} | {r} |")
    lines += ["", f"Filtered flags (LLM said stale, claim check discarded it): {sum(filtered.values())} total, "
              f"{filtered_true} of them on docs that really were stale."]
    if reasons:
        lines += ["", "False positive reasons (first seen):", ""]
        lines += [f"- `{k}`: {v}" for k, v in reasons.items()]
    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        old = args.out.read_text() + "\n" if args.append and args.out.exists() else "# Eval results\n\n"
        args.out.write_text(old + text)


if __name__ == "__main__":
    main()
