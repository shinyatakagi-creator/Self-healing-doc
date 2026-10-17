# Eval results

## Stage 0: baseline with held-out fixtures 09 and 10 (no logic changes)

2026-10-17 | provider `openai` model `gpt-4o` | embedder `text-embedding-3-small` | runs 3 | LLM calls used 60/150

| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors |
|---|---|---|---|---|
| 01_wrong_path_missing_param | 1 | 3/3 | - | 0 |
| 02_removed_param | 1 | 3/3 | - | 0 |
| 03_changed_default | 1 | 3/3 | - | 0 |
| 04_deleted_function | 1 | 3/3 | - | 0 |
| 05_clean_match | 0 | 3/3 | - | 0 |
| 06_clean_reworded | 0 | 3/3 | - | 0 |
| 07_unrelated_docs | 0 | 3/3 | - | 0 |
| 08_large_corpus | 1 | 0/3 | FP docs/guide.md::Searching these docs (3/3); FP docs/guide.md::Result pagination (3/3) | 0 |
| 09_orders_corpus | 1 | 0/3 | FP docs/ops.md::Logging (3/3); FP docs/ops.md::Configuration (3/3); FP docs/ops.md::Deployment (3/3); FP docs/ops.md::Backups (3/3) | 0 |
| 10_prose_claim | 1 | 3/3 | - | 0 |

| Check | Precision | Recall |
|---|---|---|
| overall | 0.54 (21/39) | 1.00 (21/21) |
| reference check | 0.43 (9/21) | 0.43 (9/21) |
| LLM check (recall over stale docs the reference check missed) | 0.67 (12/18) | 1.00 (12/12) |

False positive reasons (first seen):

- `08_large_corpus FP docs/guide.md::Searching these docs`: The documentation does not mention the '/v2/search' route or its parameters.
- `08_large_corpus FP docs/guide.md::Result pagination`: The documentation does not mention the '/v2/search' route or the 'query' and 'limit' parameters.
- `09_orders_corpus FP docs/ops.md::Logging`: doc references no longer in code: route /var/log/orders/app.log
- `09_orders_corpus FP docs/ops.md::Configuration`: doc references no longer in code: name max_connections, name request_timeout
- `09_orders_corpus FP docs/ops.md::Deployment`: doc references no longer in code: name debug_mode
- `09_orders_corpus FP docs/ops.md::Backups`: doc references no longer in code: name pg_dump

## Stage 1: doc_claim/code_fact schema + claim filter

2026-10-17 | provider `openai` model `gpt-4o` | embedder `text-embedding-3-small` | runs 3 | LLM calls used 60/150

| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors | Filtered |
|---|---|---|---|---|---|
| 01_wrong_path_missing_param | 1 | 3/3 | - | 0 | 0 |
| 02_removed_param | 1 | 3/3 | - | 0 | 0 |
| 03_changed_default | 1 | 3/3 | - | 0 | 0 |
| 04_deleted_function | 1 | 3/3 | - | 0 | 0 |
| 05_clean_match | 0 | 3/3 | - | 0 | 0 |
| 06_clean_reworded | 0 | 3/3 | - | 0 | 0 |
| 07_unrelated_docs | 0 | 3/3 | - | 0 | 0 |
| 08_large_corpus | 1 | 1/3 | FP docs/guide.md::Searching these docs (2/3) | 0 | 0 |
| 09_orders_corpus | 1 | 0/3 | FP docs/ops.md::Backups (3/3); FP docs/ops.md::Deployment (3/3); FP docs/ops.md::Configuration (3/3); FP docs/ops.md::Logging (3/3) | 0 | 0 |
| 10_prose_claim | 1 | 3/3 | - | 0 | 0 |

| Check | Precision | Recall |
|---|---|---|
| overall | 0.60 (21/35) | 1.00 (21/21) |
| reference check | 0.43 (9/21) | 0.43 (9/21) |
| LLM check (recall over stale docs the reference check missed) | 0.86 (12/14) | 1.00 (12/12) |

