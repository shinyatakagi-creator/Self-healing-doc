# self-healing-docs

Flags documentation sections that no longer match the code, and suggests a fix.

```
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add keys
pytest                 # offline
pytest -m live         # real API calls
```

Status: Phase 5 (changed-only mode, PR workflow). Phase 4 (CLI + eval). `python -m shd.cli check --fixture fixtures/03_changed_default`; `python eval/run_eval.py --runs 3 --max-calls 60`. Baseline in eval/baseline.md.

## Changed-only mode

```
python -m shd.cli check --base main --code src --docs README.md --docs docs --max-calls 30 --comment-file comment.md
```

Compares the merge-base with `--base` to the working tree. Only changed or new code chunks start LLM comparisons.
Removed or renamed chunks (and any name, route or param that disappeared from the code) trigger the reference check
on the doc sections that still mention them; changed doc files get the reference check too.
`--max-calls` stops the run and reports what was checked. The comment has a hidden marker, so reruns update it.

## Testing the workflow

Do this on a scratch repo, not this one.

1. Push a copy of this project to a scratch GitHub repo with `main` as the default branch.
2. Add the repo secret `OPENAI_API_KEY` (Settings > Secrets and variables > Actions). `GITHUB_TOKEN` is automatic.
3. Open a PR from a branch that changes a default, like fixture 03: in `src/shd/chunk_code.py` change `CONTEXT_CAP = 2000` to a different value, or edit a documented default in `src/shd/`.
4. Expected: the `pytest` step passes, then a PR comment with a "Stale" and/or "Worth a look" section appears.
5. Push another commit to the same PR: the same comment is edited, not duplicated.
6. Delete a function that README.md or CLAUDE.md mentions by name: it shows up under "Stale" through the reference check.
7. PRs from forks run only the offline tests: forks do not get repo secrets, so the check and comment steps are skipped.

Run locally first: `python -m shd.cli check --base main --code src/shd --docs README.md --docs CLAUDE.md --comment-file /tmp/c.md`

## Known limitations

- **Equivalence false positive (fixture 09):** the LLM can flag a doc that says a param is "empty by default" when the code has `reason: str = ""`. The two are equivalent, but the model treats them as a value conflict and the verifier agrees. It showed up as a stale-tier false positive in 2 of 5 eval runs.
- **Reference check only covers names with an underscore:** a renamed or removed `search` is not caught by the reference check (single-word names are too often ordinary words). Routes, `snake_case` names and call syntax are covered; config keys and file paths are not checked.
- **The review tier is too small to measure:** it produced 5 flags across 5 eval runs (all from one fixture), so its precision of 1.00 says little. Treat "Worth a look" as unvalidated.
- The eval uses 12 small fixtures and gpt-4o only; the anthropic and gemini providers have not been run live.

To scan everything at once, call `run_drift_scan()`.
