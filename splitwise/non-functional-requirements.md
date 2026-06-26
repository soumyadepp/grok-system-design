# Splitwise Non-Functional Requirements

## Reliability

- The service must handle invalid input gracefully by raising meaningful exceptions.
- Expense and group data should be stored reliably in memory for the current process and persist in a future implementation.
- The system should avoid data corruption by validating all split allocations before expense creation.

## Usability

- APIs and methods should be intuitive and self-documenting.
- Error messages should be clear and actionable for reviewers and developers.
- Demo usage should be easy to run and understand with minimal setup.

## Maintainability

- The codebase should separate split strategies into modular classes.
- New split methods should be easy to add without modifying core expense logic.
- Domain concepts like User, Group, Expense, and Split should remain clearly defined.

## Performance

- Balance computation should be efficient for a reasonable number of users and expenses.
- Debt simplification should use a greedy algorithm to minimize transaction count without excessive overhead.

## Extensibility

- The system should support adding new split strategies and persistence backends.
- Group and expense models should allow future expansion for features like recurring expenses, currency conversion, and reconciliation.

## Testability

- Core logic should be isolated so it can be covered by unit tests.
- Sample flows should demonstrate behavior clearly and validate expected outputs.
- Each strategy should be verifiable against edge cases such as missing users, invalid totals, and empty debtor groups.