Filtered flags (LLM said stale, claim check discarded it): 0 total, 0 of them on docs that really were stale.

False positive reasons (first seen):

- `08_large_corpus FP docs/guide.md::Searching these docs`: The documentation does not mention the '/v2/search' API endpoint or its parameters.
- `09_orders_corpus FP docs/ops.md::Backups`: doc references no longer in code: name pg_dump
- `09_orders_corpus FP docs/ops.md::Deployment`: doc references no longer in code: name debug_mode
- `09_orders_corpus FP docs/ops.md::Configuration`: doc references no longer in code: name max_connections, name request_timeout
- `09_orders_corpus FP docs/ops.md::Logging`: doc references no longer in code: route /var/log/orders/app.log

## Stage 2a: baseline with held-out fixture 11, old reference check

2026-10-17 | provider `openai` model `gpt-4o` | embedder `text-embedding-3-small` | runs 3 | LLM calls used 66/200

| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors | Filtered |
|---|---|---|---|---|---|
| 01_wrong_path_missing_param | 1 | 3/3 | - | 0 | 0 |
| 02_removed_param | 1 | 3/3 | - | 0 | 0 |
| 03_changed_default | 1 | 3/3 | - | 0 | 0 |
| 04_deleted_function | 1 | 3/3 | - | 0 | 0 |
| 05_clean_match | 0 | 3/3 | - | 0 | 0 |
| 06_clean_reworded | 0 | 3/3 | - | 0 | 0 |
| 07_unrelated_docs | 0 | 3/3 | - | 0 | 0 |
| 08_large_corpus | 1 | 3/3 | - | 0 | 0 |
| 09_orders_corpus | 1 | 0/3 | FP docs/ops.md::Configuration (3/3); FP docs/ops.md::Deployment (3/3); FP docs/ops.md::Backups (3/3); FP docs/ops.md::Logging (3/3) | 0 | 0 |
| 10_prose_claim | 1 | 3/3 | - | 0 | 0 |
| 11_stray_symbols | 0 | 0/3 | FP docs/ops.md::Scheduling (3/3); FP docs/ops.md::Files (3/3); FP docs/ops.md::Retries (3/3); FP docs/ops.md::Environment (3/3) | 0 | 0 |

| Check | Precision | Recall |
|---|---|---|
| overall | 0.47 (21/45) | 1.00 (21/21) |
| reference check | 0.27 (9/33) | 0.43 (9/21) |
| LLM check (recall over stale docs the reference check missed) | 1.00 (12/12) | 1.00 (12/12) |

Filtered flags (LLM said stale, claim check discarded it): 0 total, 0 of them on docs that really were stale.

False positive reasons (first seen):

- `09_orders_corpus FP docs/ops.md::Configuration`: doc references no longer in code: name max_connections, name request_timeout
- `09_orders_corpus FP docs/ops.md::Deployment`: doc references no longer in code: name debug_mode
- `09_orders_corpus FP docs/ops.md::Backups`: doc references no longer in code: name pg_dump
- `09_orders_corpus FP docs/ops.md::Logging`: doc references no longer in code: route /var/log/orders/app.log
- `11_stray_symbols FP docs/ops.md::Scheduling`: doc references no longer in code: name cron_expression
- `11_stray_symbols FP docs/ops.md::Files`: doc references no longer in code: route /tmp/export_cache, route /usr/local/bin/shd
- `11_stray_symbols FP docs/ops.md::Retries`: doc references no longer in code: name backoff_seconds, name retry_count
- `11_stray_symbols FP docs/ops.md::Environment`: doc references no longer in code: name max_workers

## Stage 2b: reference check with general rules

2026-10-17 | provider `openai` model `gpt-4o` | embedder `text-embedding-3-small` | runs 3 | LLM calls used 69/200

| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors | Filtered |
|---|---|---|---|---|---|
| 01_wrong_path_missing_param | 1 | 3/3 | - | 0 | 0 |
| 02_removed_param | 1 | 3/3 | - | 0 | 0 |
| 03_changed_default | 1 | 3/3 | - | 0 | 0 |
| 04_deleted_function | 1 | 3/3 | - | 0 | 0 |
| 05_clean_match | 0 | 3/3 | - | 0 | 0 |
| 06_clean_reworded | 0 | 3/3 | - | 0 | 0 |
| 07_unrelated_docs | 0 | 3/3 | - | 0 | 0 |
| 08_large_corpus | 1 | 0/3 | FP docs/guide.md::Searching these docs (3/3) | 0 | 0 |
| 09_orders_corpus | 1 | 3/3 | - | 0 | 0 |
| 10_prose_claim | 1 | 3/3 | - | 0 | 0 |
| 11_stray_symbols | 0 | 3/3 | - | 0 | 0 |

| Check | Precision | Recall |
|---|---|---|
| overall | 0.88 (21/24) | 1.00 (21/21) |
| reference check | 1.00 (9/9) | 0.43 (9/21) |
| LLM check (recall over stale docs the reference check missed) | 0.80 (12/15) | 1.00 (12/12) |

Filtered flags (LLM said stale, claim check discarded it): 0 total, 0 of them on docs that really were stale.

False positive reasons (first seen):

- `08_large_corpus FP docs/guide.md::Searching these docs`: The documentation does not mention the '/v2/search' endpoint or its parameters.

## Stage 2 (5 runs): general reference rules, no verifier

2026-10-17 | provider `openai` model `gpt-4o` | embedder `text-embedding-3-small` | runs 5 | LLM calls used 115/250 | verifier off

| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors | Filtered | Verifier rejected |
|---|---|---|---|---|---|---|
| 01_wrong_path_missing_param | 1 | 5/5 | - | 0 | 0 | 0 |
| 02_removed_param | 1 | 5/5 | - | 0 | 0 | 0 |
| 03_changed_default | 1 | 5/5 | - | 0 | 0 | 0 |
| 04_deleted_function | 1 | 5/5 | - | 0 | 0 | 0 |
| 05_clean_match | 0 | 5/5 | - | 0 | 0 | 0 |
| 06_clean_reworded | 0 | 5/5 | - | 0 | 0 | 0 |
| 07_unrelated_docs | 0 | 5/5 | - | 0 | 0 | 0 |
| 08_large_corpus | 1 | 1/5 | FP docs/guide.md::Searching these docs (4/5) | 0 | 0 | 0 |
| 09_orders_corpus | 1 | 5/5 | - | 0 | 0 | 0 |
| 10_prose_claim | 1 | 5/5 | - | 0 | 0 | 0 |
| 11_stray_symbols | 0 | 5/5 | - | 0 | 0 | 0 |

| Check | Precision | Recall |
|---|---|---|
| overall | 0.90 (35/39) | 1.00 (35/35) |
| reference check | 1.00 (15/15) | 0.43 (15/35) |
| LLM check (recall over stale docs the reference check missed) | 0.83 (20/24) | 1.00 (20/20) |

Filtered flags (LLM said stale, claim check discarded it): 0 total, 0 of them on docs that really were stale.
Verifier rejected flags: 0 total, 0 of them on docs that really were stale.

False positive reasons (first seen):

- `08_large_corpus FP docs/guide.md::Searching these docs`: The documentation does not mention the '/v2/search' endpoint or its parameters.

## Stage 3 (5 runs): + LLM verifier pass

2026-10-17 | provider `openai` model `gpt-4o` | embedder `text-embedding-3-small` | runs 5 | LLM calls used 140/250 | verifier on

| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors | Filtered | Verifier rejected |
|---|---|---|---|---|---|---|
| 01_wrong_path_missing_param | 1 | 5/5 | - | 0 | 0 | 0 |
| 02_removed_param | 1 | 5/5 | - | 0 | 0 | 0 |
| 03_changed_default | 1 | 5/5 | - | 0 | 0 | 0 |
| 04_deleted_function | 1 | 5/5 | - | 0 | 0 | 0 |
| 05_clean_match | 0 | 5/5 | - | 0 | 0 | 0 |
| 06_clean_reworded | 0 | 5/5 | - | 0 | 0 | 0 |
| 07_unrelated_docs | 0 | 5/5 | - | 0 | 0 | 0 |
| 08_large_corpus | 1 | 5/5 | - | 0 | 0 | 3 |
| 09_orders_corpus | 1 | 5/5 | - | 0 | 0 | 0 |
| 10_prose_claim | 1 | 5/5 | - | 0 | 0 | 0 |
| 11_stray_symbols | 0 | 5/5 | - | 0 | 0 | 0 |

| Check | Precision | Recall |
|---|---|---|
| overall | 1.00 (35/35) | 1.00 (35/35) |
| reference check | 1.00 (15/15) | 0.43 (15/35) |
| LLM check (recall over stale docs the reference check missed) | 1.00 (20/20) | 1.00 (20/20) |

Filtered flags (LLM said stale, claim check discarded it): 0 total, 0 of them on docs that really were stale.
Verifier rejected flags: 3 total, 0 of them on docs that really were stale.

## Stage 4 baseline (3 runs): + held-out fixture 12, before any Stage 4 logic change

2026-10-17 | provider `openai` model `gpt-4o` | embedder `text-embedding-3-small` | runs 3 | LLM calls used 89/300 | verifier on

| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors | Filtered | Verifier rejected |
|---|---|---|---|---|---|---|
| 01_wrong_path_missing_param | 1 | 3/3 | - | 0 | 0 | 0 |
| 02_removed_param | 1 | 3/3 | - | 0 | 0 | 0 |
| 03_changed_default | 1 | 3/3 | - | 0 | 0 | 0 |
| 04_deleted_function | 1 | 3/3 | - | 0 | 0 | 0 |
| 05_clean_match | 0 | 3/3 | - | 0 | 0 | 0 |
| 06_clean_reworded | 0 | 3/3 | - | 0 | 0 | 0 |
| 07_unrelated_docs | 0 | 3/3 | - | 0 | 0 | 0 |
| 08_large_corpus | 1 | 3/3 | - | 0 | 0 | 3 |
| 09_orders_corpus | 1 | 3/3 | - | 0 | 0 | 0 |
| 10_prose_claim | 1 | 3/3 | - | 0 | 0 | 0 |
| 11_stray_symbols | 0 | 3/3 | - | 0 | 0 | 0 |
| 12_non_function_symbols | 1 | 0/3 | FP docs/api.md::Batch processing (3/3) | 0 | 0 | 0 |

| Check | Precision | Recall |
|---|---|---|
| overall | 0.89 (24/27) | 1.00 (24/24) |
| reference check | 0.80 (12/15) | 0.50 (12/24) |
| LLM check (recall over stale docs the reference check missed) | 1.00 (12/12) | 1.00 (12/12) |

Filtered flags (LLM said stale, claim check discarded it): 0 total, 0 of them on docs that really were stale.
Verifier rejected flags: 3 total, 0 of them on docs that really were stale.

False positive reasons (first seen):

- `12_non_function_symbols FP docs/api.md::Batch processing`: doc references no longer in code: name cache_ttl, name max_batch_size, name retry_limit

## Stage 4 (5 runs): all-identifier symbol index + mutual top-k pairing, 12 fixtures

2026-10-17 | provider `openai` model `gpt-4o` | embedder `text-embedding-3-small` | runs 5 | LLM calls used 152/400 | verifier on

| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors | Filtered | Verifier rejected |
|---|---|---|---|---|---|---|
| 01_wrong_path_missing_param | 1 | 5/5 | - | 0 | 0 | 0 |
| 02_removed_param | 1 | 5/5 | - | 0 | 0 | 0 |
| 03_changed_default | 1 | 5/5 | - | 0 | 0 | 0 |
| 04_deleted_function | 1 | 5/5 | - | 0 | 0 | 0 |
| 05_clean_match | 0 | 5/5 | - | 0 | 0 | 0 |
| 06_clean_reworded | 0 | 5/5 | - | 0 | 0 | 0 |
| 07_unrelated_docs | 0 | 5/5 | - | 0 | 0 | 0 |
| 08_large_corpus | 1 | 5/5 | - | 0 | 0 | 3 |
| 09_orders_corpus | 1 | 5/5 | - | 0 | 0 | 0 |
| 10_prose_claim | 1 | 5/5 | - | 0 | 0 | 0 |
| 11_stray_symbols | 0 | 5/5 | - | 0 | 0 | 0 |
| 12_non_function_symbols | 1 | 2/5 | FP docs/api.md::Batch processing (3/5) | 0 | 0 | 0 |

| Check | Precision | Recall |
|---|---|---|
| overall | 0.93 (40/43) | 1.00 (40/40) |
| reference check | 1.00 (20/20) | 0.50 (20/40) |
| LLM check (recall over stale docs the reference check missed) | 0.87 (20/23) | 1.00 (20/20) |

Filtered flags (LLM said stale, claim check discarded it): 0 total, 0 of them on docs that really were stale.
Verifier rejected flags: 3 total, 0 of them on docs that really were stale.

False positive reasons (first seen):

- `12_non_function_symbols FP docs/api.md::Batch processing`: The documentation mentions constraints and behaviors that are not present in the code.

## Stage 4 dogfood: README.md + CLAUDE.md vs src/shd (1 run)

`python -m shd.cli check --code src/shd --docs README.md --docs CLAUDE.md`, 49 code chunks, 5 doc sections, verifier on.

| Doc section | LLM pairs before (one-sided top-3) | LLM pairs after (mutual top-3/top-5) | Result |
|---|---|---|---|
| README.md::self-healing-docs | 30 | 3 | OK |
| CLAUDE.md::self-healing-docs | 28 | 5 | OK |
| CLAUDE.md::Run | 4 | 2 | OK |
| CLAUDE.md::Conventions | 51 | 5 | OK |
| CLAUDE.md::Assumptions | 49 | 5 | OK |
| total | 162 | 20 | 0 stale flags |

"Before" counts use the new all-identifier reference check (so `CLAUDE.md::Assumptions` is no longer skipped). First dogfood run, before Stage 4: 105 pairs, 3 stale flags (1 reference, 2 LLM), 4 filtered, 6 verifier-rejected.
After: 20 pairs, 0 stale flags, 1 filtered (it quoted the eval prompt instead of the doc), 0 verifier-rejected, 0 errors.

Pair counts on the 12 fixtures are identical before and after (max 3 pairs per doc), so the cap only matters on larger corpora.

## Stage 5 (5 runs): module context for drift check and verifier, 12 fixtures

2026-10-17 | provider `openai` model `gpt-4o` | embedder `text-embedding-3-small` | runs 5 | LLM calls used 165/400 | verifier on

| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors | Filtered | Verifier rejected |
|---|---|---|---|---|---|---|
| 01_wrong_path_missing_param | 1 | 5/5 | - | 0 | 0 | 0 |
| 02_removed_param | 1 | 5/5 | - | 0 | 0 | 0 |
| 03_changed_default | 1 | 5/5 | - | 0 | 0 | 0 |
| 04_deleted_function | 1 | 5/5 | - | 0 | 0 | 0 |
| 05_clean_match | 0 | 5/5 | - | 0 | 0 | 0 |
| 06_clean_reworded | 0 | 5/5 | - | 0 | 0 | 0 |
| 07_unrelated_docs | 0 | 5/5 | - | 0 | 0 | 0 |
| 08_large_corpus | 1 | 0/5 | FP docs/guide.md::Result pagination (5/5) | 0 | 0 | 0 |
| 09_orders_corpus | 1 | 5/5 | - | 0 | 0 | 5 |
| 10_prose_claim | 1 | 5/5 | - | 0 | 0 | 0 |
| 11_stray_symbols | 0 | 5/5 | - | 0 | 0 | 0 |
| 12_non_function_symbols | 1 | 5/5 | - | 0 | 0 | 0 |

