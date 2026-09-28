# Incident Report: orders-api ValidationError spike

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for `orders-api` indicating a 27% error rate consisting of `ValidationError` exceptions during order creation. The root cause was traced to rolling out the `new_pricing_engine` feature flag to 100%.

## Timeline
- **2026-08-30T02:53:00.000Z**: `new_pricing_engine` feature flag increased from 20% to 100% by sam.
- **2026-08-30T02:58:55.000Z**: First `ValidationError` due to negative total with `coupon_type=percentage_stacked` logged.
- **2026-08-30T03:12:00.000Z**: Alert fires indicating elevated error rates on `orders-api` and `api-gateway`.

## Root Cause
The new pricing engine calculates stacked percentage coupons incorrectly, resulting in a negative total amount for carts, which triggers validation failures upon order creation.

## Evidence
- Config change: `orders-api: new_pricing_engine 20% -> 100%`
- Log entries: `ERROR orders-api: pricing_engine=new ValidationError: negative total for cart with coupon_type=percentage_stacked`

## Remediation
Disable or roll back the `new_pricing_engine` feature flag on the `orders-api` service.

## Follow-ups
1. Fix the calculation bug in `new_pricing_engine` regarding `percentage_stacked` coupons.
2. Add unit tests covering stacked percentage coupons under the new pricing logic before re-enabling.