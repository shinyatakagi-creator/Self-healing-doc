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
