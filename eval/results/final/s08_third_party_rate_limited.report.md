# Incident Report: payments-api HTTP 429 Rate-Limited by Vendor

## Summary
At 2026-08-30T03:12:00Z, `payments-api` began failing 38% of charge requests due to HTTP 429 (Too Many Requests) responses from the external payment gateway (`api.paygate.example`). Investigation revealed that a background worker refund backfill job was aggressively calling PayGate directly using the shared production API key, exhausting the rate limit quota.

## Timeline
- **2026-08-30T02:46:00Z**: `worker` version `worker-1.4.1` deployed with a one-off refund backfill job (18k refunds) at concurrency 32, calling PayGate directly with the production API key.
- **2026-08-30T03:12:00Z**: Alert fires: `payments-api` experiences 38% charge failures due to HTTP 429s from vendor.

## Root Cause
Third-party rate limited (`third_party_rate_limited`). The payment gateway rate limit quota (600 req/min) was saturated by the concurrent refund backfill job running in the worker service (`worker-1.4.1`).

## Evidence
1. **Alert**: `payments-api` reporting `charge_failed 38% (HTTP 429 from vendor)`.
2. **Recent Changes**: `worker-1.4.1` deployed at 02:46 UTC with a one-off refund backfill job (18k refunds) at concurrency 32.
3. **Probe**: `run_probe` confirmed rate-limit dashboard showed API key at 100% of 600/min, with 92% of calls from user-agent `worker/1.4.1`.

## Proposed Remediation
No automated action available via tool definitions; escalate to owner (priya) to pause the backfill job.
Target: `worker`.