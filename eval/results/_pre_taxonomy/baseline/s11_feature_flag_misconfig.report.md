# Incident Report: orders-api Error Spike

## Summary
At 2026-08-30T03:12:00.000Z, `orders-api` experienced a spike in error rates (~26-28%) returning `ValidationError` responses during order creation. The root cause was traced to rolling out the `new_pricing_engine` feature flag to 100%, which calculates negative cart totals for certain percentage stacked coupons.

## Timeline
- **2026-08-30T02:53:00.000Z**: Feature flag `new_pricing_engine` rolled out from 20% to 100% by sam.
- **2026-08-30T02:58:55.000Z**: First `ValidationError` due to negative total logged.
- **2026-08-30T03:12:00.000Z**: Alert fires indicating 27% error rate on `order_create`.

## Root Cause
Feature flag misconfiguration / buggy pricing logic (`new_pricing_engine`) producing negative cart totals with `coupon_type=percentage_stacked` when applied globally.

## Evidence
- Config change audit: `orders-api: new_pricing_engine 20% -> 100%`
- Log output: `ERROR orders-api: pricing_engine=new ValidationError: negative total for cart with coupon_type=percentage_stacked`

## Remediation
Disable the faulty feature flag (`new_pricing_engine`) on `orders-api`.

## Follow-ups
1. Fix pricing engine bug handling stacked percentage coupons.
2. Add unit tests for percentage stacked coupons under the new pricing engine.