# Incident Report

**Summary**
- The `worker` service entered a restart loop (9 restarts in 12 min) and accumulated a backlog of ~4,300 jobs.

**Timeline**
- **02:14 UTC** – `data-import` service deployed `importer-2.4.0` which changed job creation to inline source rows as a base64 payload with no size cap (first export 912 MB).
- **02:45‑03:12 UTC** – `worker` processes began receiving these massive payloads. Logs show repeated `OOMKilled (exit 137)` errors while decoding a 912 MB job.
- **03:00‑03:12 UTC** – Memory usage metric for `worker` rose from ~50 % to >100 %, confirming OOM conditions.
- **03:12 UTC** – Alert fired: *worker restart loop*.

**Root Cause**
- The `data-import` change caused jobs to contain extremely large (≈ 912 MB) payloads. The `worker` service, which decodes these payloads, ran out of memory and was killed by the kernel, leading to rapid restarts and a processing backlog.

**Evidence**
- Alert payload (service `worker`, degraded status).
- Recent change log showing the inlining change.
- `worker` error logs: `OOMKilled (exit 137) while decoding payload job=... size=912MB` repeated.
- Memory usage metric: peak `mem_pct` 102.4 %.
- HTTP health probe of `worker` reports last job failed 9 times due to 912 MB payload.

**Proposed Remediation (Safe)**
- **Rollback the `data-import` deployment** to the previous version that used S3 references for large rows. This removes the unbounded payload size, preventing workers from OOM.
- The rollback is a read‑only action (no state loss) and does not require restarting stateful services.

**Follow‑ups**
- Add a size guard on job payloads in `data-import` to reject >200 MB before enqueuing.
- Implement back‑pressure or circuit‑breaker in `worker` to gracefully reject oversized jobs.
- Review job size limits in CI for future changes.

**Root Cause Label**: `memory_leak_oom`
**Service where cause lives**: `data-import`
**Summary**: Worker OOM caused by oversized job payload from data-import change.
**Target for action**: `data-import`