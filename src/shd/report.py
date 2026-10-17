import json
from pathlib import Path

from shd.detect import DriftResult


def doc_statuses(doc_chunks: list[dict], results: list[DriftResult]) -> list[dict]:
    """One row per doc section. STALE if any check flagged it; ERROR if a check failed and nothing flagged it."""
    rows = []
    for doc in doc_chunks:
        mine = [r for r in results if r.doc_id == doc["id"]]
        stale = [r for r in mine if r.is_stale]
        status = "STALE" if stale else "ERROR" if any(r.error for r in mine) else "OK"
        rows.append({"doc_id": doc["id"], "status": status, "results": stale or mine})
    return rows


def write_report(results: list[DriftResult], path: str | Path) -> None:
    Path(path).write_text(json.dumps([r.model_dump() for r in results], indent=2))


def coverage(doc_chunks: list[dict], results: list[DriftResult]) -> dict:
    """Every section gets the reference check. The LLM only sees sections retrieved for some code chunk."""
    llm_seen = {r.doc_id for r in results if r.detection == "llm"}
    ref_flagged = {r.doc_id for r in results if r.detection == "reference"}
    ids = {d["id"] for d in doc_chunks}
    return {"sections": len(ids), "llm_checked": len(llm_seen), "reference_flagged_skipped_llm": len(ref_flagged - llm_seen),
            "never_sent_to_llm": len(ids - llm_seen - ref_flagged)}


def print_summary(doc_chunks: list[dict], results: list[DriftResult]) -> None:
    for row in doc_statuses(doc_chunks, results):
        print(f"{row['status']:5}  {row['doc_id']}")
        if row["status"] == "OK":
            continue
        for r in row["results"]:
            print(f"       [{r.detection}] code: {r.code_id or '-'}")
            print(f"       reason: {r.error or r.reason}")
            if r.doc_claim:
                print(f"       claim: {r.doc_claim}")
            if r.suggested_fix:
                print(f"       fix: {r.suggested_fix}")
    c = coverage(doc_chunks, results)
    print(f"\n{c['sections']} sections: {c['llm_checked']} checked by the LLM, {c['reference_flagged_skipped_llm']} flagged by the "
          f"reference check (LLM skipped), {c['never_sent_to_llm']} never sent to the LLM (all {c['sections']} got the reference check)")
