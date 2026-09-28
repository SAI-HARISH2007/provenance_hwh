# Incident Report

**Summary**
- Worker service entered a restart loop (9 restarts in 12 min) and job queue backlog grew to 4,300 jobs.
- Alert fired at 2026‑08‑30T03:12:00Z.

**Timeline**
- 2026‑08‑30T02:14:00Z – `data-import` service deployed `importer-2.4.0` which changed job payload handling to inline source rows as base64 with **no size cap** (912 MB payload created).
- 2026‑08‑30T03:00:36Z – Worker logs first `OOMKilled (exit 137) while decoding payload job=job_8f3a1c size=912MB`.
- 03:00‑03:12 – Repeated OOM kills cause worker to restart repeatedly, leading to backlog.

**Root Cause**
- The `data-import` change produced excessively large job messages (≈912 MB). The worker process attempts to decode these payloads, exhausting its memory and being killed by the OOM killer. This triggers the observed restart loop and backlog.

**Evidence**
1. **Alert** – worker in degraded state, restart loop, large backlog.
2. **Recent Changes** – `data-import` deploy introduced unbounded inlining of rows, creating a 912 MB job payload.
3. **Worker Logs** – multiple `ERROR` entries: `OOMKilled (exit 137) while decoding payload job=job_8f3a1c size=912MB`.
4. **Health Probe** – `/healthz` reports last job failed 9 times with payload 912 MB, confirming OOM condition.

**Proposed Remediation (Safe)**
- **Rollback the `data-import` deployment** (`importer-2.4.0`) to the previous version that used S3 references for large payloads. This instantly stops creation of oversized job messages, allowing the worker to process remaining jobs without OOM.
- After rollback, monitor the worker restarts and backlog; they should clear as workers resume normal operation.
- Long‑term: add a payload size limit or revert to external storage for large data to prevent recurrence.

**Follow‑ups**
- Verify that the `data-import` service no longer emits >100 MB job messages.
- Add a monitoring alert on worker memory usage and job payload size.
- Consider implementing a feature flag to cap payload size before future releases.

**Root Cause Label**: `memory_leak_oom`
**Service where cause lives**: `data-import`
**Target for action**: `data-import`