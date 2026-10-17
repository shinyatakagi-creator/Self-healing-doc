# Search API

## Naming conventions

This project uses `snake_case` for functions such as `run_search(query)`, never `camel_case` or `kebab_case`. Writing snake_case or camel_case in plain prose is just talking about style.

## Limitations

The checker verifies names written as `snake_case` identifiers or as calls. Words like `kebab_case` and `camel_case` describe a style, not code. See `POST /v1/search`.

## Cleanup

Call `purge_cache()` after every search to free memory.
