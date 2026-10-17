# self-healing-docs

Detects when code changes make markdown docs inaccurate, points at the stale sections, suggests a fix. Python source + markdown only. Local-first; GitHub Actions come in Phase 5.

## Run
- `source venv/bin/activate && pip install -r requirements.txt`
- `pytest` runs the offline suite. `pytest -m live` runs real API calls (needs `.env`).

## Conventions
- Embedder and DriftChecker are interfaces with a real and a fake implementation. Unit tests use fakes only.
- Chunk IDs are stable and appear in every report: code `path::function`, docs `path::heading`.
- Paths in IDs are relative to the scenario/repo root (e.g. `src/api.py::search`).
- LLM output is JSON, validated with pydantic; malformed output is retried once, then recorded as an error.
- Never commit `.env` or `.chroma/`. No async, no extra frameworks.

## Assumptions
- Nested functions and methods use dotted names (`outer.inner`, `Class.method`) so IDs don't collide.
- Docs split on every heading level; headings inside code fences are ignored; sections with no body are skipped; text before the first heading is `(preamble)`.
- Doc refs are only extracted from backtick spans.
- Drift detection has two types: `reference` (deterministic: doc routes/underscore-names missing from the code, no LLM) and `llm` (factual mismatch). Docs already flagged by `reference` skip the LLM call.
- `FakeDriftChecker` tests are plumbing tests, not accuracy tests. Accuracy is measured by the reference-check tests and the live tests.
- Reference check rules: a path is a route if an HTTP method precedes it, or (bare) it is not a filename and shares a non-version segment with a real route. the symbol index holds every identifier in the code (functions, classes, params, assigned names/fields/attributes, keyword args, imports); snake_case names are checked only when the section is anchored to code (call syntax, a parameter list, or a ref that exists in the code). Shell/config fenced blocks are ignored. Config keys and file paths are never checked.
- Provider models: `LLM_MODEL` env overrides the per-provider default.
- LLM stale flags must carry `doc_claim` (verbatim doc quote, matched after normalizing case/backticks/whitespace) and `code_fact`; otherwise the flag is discarded and counted as `filtered`. The filter checks that the quote exists, not that it contradicts the code.
- `eval/results.md` is the running log of eval runs (stage by stage); `eval/baseline.md` is the earlier pre-tuning baseline.
- Verifier: each LLM stale flag that passes the quote check gets one extra temperature-0 call with only `doc_claim` and `code_fact` ("does the first directly contradict the second?"). Anything but a leading "yes" discards the flag (`verifier_rejected`). Verifier calls count toward `--max-calls`. `eval/run_eval.py --no-verifier` measures without it.
- LLM pairing is mutual top-k: a (code chunk, doc section) pair is kept only if the doc is in the code chunk's top-3 docs AND the chunk is in the doc's top-5 code chunks (cosine, same embedder). That caps a doc section at 5 LLM pairs. There is no ref-sharing prefilter (it would drop prose-only claims like fixture 10).
- Two report tiers. `stale`: reference-check flags plus LLM flags whose quoted `doc_claim` names a code element (backticked name/call/path/config key, or a bare /route). `review` ("worth a look"): LLM flags with prose-only claims. Eval pass = every expected doc flagged in either tier and no stale-tier false positive; eval/results.md labels every number with its tier.
- Verifier rule: "code lacks / does not mention X" is not a contradiction unless the doc names a code element; value conflicts still count. An empty `confidence` on a non-stale answer is read as "low".
- Changed-only (`--base`): old chunks come from the merge-base, new from the working tree. LLM pairs start only from new/modified chunks (by `source`); removed/renamed chunk IDs and vanished names/routes/params trigger the reference check on docs that still mention them. Misses: renames of non-snake_case names, since the reference check only checks names with an underscore.
- The PR comment is flags only (never commits). Workflow: offline `pytest`, Python 3.12, `--max-calls 30`, fork PRs skip the check and comment steps.
