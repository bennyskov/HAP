---
description: "Applies to code changes across the HAP workspace. Covers general coding conventions, scope discipline, and debugging/workfile hygiene."
applyTo: "**/*.{py,js,ts,tsx,jsx,cs,java,go,rs,php,rb,swift,kt,sql}"
---

# Coding Guidelines

## Scope Discipline

- Prefer minimal, readable, correct edits over broad refactors.
- Keep task scope focused on the asked problem; do not make unrelated edits to notes, logs, or generated artifacts unless explicitly requested.
- Validate only against relevant files and existing checks.

## Language Practices

- Follow best practices for the specific programming language involved when debugging or fixing code.
- Preserve existing project conventions (naming, structure, formatting) over introducing new ad hoc patterns.

## Debugging and Workfiles

- Treat original files as read-only when debugging and creating backups or new scripts for testing.
- Move any temporary work scripts to `.archive AI work scripts` afterward rather than leaving them in active source directories.

## Archived and Duplicate Content

- Never propose changes based on files inside any `.archive/` directory; focus on current implementation, not historical backups.
- Assume references favor non-`.archive` versions when duplicates exist.

## File Hygiene

- After document edits, ensure UTF-8 (with BOM if required by tooling) and LF line endings.
- Ignore build artifacts, lockfiles, and temporary files (`*.tmp`, `*.temp`, `*.log`, `*.cache`, `*.bak`, `*.old`) unless explicitly requested.
