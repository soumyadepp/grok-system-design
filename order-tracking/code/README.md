# Order Tracking System — Code

Pure Python implementation of the Order Tracking System design.
No external dependencies. Python 3.9+ only.

## Run

```bash
python order_tracking.py
```

## Expected Output

10 scenarios execute with assertions. On success:

```
────────────────────────────────────────────────────────────
  Scenario A: Happy path (PENDING → DELIVERED)
────────────────────────────────────────────────────────────
  Order : <id>…
  State : DELIVERED
  Total : INR 510.00
  ETA   : 0 min
  Events (7): ...
  [PASS] Scenario A

... (B through J) ...

────────────────────────────────────────────────────────────
  Results: 10/10 scenarios passed
────────────────────────────────────────────────────────────
  All scenarios passed.
```

## Scenario Coverage

| # | Scenario | What it verifies |
|---|---|---|
| A | Happy path | Full PENDING → DELIVERED traversal; ETA = 0 at delivery |
| B | Cancellation | CONFIRMED → CANCELLED; inventory released |
| C | Failed delivery + retry | FAILED_DELIVERY → retry → RETURNED; agent released |
| D | Inventory stockout | Guard blocks PENDING → CONFIRMED; order stays PENDING |
| E | Illegal transition | DELIVERED → PENDING raises InvalidTransitionError |
| F | Double agent assignment | Second assign raises AgentNotAvailableError |
| G | Customer order history | Returns all orders for a customer, sorted newest-first |
| H | Admin state filter | list_by_state(CANCELLED) returns correct subset |
| I | ETA monotonic | ETA strictly decreases along the happy-path state sequence |
| J | Notification log | At least 7 notifications created for the happy-path order |

## Architecture (in-process)

```
OrderService          — primary orchestrator; place, transition, assign, history
TrackingService       — status query, ETA, admin listing
OrderStateMachine     — validates transitions; runs guards; emits OrderEvent
InventoryService      — check + reserve + release + consume
NotificationService   — creates Notification records on every transition
DeliveryAgentService  — assign agent; enforce one-active-order constraint

Repositories          — in-memory dicts; swap for DB adapters in production
ETAStrategy (ABC)     — pluggable ETA calculation; default: SimpleETAStrategy
```

## Extending

**New order state:**
1. Add to `OrderState` enum
2. Add entry in `TRANSITIONS` dict
3. Add duration in `_STATE_DURATION` (if on the happy path)

**New notification channel:**
1. Add to `NotificationChannel` enum
2. Extend `NotificationService._format()` or add a dispatch method

**New guard:**
```python
def my_guard(order: Order, **kwargs) -> Tuple[bool, str]:
    return True, ""  # or (False, "reason")

state_machine.register_guard(OrderState.X, OrderState.Y, my_guard)
```

**Production swap-ins:**
- Repositories → SQLAlchemy models (PostgreSQL)
- NotificationService → Kafka producer / SQS publisher
- ETAStrategy → ML-based ETA from historical delivery data
- AgentService → Redis-locked assignment for distributed safety
