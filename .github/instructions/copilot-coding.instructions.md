---
description: "Use when writing, reviewing, or refactoring Python code. Covers naming conventions, typing, error handling, function design, and code organisation."
applyTo: "src/**/*.py,scripts/**/*.py,tools/**/*.py,tests/**/*.py"
---
# Python Coding Best Practices

## Naming and Style
- Follow PEP 8 style conventions.
- Use `snake_case` for variables, functions, and module names.
- Use `PascalCase` for classes and exceptions.
- Use `UPPER_SNAKE_CASE` for constants.
- Prefer descriptive names over abbreviations unless the abbreviation is standard.

## Functions and Classes
- Keep functions focused on one responsibility.
- Prefer small, composable functions over long procedural blocks; aim to keep functions under ~30 lines when practical.
- Add type hints for function parameters and return values.
- Use dataclasses for structured data objects when behavior is minimal.
- Avoid hidden side effects; make state changes explicit in function names and signatures.
- Prefer pure functions and return values over mutating arguments.

## Error Handling
- Raise specific exception types instead of generic `Exception`.
- Add actionable context to error messages.
- Validate input at boundaries (CLI entry points, API handlers, file/IO interfaces).
- Do not silently swallow exceptions; either handle them meaningfully or re-raise.
- Use `finally` or context managers for resource cleanup.

## Imports and Dependencies
- Group imports as: standard library, third-party packages, local modules.
- Keep imports explicit; avoid wildcard imports.
- Remove unused imports.
- Avoid circular imports by extracting shared logic to dedicated modules.

## State, Data, and Side Effects
- Prefer immutable data flow where practical.
- Keep business logic separate from IO, framework glue, and CLI concerns.
- Pass dependencies explicitly instead of relying on hidden globals.
- Use context managers (`with`) for files, locks, and network resources.

## Comments and Documentation
- Write comments that explain why, not what.
- Add docstrings for public modules, classes, and functions.
- Keep examples and documentation aligned with current behavior.
- Document assumptions, constraints, and non-obvious edge cases.

## Testing Expectations
- Write unit tests for core logic and regression tests for bug fixes.
- Test behavior and outcomes, not internal implementation details.
- Keep tests deterministic and isolated.
- Use clear test names that describe the expected behavior.

## Project Naming Convention
- Use `HAP` for project references in filenames, docs, identifiers, and user-facing text.
- Keep executable command syntax as `hermes` when commands are documented.

## General Coding Standards
- Keep modules, functions, and classes narrowly scoped and easy to reuse.
- Make error messages specific enough to identify the failing path or input.
- Prefer explicit, readable control flow over clever shortcuts.
- Keep comments focused on non-obvious decisions, constraints, or workarounds.
