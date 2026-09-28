# Incident Report: orders-api ValidationError spike

## Summary
At 2026-08-30T03:12:00.000Z, the `orders-api` experienced a spike in error rates (~27%) returning ValidationErrors (`negative total for cart with coupon_type=percentage_stacked`) after the `new_pricing_engine` feature flag was rolled out to 100%.

## Timeline
- **2026-08-30T02:53:00Z**: Feature flag `new_pricing_engine` rolled out from 20% to 100% by sam.
- **2026-08-30T02:58:55Z**: First `ValidationError` logged due to negative cart totals.
- **2026-08-30T03:12:00Z**: Alert fires indicating 27% error rate on `orders-api`.

## Root Cause
The `new_pricing_engine` feature flag calculation logic introduced a bug when applied to carts with `percentage_stacked` coupons, resulting in negative totals and triggering validation errors.

## Evidence
- Feature flag change audit: `new_pricing_engine 20% -> 100%` at `02:53:00Z`.
- Error logs: `ERROR orders-api: pricing_engine=new ValidationError: negative total for cart with coupon_type=percentage_stacked`.
- Metric jump: `orders-api.error_rate_pct` climbed from ~0.4% to ~26-28% immediately following the change.

## Remediation
Disable or roll back the `new_pricing_engine` feature flag on `orders-api`.

## Follow-ups
1. Fix the calculation logic in `new_pricing_engine` to handle `percentage_stacked` coupons correctly.
2. Add unit tests for edge cases combining stacking coupons and the new pricing engine.