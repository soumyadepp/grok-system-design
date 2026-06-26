from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from heapq import heappush, heappop
from uuid import uuid4


class UserNotFoundError(Exception):
    """Raised when a user ID is not found in the service."""

    pass


class GroupNotFoundError(Exception):
    """Raised when a group ID is not found in the service."""

    pass


class InvalidSplitError(Exception):
    """Raised when a split operation is invalid."""

    pass


@dataclass
class User:
    """Represents a user in the Splitwise system.

    Attributes:
        user_id: Unique identifier for the user.
        name: Display name of the user.
    """

    user_id: str
    name: str


@dataclass
class Split:
    """Represents an individual user's share of an expense.

    Attributes:
        user: The user responsible for this portion.
        amount: The monetary amount owed by the user.
    """

    user: User
    amount: float


@dataclass
class Expense:
    """Represents an expense paid by one user and split among others.

    Attributes:
        expense_id: Unique identifier for the expense.
        description: Human-readable description of the expense.
        paid_by: The user who paid the expense.
        amount: Total amount of the expense.
        splits: How the expense is divided among users.
        group_id: Optional group this expense belongs to.
        created_at: Timestamp when the expense was created.
    """

    expense_id: str
    description: str
    paid_by: User
    amount: float
    splits: list[Split]
    group_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Group:
    """Represents a group of users who share expenses.

    Attributes:
        group_id: Unique identifier for the group.
        name: Display name of the group.
        members: List of users in the group.
        expenses: List of expenses associated with the group.
    """

    group_id: str
    name: str
    members: list[User] = field(default_factory=list)
    expenses: list[Expense] = field(default_factory=list)


class SplitStrategy(ABC):
    """Abstract base class for expense splitting strategies."""

    @abstractmethod
    def split(self, amount: float, users: list[User]) -> list[Split]:
        """Divide an amount among a list of users.

        Args:
            amount: The total amount to split.
            users: The users among whom the amount is split.

        Returns:
            A list of Split objects representing each user's share.
        """
        pass


class EqualSplit(SplitStrategy):
    """Splits an expense equally among all users."""

    def split(self, amount: float, users: list[User]) -> list[Split]:
        """Divide an amount equally among users.

        Args:
            amount: The total amount to split.
            users: The users among whom the amount is split equally.

        Returns:
            A list of Split objects with equal amounts.

        Raises:
            InvalidSplitError: If the user list is empty.
        """
        if not users:
            raise InvalidSplitError("Cannot split among zero users")
        per_person = round(amount / len(users), 2)
        return [Split(user=u, amount=per_person) for u in users]


class PercentageSplit(SplitStrategy):
    """Splits an expense by user-defined percentages.

    Attributes:
        _percentages: Mapping of user ID to their percentage share.
    """

    def __init__(self, percentages: dict[str, float]) -> None:
        """Initialize with percentage allocations.

        Args:
            percentages: Mapping of user ID to percentage share.
                Values must sum to 100.

        Raises:
            InvalidSplitError: If percentages do not sum to 100.
        """
        total = sum(percentages.values())
        if round(total, 2) != 100:
            raise InvalidSplitError(f"Percentages must sum to 100, got {total}")
        self._percentages = percentages

    def split(self, amount: float, users: list[User]) -> list[Split]:
        """Divide an amount by percentage among users.

        Args:
            amount: The total amount to split.
            users: The users among whom the amount is split.

        Returns:
            A list of Split objects with amounts proportional to each
            user's percentage.

        Raises:
            InvalidSplitError: If the user list is empty or any user
                is missing a percentage entry.
        """
        if not users:
            raise InvalidSplitError("Cannot split among zero users")
        missing = [u for u in users if u.user_id not in self._percentages]
        if missing:
            raise InvalidSplitError(
                f"Missing percentages for: {[u.user_id for u in missing]}"
            )
        return [
            Split(user=u, amount=round(amount * self._percentages[u.user_id] / 100, 2))
            for u in users
        ]


class ExactSplit(SplitStrategy):
    """Splits an expense using exact amounts for each user.

    Attributes:
        _allocations: Mapping of user ID to the exact amount owed.
    """

    def __init__(self, allocations: dict[str, float]) -> None:
        """Initialize with exact allocations.

        Args:
            allocations: Mapping of user ID to the exact amount owed.

        Raises:
            InvalidSplitError: If any allocation amount is negative.
        """
        if any(a < 0 for a in allocations.values()):
            raise InvalidSplitError("All exact allocation amounts must be non-negative")
        self._allocations = allocations

    def split(self, amount: float, users: list[User]) -> list[Split]:
        """Divide an amount by exact allocations among users.

        Args:
            amount: The total amount to split.
            users: The users among whom the amount is split.

        Returns:
            A list of Split objects with the exact amounts owed by each user.

        Raises:
            InvalidSplitError: If the user list is empty, any user is missing
                an allocation entry, or the provided allocations do not sum to
                the expected total amount.
        """
        if not users:
            raise InvalidSplitError("Cannot split among zero users")
        missing = [u for u in users if u.user_id not in self._allocations]
        if missing:
            raise InvalidSplitError(
                f"Missing exact allocations for: {[u.user_id for u in missing]}"
            )

        total_allocated = round(sum(self._allocations[u.user_id] for u in users), 2)
        if round(amount, 2) != total_allocated:
            raise InvalidSplitError(
                f"Exact allocations must sum to the total amount. "
                f"Expected {round(amount,2)}, got {total_allocated}"
            )

        return [
            Split(user=u, amount=round(self._allocations[u.user_id], 2)) for u in users
        ]


