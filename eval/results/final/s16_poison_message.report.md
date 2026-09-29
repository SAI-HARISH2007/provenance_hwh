# Incident Report: Worker Restart Loop / OOMKilled

## Summary
The background worker service entered a persistent restart loop due to repeated `OOMKilled` (exit 137) errors. A recently deployed data importer change (`importer-2.4.0`) attached a 912MB source export inline as base64 within a single job message without a size cap. Whenever the worker attempts to decode this oversized payload (`job_8f3a1c`), memory consumption spikes to 102%, exhausting container memory and causing an OOM kill. The failed job is then retried endlessly, blocking the queue and crashing the worker repeatedly.

## Timeline
- **02:14 UTC**: `data-import` deployed version `importer-2.4.0`, changing data export to attach source rows inline as base64 (912MB export).
- **02:47 UTC**: `worker` deployed version `worker-1.3.1` (structured logging, unrelated to decoding).
- **03:00 UTC**: First `OOMKilled` logged on `worker` while decoding payload `job_8f3a1c` (912MB).
- **03:12 UTC**: PagerDuty alert fires: worker restart loop (9 restarts in 12 min, job queue backlog 4,300).
- **03:15 UTC**: Investigation confirms memory exhaustion due to oversized base64 payload in the job queue.

## Root Cause
- **Root Cause**: `poison_message`
- **Explanation**: An oversized 912MB job payload (`job_8f3a1c`) injected into the queue by the new data-import mechanism acts as a poison message, crashing the worker with an Out-Of-Memory error on every processing attempt.

## Evidence
- `recent_changes`: `importer-2.4.0` inlined a 912MB export into a single job message.
- `query_logs`: Repeated `ERROR worker: OOMKilled (exit 137) while decoding payload job=job_8f3a1c size=912MB`.
- `get_metrics`: `worker.mem_pct` climbs up to 102.39% coinciding with the OOM crashes.
- `run_probe`: Health check confirmed process is up briefly (`up 41 s`) and reported `last job job_8f3a1c failed 9 times; payload 912MB`.

## Proposed Remediation
- **Action**: `rollback_deploy` (Roll back `data-import` from version `importer-2.4.0` to prevent further inline generation of oversized 912MB payloads, and purge the existing poison message `job_8f3a1c` from the queue).
