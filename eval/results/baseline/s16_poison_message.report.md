# Incident Report: Worker Restart Loop Caused by Poison Message

## Summary
At 2026-08-30T03:12:00.000Z, the `worker` service entered a restart loop experiencing 9 restarts in 12 minutes with a growing job queue backlog of 4,300 jobs. The root cause is a poisoned message (`job_8f3a1c`) containing a 912MB inlined payload from a recent `data-import` deployment change, which exhausts the worker container's memory during decoding and triggers an OOM kill.

## Timeline
- **2026-08-30T02:14:00Z**: `data-import` deployed with inline base64 source rows (no size cap).
- **2026-08-30T03:06:54Z**: First observed OOMKilled event while decoding 912MB job `job_8f3a1c`.
- **2026-08-30T03:12:00Z**: Alert fires: worker restart loop (9 restarts in 12 min).

## Root Cause
A massive 912MB job payload was pushed into the `bulk-import` queue due to an unbounded inlining change. Whenever any worker picks up `job_8f3a1c`, decoding the payload consumes all available memory, causing an OOM kill (`exit 137`) and redelivery back to the queue, resulting in a persistent restart loop.

## Evidence
- `[deploy] data-import: importer-2.4.0: attach source rows inline as base64 instead of an S3 ref (no size cap)`
- `ERROR worker: OOMKilled (exit 137) while decoding payload job=job_8f3a1c size=912MB`
- `worker: mem_pct: now 102.399, restarts: now 9`

## Remediation
1. Update the worker config to skip or drop the offending job ID (`SKIP_JOB_IDS: ['job_8f3a1c']`) or set a strict payload size limit (`MAX_PAYLOAD_BYTES`).
2. Restart the worker service to clear the loop and resume processing healthy jobs.

## Follow-ups
- Revert or fix `importer-2.4.0` to use S3 references rather than inline base64 payloads for large exports.
- Implement payload size validation at the queue ingestion layer.