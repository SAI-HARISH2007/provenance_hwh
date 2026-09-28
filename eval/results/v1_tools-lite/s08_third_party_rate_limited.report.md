# Incident Report: payments-api Rate Limited by PayGate Vendor

## Summary
At 2026-08-30T03:12:00.000Z, `payments-api` began failing 38% of charges due to HTTP 429 (Too Many Requests) errors from the PayGate vendor API. Investigation revealed that a one-off refund backfill job deployed in `worker` (`worker-1.4.1`) at 02:46:00.000Z overwhelmed the shared PayGate API rate limit (600 requests/minute), starving legitimate payment traffic from `payments-api`.

## Timeline
- **02:46:00.000Z**: `worker` (`worker-1.4.1`) deployed with a one-off refund backfill job (18k refunds) at concurrency 32, sharing the production API key.
- **02:47:28.000Z**: `payments-api` logs first `429 Too Many Requests` error from PayGate.
- **03:12:00.000Z**: P2 page fires as `payments-api` charge failure rate hits 38%.
- **03:12:00Z+**: Investigation confirms `worker` backfill has consumed 100% of the PayGate rate limit (92% of calls coming from `worker/1.4.1`).

## Root Cause
`third_party_rate_limited`: The background worker job (`worker-1.4.1`) flooded the third-party payment gateway (`PayGate`) with refund requests using the shared production API key, exhausting the 600 requests/minute rate limit and causing `payments-api` charges to fail with HTTP 429 errors.

## Evidence
- **Alert**: `payments-api` reporting `charge_failed 38% (HTTP 429 from vendor)`.
- **Recent Changes**: `worker-1.4.1` deployed at 02:46:00.000Z with backfill job calling PayGate directly sharing production key.
- **Logs**: `payments-api` error logs showing continuous `paygate 429 Too Many Requests retry-after=30 (limit 600/min for key pk_live_…c9)` starting at 02:47:28.000Z.
- **Probe**: `run_probe` to `https://api.paygate.example` confirmed vendor is healthy, but rate-limit dashboard showed key `…c9` at 100% capacity with 92% of calls originating from `worker/1.4.1`.

## Proposed Remediation
Enable the circuit breaker on `payments-api` (`enable_circuit_breaker`) and/or pause the worker backfill job to protect the payment gateway quota and allow legitimate customer transactions to proceed.
