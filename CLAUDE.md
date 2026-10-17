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
- Reference check limits: bare `/x` paths count as routes, only names containing `_` are checked, config keys and file paths are not.
- Provider models: `LLM_MODEL` env overrides the per-provider default.