| Check | Precision | Recall |
|---|---|---|
| overall | 0.89 (40/45) | 1.00 (40/40) |
| reference check | 1.00 (20/20) | 0.50 (20/40) |
| LLM check (recall over stale docs the reference check missed) | 0.80 (20/25) | 1.00 (20/20) |

Filtered flags (LLM said stale, claim check discarded it): 0 total, 0 of them on docs that really were stale.
Verifier rejected flags: 5 total, 0 of them on docs that really were stale.

False positive reasons (first seen):

- `08_large_corpus FP docs/guide.md::Result pagination`: The documentation mentions pagination with a next page link, but the code does not implement pagination.

## Stage 5 dogfood: README.md + CLAUDE.md vs src/shd (1 run, module context on)

49+ code chunks, 5 doc sections, 20 LLM pairs, verifier on.

| Metric | Value |
|---|---|
| stale flags | 0 |
| errors | 1 (`CLAUDE.md::Assumptions` x `detect.py::check_drift`: malformed output after retry, `confidence` was `""` on a non-stale answer) |
| filtered (claim not grounded) | 1 |
| verifier rejected | 1 |
| pairs per doc | Conventions 5, Assumptions 5, self-healing-docs (CLAUDE) 5, README 3, Run 2 |

The Stage 5 gate (fixtures 01-12 all 5/5 and dogfood 0 flags) was NOT met: 08 failed 0/5 and dogfood had 1 error. Stopped before Phase 5.

## Stage 6 (5 runs): verifier absence rule, confidence fix, stale/review tiers, 12 fixtures

2026-10-17 | provider `openai` model `gpt-4o` | embedder `text-embedding-3-small` | runs 5 | LLM calls used 161/400 | verifier on

Pass = every expected doc flagged in either tier AND no stale-tier false positive.

| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors | Filtered | Verifier rejected |
|---|---|---|---|---|---|---|
| 01_wrong_path_missing_param | 1 | 5/5 | - | 0 | 0 | 0 |
| 02_removed_param | 1 | 5/5 | - | 0 | 0 | 0 |
| 03_changed_default | 1 | 5/5 | - | 0 | 0 | 0 |
| 04_deleted_function | 1 | 5/5 | - | 0 | 0 | 0 |
| 05_clean_match | 0 | 5/5 | - | 0 | 0 | 0 |
| 06_clean_reworded | 0 | 5/5 | - | 0 | 0 | 0 |
| 07_unrelated_docs | 0 | 5/5 | - | 0 | 0 | 0 |
| 08_large_corpus | 1 | 5/5 | - | 0 | 0 | 1 |
| 09_orders_corpus | 1 | 3/5 | FP[stale] docs/api.md::Cancelling orders (2/5) | 0 | 0 | 3 |
| 10_prose_claim | 1 | 5/5 | - | 0 | 0 | 0 |
| 11_stray_symbols | 0 | 5/5 | - | 0 | 0 | 0 |
| 12_non_function_symbols | 1 | 5/5 | - | 0 | 0 | 0 |

| Tier / check | Precision | Recall | Note |
|---|---|---|---|
| **Stale tier** (reference + LLM flags naming a code element) | 0.95 (35/37) | 0.88 (35/40) |  |
| Review tier (LLM prose-only flags) | 1.00 (5/5) | 0.12 (5/40) | 5 flags over 5 runs; recall here = stale docs that landed only in this tier |
| Either tier | 0.95 (40/42) | 1.00 (40/40) | recall counts a detection in either tier |
| Reference check (stale tier) | 1.00 (20/20) | 0.50 (20/40) |  |
| LLM check, stale tier | 0.88 (15/17) | 0.75 (15/20) | recall over expected docs the reference check missed |

