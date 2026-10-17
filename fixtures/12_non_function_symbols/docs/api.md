# Batch API

## Batch processing

`POST /v1/batches` runs `process_batch(items)`. At most `max_batch_size` items are accepted. Failed items are retried up to `retry_limit` times and results are cached for `cache_ttl` seconds.

## Flushing

Call `flush_buffer()` after a batch to release memory.
