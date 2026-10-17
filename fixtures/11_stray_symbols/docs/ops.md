# Operations

## Environment

Set `DATABASE_URL` and `REPORT_BUCKET` before starting. Override the worker count with `max_workers` in the config file.

## Command line

Run `shd --dry-run --max-retries 3` to preview an export. Use `--output-dir` to choose where files go.

## Files

Settings live in `config/app_settings.yaml` and raw input is read from `data/raw_events.csv`. Helpers are in `src/export_utils.py`. Temporary exports go to `/tmp/export_cache` and the binary is installed at `/usr/local/bin/shd`.

## Links

Setup notes are at https://example.com/v1/docs/setup. The status page is `https://status.example.com/v2/health`.

## Retries

`retry_count` controls how many times a failed export is retried and `backoff_seconds` sets the pause between attempts.

## Scheduling

Reports are generated nightly. Set `cron_expression` to change the schedule, and `SCHEDULER_TZ` for the time zone.
