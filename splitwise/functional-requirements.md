# Splitwise Functional Requirements

## Core User Management

- Users must be able to register with a unique ID and display name.
- Users must be retrievable by ID for expense and group operations.
- The system must validate user existence before recording expenses or groups.

## Group Management

- Users must be able to create groups with a name and a list of member IDs.
- Groups must store members and associated expenses.
- The service must validate all group member IDs when creating a group.

## Expense Management

- Users must be able to add an expense with:
  - description
  - payer ID
  - total amount
  - split strategy
  - debtor IDs or group ID
- The system must support multiple split strategies, including:
  - equal split
  - percentage split
  - exact amount split
- Expenses must record each debtor's share using `Split` objects.
- The service must reject invalid expense amounts (non-positive values).

## Split Strategy Validation

- Equal split must divide the total amount equally among specified users.
- Percentage split must accept per-user percentages that sum to 100.
- Exact split must accept explicit amounts per user and validate that they sum to the total expense.
- Split operations must reject empty debtor lists and missing allocation entries.

## Balances and Settlement

- The system must compute user balances from recorded expenses.
- Positive balances mean the user is owed money; negative balances mean the user owes money.
- Balances must be aggregated across all expenses or scoped to a group.
- The system must simplify debts by matching creditors to debtors to minimize transactions.

## Error Handling

- The system must raise clear exceptions for:
  - missing users
  - missing groups
  - invalid split definitions
  - invalid expense parameters

## Demo and Example Flow

- The repository should include a working sample flow demonstrating:
  - user creation
  - group creation
  - expense creation with multiple split strategies
  - balance calculation
  - simplified debt settlement
