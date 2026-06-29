# Functional Requirements — Order Tracking System

## Actors

| Actor | Description |
|---|---|
| **Customer** | Places orders, tracks status, views history |
| **Merchant** | Confirms orders, updates preparation status |
| **Delivery Agent** | Picks up orders, marks delivered/failed |
| **Admin** | Views all orders, filters by state, overrides |
| **System** | Auto-transitions on timeout, sends notifications |

---

## Use Cases

### Customer
- FR-1: Place an order with items, quantities, and delivery address
- FR-2: View current order status and full event history
- FR-3: Cancel an order (allowed in PENDING or CONFIRMED states only)
- FR-4: View all past orders (order history)
- FR-5: Get ETA for current order

### Merchant
- FR-6: Confirm a pending order (triggers inventory reservation)
- FR-7: Mark order as PREPARING once started
- FR-8: Mark order as READY_FOR_PICKUP when packaged
- FR-9: Cancel an order before preparation begins

### Delivery Agent
- FR-10: Accept assignment for a READY_FOR_PICKUP order
- FR-11: Mark order as DELIVERED upon successful handoff
- FR-12: Mark order as FAILED_DELIVERY if customer unavailable
- FR-13: Retry delivery (FAILED_DELIVERY → OUT_FOR_DELIVERY)
- FR-14: Mark as RETURNED if delivery cannot be completed

### Admin
- FR-15: View all orders, filter by state
- FR-16: Assign a delivery agent to an order
- FR-17: Override order state with reason

### System
- FR-18: Decrement inventory on order confirmation; restore on cancellation
- FR-19: Send notifications (EMAIL/SMS/PUSH) on every state transition
- FR-20: Reject invalid state transitions with descriptive error

---

## Order State Machine

```
                    ┌─────────┐
              ┌────▶│CANCELLED│◀────────────┐
              │     └─────────┘             │
              │                             │
         ┌────┴────┐    ┌───────────┐   ┌──┴───────┐
 START──▶│ PENDING ├───▶│ CONFIRMED ├──▶│PREPARING │
         └─────────┘    └─────────┬─┘   └────┬─────┘
                                  │           │
                                  ▼           ▼
                              ┌───────────────────┐
                              │  READY_FOR_PICKUP │
                              └─────────┬─────────┘
                                        │
                                        ▼
                              ┌──────────────────┐
                         ┌───▶│ OUT_FOR_DELIVERY │◀──┐
                         │    └────────┬─────────┘   │
                         │             │              │
                         │    ┌────────▼─────────┐   │
                         │    │    DELIVERED      │   │
                         │    └──────────────────┘   │
                         │                            │
                         │    ┌──────────────────┐    │
                         └────│  FAILED_DELIVERY │────┘
                              └────────┬─────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │     RETURNED     │
                              └──────────────────┘
```

### Allowed Transitions

| From State | Allowed Next States |
|---|---|
| PENDING | CONFIRMED, CANCELLED |
| CONFIRMED | PREPARING, CANCELLED |
| PREPARING | READY_FOR_PICKUP, CANCELLED |
| READY_FOR_PICKUP | OUT_FOR_DELIVERY |
| OUT_FOR_DELIVERY | DELIVERED, FAILED_DELIVERY |
| FAILED_DELIVERY | OUT_FOR_DELIVERY (retry), RETURNED |
| DELIVERED | *(terminal)* |
| CANCELLED | *(terminal)* |
| RETURNED | *(terminal)* |

### Transition Guards

| Transition | Guard Condition |
|---|---|
| PENDING → CONFIRMED | All items have sufficient inventory |
| CONFIRMED → PREPARING | Merchant is active |
| READY_FOR_PICKUP → OUT_FOR_DELIVERY | Delivery agent is assigned |
| OUT_FOR_DELIVERY → DELIVERED | Agent confirmation provided |

---

## Acceptance Criteria

| FR | Criterion |
|---|---|
| FR-1 | Order created with unique ID; state = PENDING; ETA returned |
| FR-2 | Status query returns current state + ordered event history |
| FR-3 | Cancel from DELIVERED raises InvalidTransitionError |
| FR-6 | Confirming with stockout raises InventoryInsufficientError; order stays PENDING |
| FR-10 | Assigning a BUSY agent raises AgentNotAvailableError |
| FR-18 | Cancelling restores reserved inventory quantities |
| FR-19 | One notification record created per state transition per relevant actor |
| FR-20 | Every invalid transition raises InvalidTransitionError with from/to state in message |
