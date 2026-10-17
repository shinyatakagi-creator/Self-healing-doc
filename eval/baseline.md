# Eval baseline

2026-10-17 | provider `openai` model `gpt-4o` | embedder `text-embedding-3-small` | runs 3 | LLM calls used 24/60

| Scenario | Expected stale | Pass rate | Wrong (runs) | Errors |
|---|---|---|---|---|
| 01_wrong_path_missing_param | 1 | 3/3 | - | 0 |
| 02_removed_param | 1 | 3/3 | - | 0 |
| 03_changed_default | 1 | 3/3 | - | 0 |
| 04_deleted_function | 1 | 3/3 | - | 0 |
| 05_clean_match | 0 | 3/3 | - | 0 |
| 06_clean_reworded | 0 | 3/3 | - | 0 |
| 07_unrelated_docs | 0 | 3/3 | - | 0 |
| 08_large_corpus | 1 | 0/3 | FP docs/guide.md::Result pagination (3/3); FP docs/guide.md::Searching these docs (3/3) | 0 |

| Check | Precision | Recall |
|---|---|---|
| overall | 0.71 (15/21) | 1.00 (15/15) |
| reference check | 1.00 (9/9) | 0.60 (9/15) |
| LLM check (recall over stale docs the reference check missed) | 0.50 (6/12) | 1.00 (6/6) |

False positive reasons (first seen):

- `08_large_corpus FP docs/guide.md::Result pagination`: The documentation does not mention the '/v2/search' route or the 'query' and 'limit' parameters.
- `08_large_corpus FP docs/guide.md::Searching these docs`: The documentation does not mention the '/v2/search' API endpoint or its parameters.
