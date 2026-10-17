"""Run every fixture through the real pipeline (live APIs) and print a results table.

    python eval/run_eval.py --runs 5 --max-calls 400 --out eval/results.md --append --label "..."

Tiers: "stale" = reference-check flags + LLM flags whose quoted claim names a code element;
"review" = LLM flags with prose-only claims. A scenario passes if every expected doc is flagged in
either tier and the stale tier has no false positives (review-tier false positives do not fail it).
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
from shd.detect import (CallBudget, CallBudgetExceeded, DEFAULT_MODELS, LLMDriftChecker, LLMVerifier,
                        make_complete, tier_doc_ids)
from shd.embeddings import OpenAIEmbedder

FIXTURES = Path(__file__).parent.parent / "fixtures"


def ratio(num: int, den: int) -> str:
    return f"{num / den:.2f} ({num}/{den})" if den else "n/a (0/0)"


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--max-calls", type=int, default=50, help="cap on LLM calls across all runs")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--label", default="Eval baseline", help="heading for this run in the output")
    ap.add_argument("--no-verifier", dest="verifier", action="store_false", help="skip the verifier pass")
    ap.add_argument("--append", action="store_true", help="append to --out instead of overwriting")
    args = ap.parse_args()

    budget = CallBudget(args.max_calls)
    checker = LLMDriftChecker(budget.wrap(make_complete()))
    verifier = LLMVerifier(budget.wrap(make_complete(json_mode=False))) if args.verifier else None
    embedder = OpenAIEmbedder()
    scenarios = sorted(p for p in FIXTURES.iterdir() if p.is_dir())

    passes, errors, filtered, rejected = Counter(), Counter(), Counter(), Counter()
    wrong = defaultdict(Counter)  # scenario -> "FP[stale] doc" etc -> runs
    reasons: dict[str, str] = {}
    expected_n = {}
    tot = defaultdict(Counter)  # row -> tp/fp/fn
    flags = Counter()
    drops = Counter()  # filtered_true, rejected_true

    try:
        for _ in range(args.runs):
            for sc in scenarios:
                expected = set(json.loads((sc / "expected.json").read_text())["stale"])
                _, results = run_check(sc, embedder, checker, verifier)
                ref = {r.doc_id for r in results if r.detection == "reference" and r.is_stale}
                llm_stale = {r.doc_id for r in results if r.detection == "llm" and r.tier == "stale"}
                stale_tier = tier_doc_ids(results, "stale")
                review = tier_doc_ids(results, "review")
                either = stale_tier | review
                expected_n[sc.name] = len(expected)
                passes[sc.name] += (expected <= either) and not (stale_tier - expected)
                errors[sc.name] += sum(1 for r in results if r.error)
                dropped = {r.doc_id for r in results if r.filtered}
                vr = {r.doc_id for r in results if r.verifier_rejected}
                filtered[sc.name] += len(dropped)
                rejected[sc.name] += len(vr)
                drops["filtered_true"] += len(dropped & expected)
                drops["rejected_true"] += len(vr & expected)
                for tier, docs in (("stale", stale_tier), ("review", review)):
                    for d in docs - expected:
                        wrong[sc.name][f"FP[{tier}] {d}"] += 1
                        reasons.setdefault(f"{sc.name} FP[{tier}] {d}", next(
                            f"{r.reason} | claim: {r.doc_claim!r}" for r in results if r.doc_id == d and r.tier == tier))
                for d in expected - either:
                    wrong[sc.name][f"FN {d}"] += 1
                flags["stale"] += len(stale_tier)
                flags["review"] += len(review)
                # recall on the stale tier counts only stale-tier detections; LLM rows only count
                # expected docs the reference check missed
                for key, flagged, truth in (
                    ("stale tier", stale_tier, expected), ("review tier", review, expected),
                    ("either tier", either, expected), ("reference check", ref, expected),
                    ("LLM check, stale tier", llm_stale, expected - ref),
                ):
                    tot[key]["tp"] += len(flagged & truth)
                    tot[key]["fp"] += len(flagged - expected)
                    tot[key]["fn"] += len(truth - flagged)
    except CallBudgetExceeded as e:
        sys.exit(f"aborted: {e}. No table written; raise --max-calls to finish.")

    provider = os.getenv("LLM_PROVIDER", "openai")
    n = args.runs
    lines = [
        f"## {args.label}",
        "",
        f"{date.today()} | provider `{provider}` model `{os.getenv('LLM_MODEL') or DEFAULT_MODELS[provider]}` | "
        f"embedder `text-embedding-3-small` | runs {n} | LLM calls used {budget.calls}/{args.max_calls} | "
        f"verifier {'on' if args.verifier else 'off'}",
        "",
        "Pass = every expected doc flagged in either tier AND no stale-tier false positive.",
        "",
        "| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors | Filtered | Verifier rejected |",
        "|---|---|---|---|---|---|---|",
    ]
    for sc in scenarios:
        name = sc.name
        w = "; ".join(f"{k} ({v}/{n})" for k, v in wrong[name].items()) or "-"
        lines.append(f"| {name} | {expected_n[name]} | {passes[name]}/{n} | {w} | {errors[name]} | {filtered[name]} | {rejected[name]} |")

    def row(label, key, note=""):
        t = tot[key]
        return f"| {label} | {ratio(t['tp'], t['tp'] + t['fp'])} | {ratio(t['tp'], t['tp'] + t['fn'])} | {note} |"

    lines += [
        "", "| Tier / check | Precision | Recall | Note |", "|---|---|---|---|",
        row("**Stale tier** (reference + LLM flags naming a code element)", "stale tier"),
        row("Review tier (LLM prose-only flags)", "review tier",
            f"{flags['review']} flags over {n} runs; recall here = stale docs that landed only in this tier"),
        row("Either tier", "either tier", "recall counts a detection in either tier"),
        row("Reference check (stale tier)", "reference check"),
        row("LLM check, stale tier", "LLM check, stale tier",
            "recall over expected docs the reference check missed"),
        "",
        f"Filtered flags (claim not grounded): {sum(filtered.values())} total, {drops['filtered_true']} on docs that really were stale.",
        f"Verifier rejected flags: {sum(rejected.values())} total, {drops['rejected_true']} on docs that really were stale.",
    ]
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
