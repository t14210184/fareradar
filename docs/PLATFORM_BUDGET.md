# Platform Budget

The Free operating profile treats the one-minute Cron as a dispatcher. Critical reserve is preserved for P0 ingest, outbox, heartbeat, and policy/terms safety checks. Full-table scans are forbidden on critical paths.
