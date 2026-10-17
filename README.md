# self-healing-docs

Documentation goes stale quietly. Someone changes a default, renames a parameter or deletes a function, and the docs keep describing the old behavior until a reader gets burned. Code review rarely catches it, because the stale text is in a different file from the change.

This tool reads a pull request, finds the doc sections that no longer match the code, and says which section is wrong and why. It posts that as a PR comment. It only flags: it never edits docs or pushes commits.

It is a Python project (3.12) that works on Python source and markdown docs.

## Demo

This is real output from fixture 01 (the code serves `POST /v2/search`, the docs still say `POST /v1/search`). Command: `python -m shd.cli check --fixture fixtures/01_wrong_path_missing_param --max-calls 10`.

```
STALE   docs/api.md::Search endpoint
       [reference] code: -
       reason: doc references no longer in code: route /v1/search
       fix: remove or update these references

1 sections: 0 checked by the LLM, 1 flagged by the reference check (LLM skipped), 0 never sent to the LLM (all 1 got the reference check)
```

The PR comment it wrote for that run:

```
<!-- self-healing-docs -->
## Docs drift check

### Stale

- `docs/api.md::Search endpoint` (reference check)
  - doc references no longer in code: route /v1/search
  - suggested fix: remove or update these references

_1 changed code chunk(s) checked against 1 doc section(s), 0 LLM call(s). Flags only: nothing was changed._
```

The wrong path was caught by the deterministic check, so this run used no LLM calls. The fixture also has a missing parameter (`include_archived`); because the section was already flagged, it was not sent to the LLM and the comment doesn't mention it.

## How it works

1. **Chunk.** Code is split into one chunk per function (routes, parameters and defaults, docstring, plus up to 2000 characters of module context such as constants and other signatures). Docs are split into one chunk per markdown heading. Chunk IDs are stable: `path::function` and `path::heading`.
2. **Index.** Doc sections and code chunks are embedded with OpenAI `text-embedding-3-small` and stored in a local ChromaDB.
3. **Retrieve.** A code chunk is compared with a doc section only if the doc is in the chunk's top 3 and the chunk is in the doc's top 5 by similarity. That caps the comparisons per doc section.
4. **Reference check (no LLM).** Every doc section is checked for routes and names that no longer exist in the code. It is deterministic and cheap.
5. **LLM check, then verifier.** gpt-4o (configurable) gets the code chunk, its module context and the doc section, and must return JSON, validated with pydantic and retried once. A stale flag must quote the doc text and name the code fact it contradicts. The quote must really appear in the doc, and a second call (the verifier) must agree that the two directly contradict. Flags that fail either step are dropped.
6. **Two tiers.** "Stale" is a reference flag, or an LLM flag whose quote names a code element (a route, function, parameter or config key). "Worth a look" is an LLM flag whose quote is plain prose.

There are two detection types: `reference` (deterministic) and `llm`. Each flag in the report says which one found it.

In changed-only mode (`--base`), only new or modified code chunks start LLM comparisons. Deleted or renamed code has no chunk to compare, so anything that disappeared (a function, route or parameter) triggers the reference check on the doc sections that still mention it.

## Results

Measured on 13 fixtures (small code and docs folders, each with a known answer), 5 runs, gpt-4o only. Fixtures 09 to 13 were written after seeing failures, so some overfitting is possible. Fixture 09 passes 4/5.

| Tier / check | Precision | Recall | Note |
|---|---|---|---|
| **Stale tier** (reference + LLM flags naming a code element) | 0.98 (40/41) | 0.89 (40/45) |  |
| Review tier (LLM prose-only flags) | 1.00 (5/5) | 0.11 (5/45) | 5 flags over 5 runs; recall here = stale docs that landed only in this tier |
| Either tier | 0.98 (45/46) | 1.00 (45/45) | recall counts a detection in either tier |
| Reference check (stale tier) | 1.00 (25/25) | 0.56 (25/45) |  |
| LLM check, stale tier | 0.94 (15/16) | 0.75 (15/20) | recall over expected docs the reference check missed |

The full per-fixture tables for every tuning stage are in `eval/results.md`. These numbers are about the fixtures, not about real pull requests.

## The two workflows

