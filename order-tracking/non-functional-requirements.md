# Non-Functional Requirements — Order Tracking System

## Scale Targets

| Metric | Average | Peak |
|---|---|---|
| Registered customers | 10 million | — |
| Active merchants | 500,000 | — |
| Orders per minute | 5,000 | 50,000 (flash sale) |
| Orders per second | ~83 | ~833 |
| State transitions per second | ~580 (7 avg per order) | ~5,800 |
| Status query QPS | ~830 (10:1 read:write) | ~8,300 |

## Latency SLAs

| Operation | p50 | p99 |
|---|---|---|
| Order placement | < 50 ms | < 200 ms |
| Status query (cache hit) | < 5 ms | < 20 ms |
| Status query (cache miss) | < 30 ms | < 100 ms |
| State transition | < 30 ms | < 100 ms |
| ETA query | < 5 ms | < 15 ms |

## Availability

| Path | Target |
|---|---|
| Status query (read path) | 99.99% (< 53 min downtime/year) |
| Order placement (write path) | 99.9% (< 8.7 hr downtime/year) |
| Notification delivery | 99.5% (best-effort, async) |

## Durability

- Zero order loss after placement acknowledgement
- Every state transition persisted before ACK returned to caller
- Full audit trail: every transition records actor, timestamp, reason

## Storage Estimation

```
Per order:
  orders row:        ~500 B
  order_items (×5):  ~1,000 B
  order_events (×8): ~2,400 B
  notifications (×8):~1,600 B
  Total:             ~5.5 KB per order

Daily:
  83 orders/s × 86,400 s = ~7.2M orders/day
  7.2M × 5.5 KB = ~39.6 GB/day

90-day hot storage:  ~3.6 TB  (primary + replica RDS)
Archival (> 90 days): S3, ~$20/TB/month
```

## Bandwidth Estimation

```
Inbound writes:  833 orders/s × 2 KB = ~1.7 MB/s peak
Outbound reads:  8,300 queries/s × 5.5 KB = ~45 MB/s peak
  → With Redis cache (95% hit rate): ~2.3 MB/s origin load
```

## Consistency Model

| Operation | Consistency Required |
|---|---|
| State machine transitions | Strong (no split-brain on order state) |
| Inventory reservation | Strong (SELECT FOR UPDATE) |
| Status reads | Eventual (read from replica + cache OK) |
| Notification delivery | Eventual (at-least-once via queue) |

## Technology Choices (production)

| Component | Choice | Rationale |
|---|---|---|
| Order DB | PostgreSQL | ACID for state machine; JSONB for flexible metadata |
| Cache | Redis | Sub-ms reads; SETNX for agent assignment locks |
| Message bus | Kafka | Ordered by order_id partition; replay for audit |
| API layer | REST + JSON | Universal compatibility |
| Delivery tracking | 30s location push (polling) | Simple; WebSocket upgrade path clear |
| Archival | S3 + Parquet | Cheap; queryable via Athena for analytics |

## Observability

- Full append-only event log per order (actor, from_state, to_state, timestamp, reason)
- Metrics: order placement rate, transition latency per state, cancellation rate, failed delivery rate
- Alerts: cancellation rate > 5%, failed delivery rate > 2%, p99 placement latency > 500ms

## Extensibility

- New order states: add to enum + TRANSITIONS dict + ETA duration table
- New notification channels: extend channel enum + send dispatcher
- New actor types: extend ActorType enum + guard functions
- Multi-region: shard by customer region; cross-region replication for tracking reads
