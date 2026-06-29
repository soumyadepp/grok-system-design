"""
Order Tracking System — pure Python, no external dependencies.

Run:  python order_tracking.py
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OrderState(Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    FAILED_DELIVERY = "FAILED_DELIVERY"
    RETURNED = "RETURNED"


class ActorType(Enum):
    CUSTOMER = "CUSTOMER"
    MERCHANT = "MERCHANT"
    AGENT = "AGENT"
    ADMIN = "ADMIN"
    SYSTEM = "SYSTEM"


class NotificationChannel(Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"


class AgentStatus(Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DeliveryAddress:
    street: str
    city: str
    zip_code: str
    lat: float = 0.0
    lng: float = 0.0


@dataclass
class Customer:
    customer_id: str
    name: str
    email: str
    phone: str


@dataclass
class Merchant:
    merchant_id: str
    name: str
    is_active: bool = True


@dataclass
class OrderItem:
    item_id: str
    product_id: str
    product_name: str
    quantity: int
    unit_price: float

    @property
    def total_price(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class Order:
    order_id: str
    customer_id: str
    merchant_id: str
    state: OrderState
    delivery_address: DeliveryAddress
    items: List[OrderItem]
    currency: str = "USD"
    placed_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    agent_id: Optional[str] = None
    cancellation_reason: Optional[str] = None

    @property
    def total_amount(self) -> float:
        return sum(i.total_price for i in self.items)


@dataclass
class OrderEvent:
    event_id: str
    order_id: str
    event_type: str
    to_state: OrderState
    actor_id: str
    actor_type: ActorType
    occurred_at: datetime = field(default_factory=datetime.now)
    from_state: Optional[OrderState] = None
    reason: Optional[str] = None


@dataclass
class DeliveryAgent:
    agent_id: str
    name: str
    phone: str
    vehicle_type: str
    status: AgentStatus = AgentStatus.AVAILABLE
    current_order_id: Optional[str] = None


@dataclass
class Product:
    product_id: str
    merchant_id: str
    name: str
    unit_price: float
    available_qty: int
    reserved_qty: int = 0

    @property
    def free_qty(self) -> int:
        return self.available_qty - self.reserved_qty


@dataclass
class Notification:
    notification_id: str
    order_id: str
    recipient_id: str
    channel: NotificationChannel
    message: str
    sent_at: datetime = field(default_factory=datetime.now)
    status: str = "SENT"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OrderTrackingError(Exception):
    pass

class OrderNotFoundError(OrderTrackingError):
    pass

class CustomerNotFoundError(OrderTrackingError):
    pass

class MerchantNotFoundError(OrderTrackingError):
    pass

class ProductNotFoundError(OrderTrackingError):
    pass

class AgentNotFoundError(OrderTrackingError):
    pass

class InventoryInsufficientError(OrderTrackingError):
    pass

class AgentNotAvailableError(OrderTrackingError):
    pass

class InvalidTransitionError(OrderTrackingError):
    pass

class MerchantInactiveError(OrderTrackingError):
    pass


# ---------------------------------------------------------------------------
# ETA Strategy
# ---------------------------------------------------------------------------

# Average minutes to complete each state before moving to the next
_STATE_DURATION: Dict[OrderState, int] = {
    OrderState.PENDING:           2,
    OrderState.CONFIRMED:         5,
    OrderState.PREPARING:         25,
    OrderState.READY_FOR_PICKUP:  10,
    OrderState.OUT_FOR_DELIVERY:  30,
}

_HAPPY_PATH: List[OrderState] = [
    OrderState.PENDING,
    OrderState.CONFIRMED,
    OrderState.PREPARING,
    OrderState.READY_FOR_PICKUP,
    OrderState.OUT_FOR_DELIVERY,
    OrderState.DELIVERED,
]


class ETAStrategy(ABC):
    @abstractmethod
    def calculate(self, current_state: OrderState) -> int:
        """Return estimated minutes to delivery from current state."""


class SimpleETAStrategy(ETAStrategy):
    def calculate(self, current_state: OrderState) -> int:
        if current_state not in _HAPPY_PATH:
            return 0  # terminal or off-path states
        idx = _HAPPY_PATH.index(current_state)
        # Include current state's remaining work + all subsequent state durations
        states_from_here = _HAPPY_PATH[idx:]
        return sum(_STATE_DURATION.get(s, 0) for s in states_from_here)


# ---------------------------------------------------------------------------
# State Machine
# ---------------------------------------------------------------------------

TRANSITIONS: Dict[OrderState, Set[OrderState]] = {
    OrderState.PENDING:           {OrderState.CONFIRMED, OrderState.CANCELLED},
    OrderState.CONFIRMED:         {OrderState.PREPARING, OrderState.CANCELLED},
    OrderState.PREPARING:         {OrderState.READY_FOR_PICKUP, OrderState.CANCELLED},
    OrderState.READY_FOR_PICKUP:  {OrderState.OUT_FOR_DELIVERY},
    OrderState.OUT_FOR_DELIVERY:  {OrderState.DELIVERED, OrderState.FAILED_DELIVERY},
    OrderState.FAILED_DELIVERY:   {OrderState.OUT_FOR_DELIVERY, OrderState.RETURNED},
    OrderState.DELIVERED:         set(),
    OrderState.CANCELLED:         set(),
    OrderState.RETURNED:          set(),
}


class OrderStateMachine:
    def __init__(self) -> None:
        # Guards keyed by (from, to); each returns (allowed: bool, reason: str)
        self._guards: Dict[Tuple[OrderState, OrderState], Callable[..., Tuple[bool, str]]] = {}

    def register_guard(
        self,
        from_state: OrderState,
        to_state: OrderState,
        guard: Callable[..., Tuple[bool, str]],
    ) -> None:
        self._guards[(from_state, to_state)] = guard

    def can_transition(self, from_state: OrderState, to_state: OrderState) -> bool:
        return to_state in TRANSITIONS.get(from_state, set())

    def get_allowed(self, state: OrderState) -> List[OrderState]:
        return list(TRANSITIONS.get(state, set()))

    def transition(
        self,
        order: Order,
        to_state: OrderState,
        actor_id: str,
        actor_type: ActorType,
        reason: Optional[str] = None,
        **guard_kwargs,
    ) -> OrderEvent:
        if not self.can_transition(order.state, to_state):
            allowed = [s.value for s in self.get_allowed(order.state)]
            raise InvalidTransitionError(
                f"Cannot transition {order.state.value} → {to_state.value}. "
                f"Allowed: {allowed or ['none (terminal)']}"
            )

        guard = self._guards.get((order.state, to_state))
        if guard:
            ok, msg = guard(order=order, **guard_kwargs)
            if not ok:
                raise InvalidTransitionError(
                    f"Guard blocked {order.state.value} → {to_state.value}: {msg}"
                )

        event = OrderEvent(
            event_id=str(uuid.uuid4()),
            order_id=order.order_id,
            event_type="STATE_CHANGED",
            from_state=order.state,
            to_state=to_state,
            actor_id=actor_id,
            actor_type=actor_type,
            reason=reason,
        )
        order.state = to_state
        order.updated_at = event.occurred_at
        return event


# ---------------------------------------------------------------------------
# Repositories (in-memory)
# ---------------------------------------------------------------------------

class OrderRepository:
    def __init__(self) -> None:
        self._orders: Dict[str, Order] = {}
        self._events: Dict[str, List[OrderEvent]] = {}

    def save(self, order: Order) -> None:
        self._orders[order.order_id] = order
        self._events.setdefault(order.order_id, [])

    def append_event(self, event: OrderEvent) -> None:
        self._events.setdefault(event.order_id, []).append(event)

    def find(self, order_id: str) -> Order:
        order = self._orders.get(order_id)
        if not order:
            raise OrderNotFoundError(f"Order {order_id} not found")
        return order

    def events(self, order_id: str) -> List[OrderEvent]:
        return list(self._events.get(order_id, []))

    def by_customer(self, customer_id: str) -> List[Order]:
        return sorted(
            [o for o in self._orders.values() if o.customer_id == customer_id],
            key=lambda o: o.placed_at,
            reverse=True,
        )

    def by_state(self, state: OrderState) -> List[Order]:
        return [o for o in self._orders.values() if o.state == state]

    def all(self) -> List[Order]:
        return list(self._orders.values())


class ProductRepository:
    def __init__(self) -> None:
        self._products: Dict[str, Product] = {}

    def save(self, product: Product) -> None:
        self._products[product.product_id] = product

    def find(self, product_id: str) -> Product:
        p = self._products.get(product_id)
        if not p:
            raise ProductNotFoundError(f"Product {product_id} not found")
        return p


class AgentRepository:
    def __init__(self) -> None:
        self._agents: Dict[str, DeliveryAgent] = {}

    def save(self, agent: DeliveryAgent) -> None:
        self._agents[agent.agent_id] = agent

    def find(self, agent_id: str) -> DeliveryAgent:
        a = self._agents.get(agent_id)
        if not a:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        return a

    def available(self) -> List[DeliveryAgent]:
        return [a for a in self._agents.values() if a.status == AgentStatus.AVAILABLE]


class CustomerRepository:
    def __init__(self) -> None:
        self._customers: Dict[str, Customer] = {}

    def save(self, customer: Customer) -> None:
        self._customers[customer.customer_id] = customer

    def find(self, customer_id: str) -> Customer:
        c = self._customers.get(customer_id)
        if not c:
            raise CustomerNotFoundError(f"Customer {customer_id} not found")
        return c


class MerchantRepository:
    def __init__(self) -> None:
        self._merchants: Dict[str, Merchant] = {}

    def save(self, merchant: Merchant) -> None:
        self._merchants[merchant.merchant_id] = merchant

    def find(self, merchant_id: str) -> Merchant:
        m = self._merchants.get(merchant_id)
        if not m:
            raise MerchantNotFoundError(f"Merchant {merchant_id} not found")
        return m


class NotificationRepository:
    def __init__(self) -> None:
        self._notifications: List[Notification] = []

    def save(self, notification: Notification) -> None:
        self._notifications.append(notification)

    def by_order(self, order_id: str) -> List[Notification]:
        return [n for n in self._notifications if n.order_id == order_id]

    def all(self) -> List[Notification]:
        return list(self._notifications)


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

class InventoryService:
    def __init__(self, product_repo: ProductRepository) -> None:
        self._repo = product_repo

    def check_and_reserve(self, items: List[OrderItem]) -> None:
        for item in items:
            product = self._repo.find(item.product_id)
            if product.free_qty < item.quantity:
                raise InventoryInsufficientError(
                    f"Insufficient stock for '{product.name}': "
                    f"need {item.quantity}, available {product.free_qty}"
                )
        for item in items:
            product = self._repo.find(item.product_id)
            product.reserved_qty += item.quantity

    def release(self, items: List[OrderItem]) -> None:
        for item in items:
            try:
                product = self._repo.find(item.product_id)
                product.reserved_qty = max(0, product.reserved_qty - item.quantity)
            except ProductNotFoundError:
                pass

    def consume(self, items: List[OrderItem]) -> None:
        """Deduct from available when order is delivered (finalize reservation)."""
        for item in items:
            product = self._repo.find(item.product_id)
            product.available_qty -= item.quantity
            product.reserved_qty = max(0, product.reserved_qty - item.quantity)


class NotificationService:
    def __init__(self, notification_repo: NotificationRepository) -> None:
        self._repo = notification_repo

    def notify_transition(
        self,
        order: Order,
        event: OrderEvent,
        recipient_ids: List[str],
        channel: NotificationChannel = NotificationChannel.PUSH,
    ) -> List[Notification]:
        notifications: List[Notification] = []
        msg = self._format(order, event)
        for rid in recipient_ids:
            n = Notification(
                notification_id=str(uuid.uuid4()),
                order_id=order.order_id,
                recipient_id=rid,
                channel=channel,
                message=msg,
            )
            self._repo.save(n)
            notifications.append(n)
        return notifications

    def _format(self, order: Order, event: OrderEvent) -> str:
        return (
            f"Order {order.order_id[:8]}… moved "
            f"{event.from_state.value if event.from_state else 'NEW'} "
            f"→ {event.to_state.value}"
            + (f" | {event.reason}" if event.reason else "")
        )


class DeliveryAgentService:
    def __init__(self, agent_repo: AgentRepository) -> None:
        self._repo = agent_repo

    def assign(self, order: Order, agent_id: str) -> DeliveryAgent:
        agent = self._repo.find(agent_id)
        if agent.status != AgentStatus.AVAILABLE:
            raise AgentNotAvailableError(
                f"Agent '{agent.name}' is {agent.status.value}, not available"
            )
        agent.status = AgentStatus.BUSY
        agent.current_order_id = order.order_id
        order.agent_id = agent_id
        return agent

    def release(self, agent_id: str) -> None:
        agent = self._repo.find(agent_id)
        agent.status = AgentStatus.AVAILABLE
        agent.current_order_id = None

    def get_available(self) -> List[DeliveryAgent]:
        return self._repo.available()


class OrderService:
    def __init__(
        self,
        order_repo: OrderRepository,
        customer_repo: CustomerRepository,
        merchant_repo: MerchantRepository,
        inventory_svc: InventoryService,
        notification_svc: NotificationService,
        agent_svc: DeliveryAgentService,
        state_machine: OrderStateMachine,
        eta_strategy: ETAStrategy,
    ) -> None:
        self._orders = order_repo
        self._customers = customer_repo
        self._merchants = merchant_repo
        self._inventory = inventory_svc
        self._notifications = notification_svc
        self._agents = agent_svc
        self._sm = state_machine
        self._eta = eta_strategy
        self._register_guards()

    def _register_guards(self) -> None:
        def inventory_guard(order: Order, **_) -> Tuple[bool, str]:
            try:
                self._inventory.check_and_reserve(order.items)
                return True, ""
            except InventoryInsufficientError as e:
                return False, str(e)

        def merchant_active_guard(order: Order, **_) -> Tuple[bool, str]:
            try:
                m = self._merchants.find(order.merchant_id)
                return (True, "") if m.is_active else (False, "Merchant is inactive")
            except MerchantNotFoundError as e:
                return False, str(e)

        def agent_assigned_guard(order: Order, **_) -> Tuple[bool, str]:
            if not order.agent_id:
                return False, "No delivery agent assigned"
            return True, ""

        self._sm.register_guard(OrderState.PENDING, OrderState.CONFIRMED, inventory_guard)
        self._sm.register_guard(OrderState.CONFIRMED, OrderState.PREPARING, merchant_active_guard)
        self._sm.register_guard(OrderState.READY_FOR_PICKUP, OrderState.OUT_FOR_DELIVERY, agent_assigned_guard)

    def place_order(
        self,
        customer_id: str,
        merchant_id: str,
        address: DeliveryAddress,
        raw_items: List[Dict],
    ) -> Order:
        self._customers.find(customer_id)
        self._merchants.find(merchant_id)

        items: List[OrderItem] = []
        for raw in raw_items:
            items.append(OrderItem(
                item_id=str(uuid.uuid4()),
                product_id=raw["product_id"],
                product_name=raw["product_name"],
                quantity=raw["quantity"],
                unit_price=raw["unit_price"],
            ))

        order = Order(
            order_id=str(uuid.uuid4()),
            customer_id=customer_id,
            merchant_id=merchant_id,
            state=OrderState.PENDING,
            delivery_address=address,
            items=items,
        )
        self._orders.save(order)

        placed_event = OrderEvent(
            event_id=str(uuid.uuid4()),
            order_id=order.order_id,
            event_type="ORDER_PLACED",
            to_state=OrderState.PENDING,
            actor_id=customer_id,
            actor_type=ActorType.CUSTOMER,
            reason="Order placed by customer",
        )
        self._orders.append_event(placed_event)
        self._notifications.notify_transition(order, placed_event, [customer_id])
        return order

    def transition(
        self,
        order_id: str,
        to_state: OrderState,
        actor_id: str,
        actor_type: ActorType,
        reason: Optional[str] = None,
    ) -> Order:
        order = self._orders.find(order_id)
        event = self._sm.transition(order, to_state, actor_id, actor_type, reason)
        self._orders.append_event(event)

        # Post-transition side effects
        if to_state == OrderState.CANCELLED and order.items:
            self._inventory.release(order.items)
            order.cancellation_reason = reason
            if order.agent_id:
                self._agents.release(order.agent_id)

        if to_state == OrderState.DELIVERED:
            self._inventory.consume(order.items)
            if order.agent_id:
                self._agents.release(order.agent_id)

        if to_state == OrderState.RETURNED and order.agent_id:
            self._agents.release(order.agent_id)

        recipients = [order.customer_id, order.merchant_id]
        if order.agent_id:
            recipients.append(order.agent_id)
        self._notifications.notify_transition(order, event, recipients)
        return order

    def assign_agent(self, order_id: str, agent_id: str) -> Order:
        order = self._orders.find(order_id)
        self._agents.assign(order, agent_id)
        return order

    def get_order(self, order_id: str) -> Order:
        return self._orders.find(order_id)

    def get_history(self, customer_id: str) -> List[Order]:
        self._customers.find(customer_id)
        return self._orders.by_customer(customer_id)

    def get_eta(self, order_id: str) -> int:
        order = self._orders.find(order_id)
        return self._eta.calculate(order.state)


class TrackingService:
    def __init__(
        self,
        order_repo: OrderRepository,
        agent_repo: AgentRepository,
        eta_strategy: ETAStrategy,
    ) -> None:
        self._orders = order_repo
        self._agents = agent_repo
        self._eta = eta_strategy

    def get_status(self, order_id: str) -> dict:
        order = self._orders.find(order_id)
        events = self._orders.events(order_id)
        eta = self._eta.calculate(order.state)

        agent_info = None
        if order.agent_id:
            try:
                a = self._agents.find(order.agent_id)
                agent_info = {"agent_id": a.agent_id, "name": a.name, "vehicle": a.vehicle_type}
            except AgentNotFoundError:
                pass

        return {
            "order_id": order.order_id,
            "state": order.state.value,
            "total_amount": order.total_amount,
            "currency": order.currency,
            "eta_minutes": eta,
            "estimated_delivery_at": (datetime.now() + timedelta(minutes=eta)).isoformat(timespec="minutes"),
            "agent": agent_info,
            "events": [
                {
                    "event_type": e.event_type,
                    "from_state": e.from_state.value if e.from_state else None,
                    "to_state": e.to_state.value,
                    "actor_type": e.actor_type.value,
                    "actor_id": e.actor_id[:8] + "…",
                    "reason": e.reason,
                    "occurred_at": e.occurred_at.isoformat(timespec="seconds"),
                }
                for e in events
            ],
        }

    def list_by_state(self, state: OrderState) -> List[Order]:
        return self._orders.by_state(state)

    def list_all(self) -> List[Order]:
        return self._orders.all()


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def build_system() -> Tuple[OrderService, TrackingService, dict]:
    """Wire all components and seed demo data. Returns (order_svc, tracking_svc, seed_data)."""
    order_repo = OrderRepository()
    product_repo = ProductRepository()
    agent_repo = AgentRepository()
    customer_repo = CustomerRepository()
    merchant_repo = MerchantRepository()
    notification_repo = NotificationRepository()

    inventory_svc = InventoryService(product_repo)
    notification_svc = NotificationService(notification_repo)
    agent_svc = DeliveryAgentService(agent_repo)
    eta = SimpleETAStrategy()
    sm = OrderStateMachine()

    order_svc = OrderService(
        order_repo, customer_repo, merchant_repo,
        inventory_svc, notification_svc, agent_svc, sm, eta,
    )
    tracking_svc = TrackingService(order_repo, agent_repo, eta)

    # Seed customers
    customers = [
        Customer("cust-001", "Aarav Shah", "aarav@example.com", "+91-9000000001"),
        Customer("cust-002", "Priya Nair", "priya@example.com", "+91-9000000002"),
        Customer("cust-003", "Rohan Mehta", "rohan@example.com", "+91-9000000003"),
    ]
    for c in customers:
        customer_repo.save(c)

    # Seed merchants
    merchants = [
        Merchant("merch-001", "Spice Garden"),
        Merchant("merch-002", "Burger House", is_active=True),
    ]
    for m in merchants:
        merchant_repo.save(m)

    # Seed products
    products = [
        Product("prod-001", "merch-001", "Paneer Tikka", 180.0, available_qty=20),
        Product("prod-002", "merch-001", "Dal Makhani", 150.0, available_qty=15),
        Product("prod-003", "merch-002", "Cheese Burger", 220.0, available_qty=10),
        Product("prod-004", "merch-002", "Fries", 80.0, available_qty=0),  # intentionally out of stock
    ]
    for p in products:
        product_repo.save(p)

    # Seed delivery agents
    agents = [
        DeliveryAgent("agent-001", "Ravi Kumar", "+91-8000000001", "BIKE"),
        DeliveryAgent("agent-002", "Sunita Devi", "+91-8000000002", "SCOOTER"),
        DeliveryAgent("agent-003", "Manoj Singh", "+91-8000000003", "CYCLE"),
    ]
    for a in agents:
        agent_repo.save(a)

    seed = {
        "customers": customers,
        "merchants": merchants,
        "products": products,
        "agents": agents,
        "notification_repo": notification_repo,
    }
    return order_svc, tracking_svc, seed


# ---------------------------------------------------------------------------
# Demo helpers
# ---------------------------------------------------------------------------

def _sep(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


def _print_status(tracking: TrackingService, order_id: str) -> None:
    s = tracking.get_status(order_id)
    print(f"  Order : {s['order_id'][:8]}…")
    print(f"  State : {s['state']}")
    print(f"  Total : {s['currency']} {s['total_amount']:.2f}")
    print(f"  ETA   : {s['eta_minutes']} min")
    if s["agent"]:
        a = s["agent"]
        print(f"  Agent : {a['name']} ({a['vehicle']})")
    print(f"  Events ({len(s['events'])}):")
    for e in s["events"]:
        arrow = f"{e['from_state']} → {e['to_state']}" if e["from_state"] else f"NEW → {e['to_state']}"
        reason = f" | {e['reason']}" if e["reason"] else ""
        print(f"    [{e['occurred_at']}] {arrow} by {e['actor_type']}{reason}")


ADDR = DeliveryAddress("12 MG Road", "Bengaluru", "560001", 12.97, 77.59)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    order_svc, tracking_svc, seed = build_system()
    customers = seed["customers"]
    merchants = seed["merchants"]
    agents = seed["agents"]
    notification_repo: NotificationRepository = seed["notification_repo"]

    passed = 0
    total = 10

    # -----------------------------------------------------------------------
    # Scenario A: Happy path — PENDING → DELIVERED
    # -----------------------------------------------------------------------
    _sep("Scenario A: Happy path (PENDING → DELIVERED)")

    order_a = order_svc.place_order(
        customers[0].customer_id,
        merchants[0].merchant_id,
        ADDR,
        [
            {"product_id": "prod-001", "product_name": "Paneer Tikka", "quantity": 2, "unit_price": 180.0},
            {"product_id": "prod-002", "product_name": "Dal Makhani", "quantity": 1, "unit_price": 150.0},
        ],
    )
    assert order_a.state == OrderState.PENDING

    order_svc.transition(order_a.order_id, OrderState.CONFIRMED, merchants[0].merchant_id, ActorType.MERCHANT, "Items available")
    assert order_a.state == OrderState.CONFIRMED

    order_svc.transition(order_a.order_id, OrderState.PREPARING, merchants[0].merchant_id, ActorType.MERCHANT, "Started cooking")
    assert order_a.state == OrderState.PREPARING

    order_svc.transition(order_a.order_id, OrderState.READY_FOR_PICKUP, merchants[0].merchant_id, ActorType.MERCHANT, "Packed and ready")
    assert order_a.state == OrderState.READY_FOR_PICKUP

    order_svc.assign_agent(order_a.order_id, agents[0].agent_id)
    assert order_a.agent_id == agents[0].agent_id

    order_svc.transition(order_a.order_id, OrderState.OUT_FOR_DELIVERY, agents[0].agent_id, ActorType.AGENT, "Picked up")
    assert order_a.state == OrderState.OUT_FOR_DELIVERY

    order_svc.transition(order_a.order_id, OrderState.DELIVERED, agents[0].agent_id, ActorType.AGENT, "Handed to customer")
    assert order_a.state == OrderState.DELIVERED

    status_a = tracking_svc.get_status(order_a.order_id)
    assert status_a["eta_minutes"] == 0  # DELIVERED has no remaining duration
    assert len(status_a["events"]) == 6  # ORDER_PLACED + 5 STATE_CHANGED
    _print_status(tracking_svc, order_a.order_id)
    print("  [PASS] Scenario A")
    passed += 1

    # -----------------------------------------------------------------------
    # Scenario B: Cancellation after CONFIRMED
    # -----------------------------------------------------------------------
    _sep("Scenario B: Cancellation after CONFIRMED")

    order_b = order_svc.place_order(
        customers[1].customer_id,
        merchants[0].merchant_id,
        ADDR,
        [{"product_id": "prod-001", "product_name": "Paneer Tikka", "quantity": 1, "unit_price": 180.0}],
    )
    order_svc.transition(order_b.order_id, OrderState.CONFIRMED, merchants[0].merchant_id, ActorType.MERCHANT)
    order_svc.transition(order_b.order_id, OrderState.CANCELLED, customers[1].customer_id, ActorType.CUSTOMER, "Changed my mind")
    assert order_b.state == OrderState.CANCELLED
    assert order_b.cancellation_reason == "Changed my mind"
    _print_status(tracking_svc, order_b.order_id)
    print("  [PASS] Scenario B")
    passed += 1

    # -----------------------------------------------------------------------
    # Scenario C: Failed delivery → retry → RETURNED
    # -----------------------------------------------------------------------
    _sep("Scenario C: Failed delivery → retry → RETURNED")

    order_c = order_svc.place_order(
        customers[2].customer_id,
        merchants[1].merchant_id,
        ADDR,
        [{"product_id": "prod-003", "product_name": "Cheese Burger", "quantity": 1, "unit_price": 220.0}],
    )
    order_svc.transition(order_c.order_id, OrderState.CONFIRMED, merchants[1].merchant_id, ActorType.MERCHANT)
    order_svc.transition(order_c.order_id, OrderState.PREPARING, merchants[1].merchant_id, ActorType.MERCHANT)
    order_svc.transition(order_c.order_id, OrderState.READY_FOR_PICKUP, merchants[1].merchant_id, ActorType.MERCHANT)
    order_svc.assign_agent(order_c.order_id, agents[1].agent_id)
    order_svc.transition(order_c.order_id, OrderState.OUT_FOR_DELIVERY, agents[1].agent_id, ActorType.AGENT)
    order_svc.transition(order_c.order_id, OrderState.FAILED_DELIVERY, agents[1].agent_id, ActorType.AGENT, "Door locked")
    assert order_c.state == OrderState.FAILED_DELIVERY

    # retry
    order_svc.transition(order_c.order_id, OrderState.OUT_FOR_DELIVERY, agents[1].agent_id, ActorType.AGENT, "Retry attempt")
    assert order_c.state == OrderState.OUT_FOR_DELIVERY

    order_svc.transition(order_c.order_id, OrderState.FAILED_DELIVERY, agents[1].agent_id, ActorType.AGENT, "Still no answer")
    order_svc.transition(order_c.order_id, OrderState.RETURNED, agents[1].agent_id, ActorType.AGENT, "Returning to merchant")
    assert order_c.state == OrderState.RETURNED
    _print_status(tracking_svc, order_c.order_id)
    print("  [PASS] Scenario C")
    passed += 1

    # -----------------------------------------------------------------------
    # Scenario D: InventoryInsufficientError on stockout
    # -----------------------------------------------------------------------
    _sep("Scenario D: InventoryInsufficientError (Fries out of stock)")

    order_d = order_svc.place_order(
        customers[0].customer_id,
        merchants[1].merchant_id,
        ADDR,
        [{"product_id": "prod-004", "product_name": "Fries", "quantity": 1, "unit_price": 80.0}],
    )
    try:
        order_svc.transition(order_d.order_id, OrderState.CONFIRMED, merchants[1].merchant_id, ActorType.MERCHANT)
        assert False, "Should have raised InventoryInsufficientError"
    except InvalidTransitionError as e:
        assert "Insufficient stock" in str(e) or "Guard blocked" in str(e)
        assert order_d.state == OrderState.PENDING, "Order must stay PENDING on guard failure"
        print(f"  Caught expected error: {e}")
    print("  [PASS] Scenario D")
    passed += 1

    # -----------------------------------------------------------------------
    # Scenario E: InvalidTransitionError on illegal transition
    # -----------------------------------------------------------------------
    _sep("Scenario E: Invalid transition DELIVERED → PENDING")

    try:
        order_svc.transition(order_a.order_id, OrderState.PENDING, "system", ActorType.SYSTEM, "Reopen attempt")
        assert False, "Should have raised InvalidTransitionError"
    except InvalidTransitionError as e:
        assert "DELIVERED" in str(e)
        print(f"  Caught expected error: {e}")
    print("  [PASS] Scenario E")
    passed += 1

    # -----------------------------------------------------------------------
    # Scenario F: AgentNotAvailableError on double-assignment
    # -----------------------------------------------------------------------
    _sep("Scenario F: AgentNotAvailableError (agent already busy)")

    # Place and advance a new order to READY_FOR_PICKUP
    order_f = order_svc.place_order(
        customers[0].customer_id,
        merchants[0].merchant_id,
        ADDR,
        [{"product_id": "prod-001", "product_name": "Paneer Tikka", "quantity": 1, "unit_price": 180.0}],
    )
    order_svc.transition(order_f.order_id, OrderState.CONFIRMED, merchants[0].merchant_id, ActorType.MERCHANT)
    order_svc.transition(order_f.order_id, OrderState.PREPARING, merchants[0].merchant_id, ActorType.MERCHANT)
    order_svc.transition(order_f.order_id, OrderState.READY_FOR_PICKUP, merchants[0].merchant_id, ActorType.MERCHANT)
    # agent-002 is still BUSY from Scenario C (order was RETURNED so agent should be free — use agent-003)
    order_svc.assign_agent(order_f.order_id, agents[2].agent_id)

    order_f2 = order_svc.place_order(
        customers[1].customer_id,
        merchants[0].merchant_id,
        ADDR,
        [{"product_id": "prod-001", "product_name": "Paneer Tikka", "quantity": 1, "unit_price": 180.0}],
    )
    try:
        order_svc.assign_agent(order_f2.order_id, agents[2].agent_id)  # already assigned to order_f
        assert False, "Should have raised AgentNotAvailableError"
    except AgentNotAvailableError as e:
        print(f"  Caught expected error: {e}")
    print("  [PASS] Scenario F")
    passed += 1

    # -----------------------------------------------------------------------
    # Scenario G: Customer order history
    # -----------------------------------------------------------------------
    _sep("Scenario G: Customer order history")

    history = order_svc.get_history(customers[0].customer_id)
    assert len(history) >= 3, f"Expected >= 3 orders, got {len(history)}"
    for o in history:
        print(f"  {o.order_id[:8]}… | {o.state.value} | INR {o.total_amount:.2f}")
    print("  [PASS] Scenario G")
    passed += 1

    # -----------------------------------------------------------------------
    # Scenario H: Admin filter by state
    # -----------------------------------------------------------------------
    _sep("Scenario H: Admin filter — CANCELLED orders")

    cancelled = tracking_svc.list_by_state(OrderState.CANCELLED)
    assert len(cancelled) >= 1
    print(f"  Found {len(cancelled)} cancelled order(s):")
    for o in cancelled:
        print(f"    {o.order_id[:8]}… | reason: {o.cancellation_reason}")
    print("  [PASS] Scenario H")
    passed += 1

    # -----------------------------------------------------------------------
    # Scenario I: ETA decreases monotonically along happy path
    # -----------------------------------------------------------------------
    _sep("Scenario I: ETA decreases monotonically")

    eta_svc = SimpleETAStrategy()
    path = [
        OrderState.PENDING,
        OrderState.CONFIRMED,
        OrderState.PREPARING,
        OrderState.READY_FOR_PICKUP,
        OrderState.OUT_FOR_DELIVERY,
        OrderState.DELIVERED,
    ]
    etas = [eta_svc.calculate(s) for s in path]
    print(f"  ETA per state: {list(zip([s.value for s in path], etas))}")
    for i in range(len(etas) - 1):
        assert etas[i] > etas[i + 1], f"ETA not decreasing at index {i}"
    assert etas[-1] == 0
    print("  [PASS] Scenario I")
    passed += 1

    # -----------------------------------------------------------------------
    # Scenario J: Notification log completeness
    # -----------------------------------------------------------------------
    _sep("Scenario J: Notification log — happy path order")

    notifs_a = notification_repo.by_order(order_a.order_id)
    print(f"  Notifications for order A: {len(notifs_a)}")
    for n in notifs_a:
        print(f"    → [{n.channel.value}] to {n.recipient_id[:8]}… | {n.message}")
    # At least one notification per event (7 events × at least 1 recipient each)
    assert len(notifs_a) >= 7
    print("  [PASS] Scenario J")
    passed += 1

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    _sep(f"Results: {passed}/{total} scenarios passed")
    if passed == total:
        print("  All scenarios passed.")
    else:
        print(f"  {total - passed} scenario(s) FAILED.")


if __name__ == "__main__":
    main()
