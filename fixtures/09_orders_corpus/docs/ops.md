# Operations

## Configuration

Settings live in `config/settings.yaml`. Secrets such as `DATABASE_URL` come from the environment. Tune the pool with `max_connections` and `request_timeout` in the same file.

## Logging

Application logs are written to `/var/log/orders/app.log`. Rotate them with `logrotate` and read them with `tail -f`.

## Backups

Dump the database nightly with `pg_dump` and copy the file to `backups/nightly.sql`. Restore with `psql`.

## Local development

Start the stack with `docker compose up`, then run the suite with `make test`. Use `pip install -r requirements.txt` for the Python side.

## Deployment

Build the image in CI and deploy it behind the load balancer. Set `LOG_LEVEL` to `warning` in production and keep `debug_mode` off.

## Troubleshooting

If orders stall, check the worker queue first. Restart workers with `systemctl restart orders-worker` if the queue is not draining.