Filtered flags (claim not grounded): 0 total, 0 on docs that really were stale.
Verifier rejected flags: 4 total, 0 on docs that really were stale.

False positive reasons (first seen):

- `09_orders_corpus FP[stale] docs/api.md::Cancelling orders`: The documentation states that the 'reason' parameter is optional and empty by default, but the code specifies a default value of an empty string. | claim: 'Params: `reason` (optional, free text, empty by default)'

## Stage 6 dogfood: README.md + CLAUDE.md vs src/shd (1 run)

20 LLM pairs, verifier on.

| Metric | Value |
|---|---|
| stale-tier flags | 0 |
| review-tier flags | 0 |
| errors | 0 |
| filtered (claim not grounded) | 2 |
| verifier rejected | 0 |
| pairs per doc | Conventions 5, Assumptions 5, self-healing-docs (CLAUDE) 5, README 3, Run 2 |

Per the stopping rule, no further tuning rounds after Stage 6. Known remaining issue: fixture 09 `Cancelling orders` is a stale-tier false positive in 2 of 5 runs ("empty by default" vs `reason: str = ""`; the model treats an equivalent value as a conflict and the verifier agrees).

## Naming terms baseline (3 runs): + held-out fixture 13, before the fix

2026-10-17 | provider `openai` model `gpt-4o` | embedder `text-embedding-3-small` | runs 3 | LLM calls used 96/300 | verifier on

Pass = every expected doc flagged in either tier AND no stale-tier false positive.

| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors | Filtered | Verifier rejected |
|---|---|---|---|---|---|---|
| 01_wrong_path_missing_param | 1 | 3/3 | - | 0 | 0 | 0 |
| 02_removed_param | 1 | 3/3 | - | 0 | 0 | 0 |
| 03_changed_default | 1 | 3/3 | - | 0 | 0 | 0 |
| 04_deleted_function | 1 | 3/3 | - | 0 | 0 | 0 |
| 05_clean_match | 0 | 3/3 | - | 0 | 0 | 0 |
| 06_clean_reworded | 0 | 3/3 | - | 0 | 0 | 0 |
| 07_unrelated_docs | 0 | 3/3 | - | 0 | 0 | 0 |
| 08_large_corpus | 1 | 3/3 | - | 0 | 0 | 0 |
| 09_orders_corpus | 1 | 1/3 | FP[stale] docs/api.md::Cancelling orders (2/3) | 0 | 0 | 1 |
| 10_prose_claim | 1 | 3/3 | - | 0 | 0 | 0 |
| 11_stray_symbols | 0 | 3/3 | - | 0 | 0 | 0 |
| 12_non_function_symbols | 1 | 3/3 | - | 0 | 0 | 0 |
| 13_naming_terms | 1 | 0/3 | FP[stale] docs/api.md::Naming conventions (3/3); FP[stale] docs/api.md::Limitations (3/3) | 0 | 0 | 0 |

| Tier / check | Precision | Recall | Note |
|---|---|---|---|
| **Stale tier** (reference + LLM flags naming a code element) | 0.75 (24/32) | 0.89 (24/27) |  |
| Review tier (LLM prose-only flags) | 1.00 (3/3) | 0.11 (3/27) | 3 flags over 3 runs; recall here = stale docs that landed only in this tier |
| Either tier | 0.77 (27/35) | 1.00 (27/27) | recall counts a detection in either tier |
| Reference check (stale tier) | 0.71 (15/21) | 0.56 (15/27) |  |
| LLM check, stale tier | 0.82 (9/11) | 0.75 (9/12) | recall over expected docs the reference check missed |

Filtered flags (claim not grounded): 0 total, 0 on docs that really were stale.
Verifier rejected flags: 1 total, 0 on docs that really were stale.

False positive reasons (first seen):

