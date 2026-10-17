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

## Testing the workflows

Two workflows run on every PR: `self-healing-docs.yml` (the drift check, comment titled "Docs drift check") and
`ai-review.yml` (the AI reviewer, comment titled "AI review (Claude)"). Each posts its own comment. Do this on a scratch repo, not this one.

1. Push a copy of this project to a scratch GitHub repo with `main` as the default branch.
2. Add the repo secrets `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` (Settings > Secrets and variables > Actions). `GITHUB_TOKEN` is automatic.
3. Install the Claude GitHub app on the scratch repo (https://github.com/apps/claude, or run `/install-github-app` in Claude Code and decline the workflow file it offers). The reviewer needs it.
4. **Drift PR:** open a PR that changes a default, like fixture 03 (for example edit a documented default in `src/shd/`). Expected: `pytest` passes, then a "Docs drift check" comment with a "Stale" and/or "Worth a look" section. Push another commit: the same comment is edited, not duplicated. Delete a function that README.md or CLAUDE.md mentions by name: it appears under "Stale".
5. **Sloppy PR:** open a PR with a deliberately sloppy change, such as an unvalidated LLM response (use `json.loads(text)` straight into a result) or a new behavior with no test. Expected: an "AI review (Claude)" comment pointing at it, with the guidelines from CLAUDE.md. The reviewer must not approve, request changes or push.
6. Drafts are skipped by the reviewer. PRs from forks (and dependabot) run only the offline tests: they do not get repo secrets, so the check, the comment and the review are skipped.
7. The reviewer checks out with `persist-credentials: false`, so the checked-out repo holds no token. Watch the first run to confirm the action still works that way.

Run the drift check locally first: `python -m shd.cli check --base main --code src/shd --docs README.md --docs CLAUDE.md --comment-file /tmp/c.md`

## Known limitations

- **Equivalence false positive (fixture 09):** the LLM can flag a doc that says a param is "empty by default" when the code has `reason: str = ""`. The two are equivalent, but the model treats them as a value conflict and the verifier agrees. It showed up as a stale-tier false positive in 2 of 5 eval runs.
- **Reference check only covers names with an underscore:** a renamed or removed `search` is not caught by the reference check (single-word names are too often ordinary words). Routes, `snake_case` names and call syntax are covered; config keys and file paths are not checked.
- **The review tier is too small to measure:** it produced 5 flags across 5 eval runs (all from one fixture), so its precision of 1.00 says little. Treat "Worth a look" as unvalidated.
- **The naming-terms list is a blocklist:** the reference check skips a short fixed list of style words (`snake_case`, `camel_case`, `kebab_case`, ...). A style word that is not on the list (for example `screaming_kebab_case`) is still treated as a missing symbol until it is added to `NAMING_TERMS` in `src/shd/detect.py`.
- The eval uses 13 small fixtures and gpt-4o only; the anthropic and gemini providers have not been run live.
