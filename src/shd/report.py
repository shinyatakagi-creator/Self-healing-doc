import json
from pathlib import Path

from shd.detect import DriftResult

MARKER = "<!-- self-healing-docs -->"


def doc_statuses(doc_chunks: list[dict], results: list[DriftResult]) -> list[dict]:
    """One row per doc section. STALE: a reference flag or an LLM flag quoting a code element.
    REVIEW ("worth a look"): only LLM flags with prose-only claims. ERROR: a check failed and nothing flagged it."""
    rows = []
    for doc in doc_chunks:
        mine = [r for r in results if r.doc_id == doc["id"]]
        stale = [r for r in mine if r.tier == "stale"]
        review = [r for r in mine if r.tier == "review"]
        status = "STALE" if stale else "REVIEW" if review else "ERROR" if any(r.error for r in mine) else "OK"
        rows.append({"doc_id": doc["id"], "status": status, "results": stale or review or mine})
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
        print(f"{row['status']:6}  {row['doc_id']}")
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


def _bullet(row: dict) -> list[str]:
    r = row["results"][0]
    lines = [f"- `{row['doc_id']}` ({', '.join(sorted({x.detection for x in row['results']}))} check)", f"  - {r.reason}"]
    if r.doc_claim:
        lines.append(f"  - doc says: > {r.doc_claim}")
    if r.code_id:
        lines.append(f"  - code: `{r.code_id}`")
    if r.suggested_fix:
        lines.append(f"  - suggested fix: {r.suggested_fix}")
    return lines


def render_comment(doc_chunks: list[dict], results: list[DriftResult], stats: dict | None = None) -> str:
    """Markdown PR comment. The hidden marker lets reruns update the same comment."""
    stats = stats or {}
    rows = doc_statuses(doc_chunks, results)
    out = [MARKER, "## Docs drift check", ""]
    for title, status in (("Stale", "STALE"), ("Worth a look", "REVIEW")):
        mine = [r for r in rows if r["status"] == status]
        if mine:
            out += [f"### {title}", ""] + [l for r in mine for l in _bullet(r)] + [""]
    if not any(r["status"] in ("STALE", "REVIEW") for r in rows):
        out += ["No stale docs found.", ""]
    errors = sum(1 for r in results if r.error)
    foot = [f"{stats.get('changed_chunks', '?')} changed code chunk(s) checked against {len(doc_chunks)} doc section(s)"
            f", {stats.get('calls', 0)} LLM call(s)"]
    if errors:
        foot.append(f"{errors} check(s) errored")
    out.append("_" + "; ".join(foot) + ". Flags only: nothing was changed._")
    if stats.get("unchecked"):
        out.append(f"\n> Stopped at the LLM call cap: {stats['unchecked']} comparison(s) were not checked.")
    return "\n".join(out) + "\n"