- `09_orders_corpus FP[stale] docs/api.md::Cancelling orders`: The documentation states that the 'reason' parameter is optional and empty by default, but the code specifies a default value of an empty string. | claim: 'Params: `reason` (optional, free text, empty by default)'
- `13_naming_terms FP[stale] docs/api.md::Naming conventions`: doc references no longer in code: name camel_case, name kebab_case, name snake_case | claim: ''
- `13_naming_terms FP[stale] docs/api.md::Limitations`: doc references no longer in code: name camel_case, name kebab_case, name snake_case | claim: ''

## Naming terms fix (5 runs): 13 fixtures

2026-10-17 | provider `openai` model `gpt-4o` | embedder `text-embedding-3-small` | runs 5 | LLM calls used 172/400 | verifier on

Pass = every expected doc flagged in either tier AND no stale-tier false positive.

| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors | Filtered | Verifier rejected |
|---|---|---|---|---|---|---|
| 01_wrong_path_missing_param | 1 | 5/5 | - | 0 | 0 | 0 |
| 02_removed_param | 1 | 5/5 | - | 0 | 0 | 0 |
| 03_changed_default | 1 | 5/5 | - | 0 | 0 | 0 |
| 04_deleted_function | 1 | 5/5 | - | 0 | 0 | 0 |
| 05_clean_match | 0 | 5/5 | - | 0 | 0 | 0 |
| 06_clean_reworded | 0 | 5/5 | - | 0 | 0 | 0 |
| 07_unrelated_docs | 0 | 5/5 | - | 0 | 0 | 0 |
| 08_large_corpus | 1 | 5/5 | - | 0 | 0 | 1 |
| 09_orders_corpus | 1 | 4/5 | FP[stale] docs/api.md::Cancelling orders (1/5) | 0 | 0 | 5 |
| 10_prose_claim | 1 | 5/5 | - | 0 | 0 | 0 |
| 11_stray_symbols | 0 | 5/5 | - | 0 | 0 | 0 |
| 12_non_function_symbols | 1 | 5/5 | - | 0 | 0 | 0 |
| 13_naming_terms | 1 | 5/5 | - | 0 | 0 | 0 |

| Tier / check | Precision | Recall | Note |
|---|---|---|---|
| **Stale tier** (reference + LLM flags naming a code element) | 0.98 (40/41) | 0.89 (40/45) |  |
| Review tier (LLM prose-only flags) | 1.00 (5/5) | 0.11 (5/45) | 5 flags over 5 runs; recall here = stale docs that landed only in this tier |
| Either tier | 0.98 (45/46) | 1.00 (45/45) | recall counts a detection in either tier |
| Reference check (stale tier) | 1.00 (25/25) | 0.56 (25/45) |  |
| LLM check, stale tier | 0.94 (15/16) | 0.75 (15/20) | recall over expected docs the reference check missed |

Filtered flags (claim not grounded): 0 total, 0 on docs that really were stale.
Verifier rejected flags: 6 total, 0 on docs that really were stale.

False positive reasons (first seen):

- `09_orders_corpus FP[stale] docs/api.md::Cancelling orders`: The documentation states that the 'reason' parameter is optional and empty by default, but the code specifies a default value of an empty string. | claim: 'Params: `reason` (optional, free text, empty by default)'

## Naming terms fix dogfood: README.md + CLAUDE.md vs src/shd (1 run)

25 LLM pairs, verifier on, 8 doc sections (all got the reference check, all 8 reached the LLM).

| Metric | Value |
|---|---|
| stale-tier flags | 0 |
| review-tier flags | 0 |
| errors | 0 |
| filtered | 2 |
| verifier rejected | 2 |
| `README.md::Known limitations` (the section that tripped on `snake_case`) | OK |

Before the fix, the PR check flagged `snake_case` in `README.md::Known limitations`. An earlier dogfood run on a branch that also carried the `test: deliberate doc drift` commit (README mentioned a nonexistent `run_drift_scan()`) correctly flagged it as stale via the reference check (`name run_drift_scan`), and that commit is not part of this branch.
