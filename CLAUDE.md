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