class SplitwiseService:
    """Core service for managing users, groups, expenses, and debt settlement."""

    def __init__(self) -> None:
        """Initialize the service with empty user, group, and expense stores."""
        self._users: dict[str, User] = {}
        self._groups: dict[str, Group] = {}
        self._expenses: list[Expense] = []

    def add_user(self, name: str, user_id: str | None = None) -> User:
        """Register a new user in the service.

        Args:
            name: Display name for the user.
            user_id: Optional custom ID. A UUID is generated if not provided.

        Returns:
            The newly created User.
        """
        uid = user_id or str(uuid4())
        user = User(user_id=uid, name=name)
        self._users[uid] = user
        return user

    def get_user(self, user_id: str) -> User:
        """Retrieve a user by their ID.

        Args:
            user_id: The unique identifier of the user.

        Returns:
            The matching User object.

        Raises:
            UserNotFoundError: If no user exists with the given ID.
        """
        if user_id not in self._users:
            raise UserNotFoundError(f"User {user_id} not found")
        return self._users[user_id]

    def create_group(
        self, name: str, member_ids: list[str], group_id: str | None = None
    ) -> Group:
        """Create a new group with the specified members.

        Args:
            name: Display name for the group.
            member_ids: List of user IDs to include as members.
            group_id: Optional custom ID. A UUID is generated if not provided.

        Returns:
            The newly created Group.

        Raises:
            UserNotFoundError: If any member ID is not found.
        """
        members = [self.get_user(uid) for uid in member_ids]
        gid = group_id or str(uuid4())
        group = Group(group_id=gid, name=name, members=members)
        self._groups[gid] = group
        return group

    def get_group(self, group_id: str) -> Group:
        """Retrieve a group by its ID.

        Args:
            group_id: The unique identifier of the group.

        Returns:
            The matching Group object.

        Raises:
            GroupNotFoundError: If no group exists with the given ID.
        """
        if group_id not in self._groups:
            raise GroupNotFoundError(f"Group {group_id} not found")
        return self._groups[group_id]

    def add_expense(
        self,
        description: str,
        paid_by_id: str,
        amount: float,
        strategy: SplitStrategy,
        debtor_ids: list[str] | None = None,
        group_id: str | None = None,
        expense_id: str | None = None,
    ) -> Expense:
        """Record a new expense and split it among debtors.

        Either ``group_id`` or ``debtor_ids`` must be provided. When a
        group is specified without explicit debtor IDs, all group members
        are used as debtors.

        Args:
            description: Human-readable description of the expense.
            paid_by_id: User ID of the person who paid.
            amount: Total expense amount (must be positive).
            strategy: The splitting strategy to apply.
            debtor_ids: Optional list of user IDs who owe money.
            group_id: Optional group to associate the expense with.
            expense_id: Optional custom ID. A UUID is generated if not
                provided.

        Returns:
            The newly created Expense.

        Raises:
            InvalidSplitError: If amount is not positive or neither
                group_id nor debtor_ids is provided.
            UserNotFoundError: If the payer or any debtor ID is not found.
            GroupNotFoundError: If the group ID is not found.
        """
        if amount <= 0:
            raise InvalidSplitError("Amount must be positive")

        paid_by = self.get_user(paid_by_id)

        if group_id:
            group = self.get_group(group_id)
            debtors = (
                group.members
                if debtor_ids is None
                else [self.get_user(uid) for uid in debtor_ids]
            )
        elif debtor_ids:
            debtors = [self.get_user(uid) for uid in debtor_ids]
        else:
            raise InvalidSplitError("Must provide either group_id or debtor_ids")

        splits = strategy.split(amount, debtors)

        expense = Expense(
            expense_id=expense_id or str(uuid4()),
            description=description,
            paid_by=paid_by,
            amount=amount,
            splits=splits,
            group_id=group_id,
        )

        self._expenses.append(expense)
        if group_id:
            self._groups[group_id].expenses.append(expense)

        return expense

    def _relevant_expenses(self, group_id: str | None) -> list[Expense]:
        """Return expenses filtered by group, or all expenses if no group.

        Args:
            group_id: Optional group ID to filter by.

        Returns:
            List of matching Expense objects.

        Raises:
            GroupNotFoundError: If the group ID is provided but not found.
        """
        if group_id:
            self.get_group(group_id)
            return [e for e in self._expenses if e.group_id == group_id]
        return self._expenses

    def get_balances(self, group_id: str | None = None) -> dict[str, float]:
        """Compute net balances for all users.

        A positive balance means the user is owed money; a negative balance
        means the user owes money.

        Args:
            group_id: Optional group ID to scope the calculation to.

        Returns:
            Mapping of user ID to net balance, excluding zero balances.
        """
        balances: dict[str, float] = {}
        for expense in self._relevant_expenses(group_id):
            payer_id = expense.paid_by.user_id
            balances[payer_id] = balances.get(payer_id, 0) + expense.amount
            for split in expense.splits:
                uid = split.user.user_id
                balances[uid] = balances.get(uid, 0) - split.amount
        return {
            uid: round(bal, 2) for uid, bal in balances.items() if round(bal, 2) != 0
        }

    def simplify_debts(
        self, group_id: str | None = None
    ) -> list[tuple[User, User, float]]:
        """Minimize the number of transactions needed to settle all debts.

        Uses a greedy heap-based approach to pair the largest creditor
        with the largest debtor until all balances are settled.

        Args:
            group_id: Optional group ID to scope the calculation to.

        Returns:
            A list of (debtor, creditor, amount) tuples representing
            the simplified transactions.
        """
        balances = self.get_balances(group_id)

        creditor_heap: list[tuple[float, str]] = []
        debtor_heap: list[tuple[float, str]] = []

        for uid, bal in balances.items():
            if bal > 0:
                heappush(creditor_heap, (-bal, uid))
            elif bal < 0:
                heappush(debtor_heap, (bal, uid))

        transactions: list[tuple[User, User, float]] = []
        while creditor_heap and debtor_heap:
            neg_c_amt, c_id = heappop(creditor_heap)
            neg_d_amt, d_id = heappop(debtor_heap)
            c_amt = -neg_c_amt
            d_amt = -neg_d_amt
            settled = min(c_amt, d_amt)
            transactions.append(
                (self._users[d_id], self._users[c_id], round(settled, 2))
            )
            remaining_credit = round(c_amt - settled, 2)
            remaining_debt = round(d_amt - settled, 2)
            if remaining_credit > 0:
                heappush(creditor_heap, (-remaining_credit, c_id))
            if remaining_debt > 0:
                heappush(debtor_heap, (-remaining_debt, d_id))

        return transactions