Both run on pull requests, and both only comment.

- **Drift check** (`self-healing-docs.yml`): runs the offline tests, then checks the changed code against `README.md` and `CLAUDE.md`. It posts one comment titled "Docs drift check" with a "Stale" and a "Worth a look" section. A hidden marker lets a new push edit the same comment.
- **AI reviewer** (`ai-review.yml`): the Claude Code GitHub Action reviews the PR the way a teammate would (bugs, missing tests, risky changes), guided by the "Review guidelines" section in `CLAUDE.md`. It posts a summary titled "AI review (Claude)" and may add inline comments. It never approves, requests changes, merges or pushes.

The drift check answers "are the docs stale?". The reviewer answers "is this change any good?". They post separate, labelled comments.

## Safety design

- Both workflows trigger on pull_request only. The steps that use secrets are skipped for forks and for dependabot, and the reviewer also skips drafts.
- Permissions are minimal: contents read and pull-requests write. The reviewer also gets id-token write, which the action needs for its short-lived app token.
- The drift check passes `--max-calls 30`, so a large PR can't run up API costs. It stops and the comment says how many comparisons were skipped.
- Jobs have a 15 minute timeout, a concurrency group that cancels older runs, and run on a pinned `ubuntu-24.04`.
- The reviewer's tools are an allow list (read files, search, `gh pr comment`, `gh pr view`, `gh pr diff`, inline comments) plus a deny list (edit, write, git, `gh pr review`, `gh pr merge`). The action is pinned to a commit, and checkout does not persist credentials.
- Workflow `run:` steps get values through `env:`, not inline expressions.
- API keys come only from repo secrets. `.env` and `.chroma/` are gitignored, and a gitleaks pre-commit hook blocks commits that contain secrets. The hook is local: after cloning, run `git config core.hooksPath .githooks`.

## Known limitations

- **Equivalence false positive (fixture 09):** the LLM can flag a doc that says a param is "empty by default" when the code has `reason: str = ""`. The two are equivalent, but the model treats them as a value conflict and the verifier agrees. It showed up as a stale-tier false positive in 2 of 5 runs in one eval and 1 of 5 in the next.
- **Reference check only covers names with an underscore:** a renamed or removed `search` is not caught by the reference check (single-word names are too often ordinary words). Routes, `snake_case` names and call syntax are covered; config keys and file paths are not checked.
- **The review tier is too small to measure:** it produced 5 flags across 5 eval runs (all from one fixture), so its precision of 1.00 says little. Treat "Worth a look" as unvalidated.
- **The naming-terms list is a blocklist:** the reference check skips a short fixed list of style words (`snake_case`, `camel_case`, `kebab_case`, ...). A style word that is not on the list (for example `screaming_kebab_case`) is still treated as a missing symbol until it is added to `NAMING_TERMS` in `src/shd/detect.py`.
- The eval uses 13 small fixtures and gpt-4o only; the anthropic and gemini providers have not been run live.
- Fixtures 09 to 13 were written after seeing failures, so the results may be better on them than on new code.
- The LLM sees one function plus a bounded module context, not the whole codebase, so it can miss behavior defined elsewhere.
- A PR that changes a lot of code can hit the 30-call cap and be only partly checked. The comment says so.
- Only Python source and markdown docs are supported, and LLM answers are not fully repeatable from run to run.

## Run it locally

```
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY (embeddings and the default LLM)
```

Check a fixture, or your own code and docs:

```
python -m shd.cli check --fixture fixtures/03_changed_default
python -m shd.cli check --code src/shd --docs README.md --docs CLAUDE.md
python -m shd.cli check --fixture fixtures/03_changed_default --fake   # offline, no keys
```

Changed-only mode compares against a branch and writes the PR comment to a file:

```
python -m shd.cli check --base main --code src/shd --docs README.md --docs CLAUDE.md --max-calls 30 --comment-file comment.md
```

Tests and eval:

```
pytest                 # offline suite, no API calls
pytest -m live         # real API calls
python eval/run_eval.py --runs 5 --max-calls 400
```

The LLM provider is set with `LLM_PROVIDER` (openai, anthropic or gemini; default openai with gpt-4o). Embeddings always use OpenAI.

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
