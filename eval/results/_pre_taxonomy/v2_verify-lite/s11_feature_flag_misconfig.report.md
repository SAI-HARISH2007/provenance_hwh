# Incident Report: orders-api ValidationError Spike

## Summary
At 2026-08-30T03:12:00.000Z, `orders-api` began failing `order_create` requests with a 27% error rate due to `ValidationError`s. The root cause is the rollout of the `new_pricing_engine` feature flag to 100%, which incorrectly calculates totals for carts with `coupon_type=percentage_stacked`, resulting in a negative total and subsequent validation failure.

## Timeline
- **2026-08-30T02:53:00.000Z**: Feature flag `new_pricing_engine` scaled from 20% to 100% by sam.
- **2026-08-30T02:54:32.000Z**: First `ValidationError` logged in `orders-api` (`negative total for cart with coupon_type=percentage_stacked`).
- **2026-08-30T03:12:00.000Z**: P2 Alert fires indicating `orders-api` `order_create` has 27% errors.

## Root Cause
Feature flag misconfiguration / bug in `new_pricing_engine` pricing calculation logic when stacking percentage coupons, producing negative cart totals.

## Evidence
- `query_logs` shows continuous `ValidationError: negative total for cart with coupon_type=percentage_stacked` explicitly tagging `pricing_engine=new`.
- `get_metrics` (`error_rate_pct`) shows error rate jumping from ~0.4% baseline to ~27% right at the 02:53 flag rollout.
- `recent_changes` shows `new_pricing_engine` moved to 100% at 02:53.
- `run_probe` verified service process is running and healthy.

## Proposed Remediation
Disable the faulty feature flag (`new_pricing_engine`) to revert pricing calculation to the stable engine. This is safe, immediate, and targets the exact mechanism causing the validation errors.

## Follow-ups
1. Fix the `new_pricing_engine` calculation logic for `percentage_stacked` coupons so totals cannot become negative.
2. Add comprehensive unit test coverage for coupon stacking in the pricing engine.