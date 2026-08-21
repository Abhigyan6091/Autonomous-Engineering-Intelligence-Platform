# Checkout API Performance Runbook

## Latency Budget

- p50 target: < 50ms
- p95 target: < 200ms (SLA threshold)
- p99 target: < 400ms

## Checkout p95 Regression Checklist

1. **Check recent deployments**: `git log --oneline HEAD~10`
2. **Verify database indexes**: Run `EXPLAIN ANALYZE` on inventory queries
   - Specifically check `ix_inventory_items_product_id` exists
   - `SELECT * FROM pg_indexes WHERE tablename = 'inventory_items';`
3. **Check for N+1 queries**: Review `checkout_service.py` inventory loop
4. **Verify connection pool health**: Check `DB_POOL_SIZE` config (default: 10)
5. **Check third-party payment gateway latency** (Stripe dashboard)

## Known Issues

- **INC-2023-0042**: Removing product_id index causes sequential scan on 45k+ rows.
  Fix: `CREATE INDEX CONCURRENTLY ix_inventory_items_product_id ON inventory_items(product_id);`
