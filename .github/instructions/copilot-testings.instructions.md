---
description: "Use when writing, fixing, or reviewing tests. Covers test structure, naming, mocking, and coverage expectations for unit and integration tests."
applyTo: "**/*.test.*,**/*.spec.*,tests/**"
---
# Testing Guidelines

## Structure
- One test file per source file, co-located or in `tests/`
- Group related tests with `describe` blocks named after the unit under test
- Test names: "should [do something] when [condition]"

## Coverage Expectations
- All public functions must have at least one test
- Cover: happy path, edge cases, and error scenarios
- Integration tests for external I/O (DB, API, filesystem)

## Mocking
- Mock at the boundary — external services, DBs, network calls
- Use real implementations for pure business logic
- Restore mocks after each test (`afterEach`)

## Assertions
- One logical assertion per test where practical
- Use specific matchers (`.toEqual`, `.toThrow`) over `.toBeTruthy`
- Test behaviour, not implementation details

## Anti-patterns
- Don't test private methods directly
- Don't use `setTimeout` or real delays — use fake timers
- Don't share mutable state between tests

## Test Documentation Maintenance
- Keep `tests/testsGuide.md` up to date whenever new tests are added.
- If an existing test changes scope or intent, update `tests/testsGuide.md` in the same change.