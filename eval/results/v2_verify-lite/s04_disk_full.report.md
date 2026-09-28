### Incident Report: Orders API Failures Due to Disk Full on PostgreSQL

#### Summary
At 2026-08-30T03:12:00.000Z, a P1 page fired for `orders-api` due to an order creation failure rate of ~58%. Investigation revealed that PostgreSQL ran out of disk space (`100% used`), causing database writes to fail with `could not extend file` errors.

#### Timeline
- **2026-08-30T01:02:00.000Z**: `log_min_duration_statement=0` was enabled on PostgreSQL for slow-query investigation, causing every single SQL query to be logged.
- **2026-08-30T02:47:16.000Z**: `orders-api` begins failing database inserts (`could not extend file "base/16384/2619"`).
- **2026-08-30T02:52:00.000Z**: Inventory-api deploy (`inventory-1.9.3`) occurs (unrelated to root cause).
- **2026-08-30T03:12:00.000Z**: P1 alert fires for `orders-api` error rate.

#### Root Cause
`disk_full`: The PostgreSQL data/log disk filled up completely (100% used, 200GB/200GB) because query logging was set to verbose (`log_min_duration_statement=0`), generating 96GB of logs growing at 1.1GB/min and exhausting available disk space.

#### Evidence
- **Logs**: `orders-api` logs showed persistent `insert failed: could not extend file "base/16384/2619"` errors.
- **Probe**: Disk probe on `postgres` returned `100% used (200G/200G); /var/lib/postgresql/log = 96G, growing 1.1G/min`.
- **Changes**: `recent_changes` confirmed `log_min_duration_statement=0` was enabled earlier.

#### Proposed Remediation
1. Free disk space on PostgreSQL by clearing/truncating excess database logs and disabling `log_min_duration_statement` or reverting config.
2. Safe because it directly addresses the resource exhaustion without impacting data integrity or restarting stateful engines.

#### Follow-ups
- Revert or adjust `log_min_duration_statement` so query logging is scoped to slow queries only.
- Set up disk space monitoring and alerting for PostgreSQL storage usage.