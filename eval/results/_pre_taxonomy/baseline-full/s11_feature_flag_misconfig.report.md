# Incident Report: orders-api Validation Errors

## Summary
At 2026-08-30T03:12:00Z, the `orders-api` service reported a 27% error rate spike characterized by `ValidationError` messages. The incident correlates directly with the full rollout of the `new_pricing_engine` feature flag.

## Timeline
- **2026-08-30T02:53:00.000Z**: Feature flag `new_pricing_engine` scaled from 20% to 100%.
- **2026-08-30T02:58:55.000Z**: First `ValidationError` logged in `orders-api` (`negative total for cart with coupon_type=percentage_stacked`).
- **2026-08-30T03:12:00.000Z**: Alert fires indicating `order_create` 27% error rate.

## Root Cause
A bug in the newly rolled-out pricing engine (`new_pricing_engine`) calculates a negative total for carts utilizing `percentage_stacked` coupons, triggering request validation failures upon order creation.

## Evidence
- Feature flag audit logs show rollout to 100% immediately preceding the error spike.
- `orders-api` error logs show repeated exceptions: `ValidationError: negative total for cart with coupon_type=percentage_stacked`.
- `orders-api.error_rate_pct` metric jumped from <0.5% to ~27%.

## Remediation
1. Disable the `new_pricing_engine` feature flag or rollback its rollout percentage.

## Follow-ups
- Fix the pricing calculation logic to prevent negative totals when `percentage_stacked` coupons are applied.
- Add unit/integration test coverage for stacked percentage discounts in the new pricing engine.