def main() -> None:
    """Demo showing equal, percentage, and share-based splits."""
    svc = SplitwiseService()

    soumyadeep = svc.add_user("Soumyadeep", "a")
    sumit = svc.add_user("Sumit", "b")
    vashishth = svc.add_user("Vashishth", "c")
    poojan = svc.add_user("Poojan", "d")

    group = svc.create_group(
        "Roommates",
        [soumyadeep.user_id, sumit.user_id, vashishth.user_id, poojan.user_id],
    )
    gid = group.group_id

    e1 = svc.add_expense("Rent", soumyadeep.user_id, 400, EqualSplit(), group_id=gid)
    print(f"Expense: {e1.description} (Rs.{e1.amount})")
    for s in e1.splits:
        print(f"  {s.user.name} owes Rs.{s.amount}")

    e2 = svc.add_expense(
        "Utilities",
        sumit.user_id,
        150,
        PercentageSplit(
            {
                soumyadeep.user_id: 40,
                sumit.user_id: 30,
                vashishth.user_id: 20,
                poojan.user_id: 10,
            }
        ),
        group_id=gid,
    )
    print(f"\nExpense: {e2.description} (Rs.{e2.amount})")
    for s in e2.splits:
        print(f"  {s.user.name} owes Rs.{s.amount}")

    e3 = svc.add_expense(
        "Groceries",
        vashishth.user_id,
        120,
        ExactSplit(
            {
                soumyadeep.user_id: 30,
                sumit.user_id: 20,
                vashishth.user_id: 40,
                poojan.user_id: 30,
            }
        ),
        group_id=gid,
    )
    print(f"\nExpense: {e3.description} (Rs.{e3.amount})")
    for s in e3.splits:
        print(f"  {s.user.name} owes Rs.{s.amount}")

    e4 = svc.add_expense(
        "Lunch",
        soumyadeep.user_id,
        50,
        EqualSplit(),
        debtor_ids=[soumyadeep.user_id, sumit.user_id],
    )
    print(f"\nExpense: {e4.description} (Rs.{e4.amount})")
    for s in e4.splits:
        print(f"  {s.user.name} owes Rs.{s.amount}")

    print("\n--- Net Balances ---")
    for uid, bal in svc.get_balances().items():
        user = svc.get_user(uid)
        status = "is owed" if bal > 0 else "owes"
        print(f"  {user.name} {status} Rs.{abs(bal)}")

    print("\n--- Simplified Debts ---")
    for debtor, creditor, amt in svc.simplify_debts():
        print(f"  {debtor.name} pays {creditor.name} Rs.{amt}")


if __name__ == "__main__":
    main()
