---
description: "Applies to code changes across the HAP workspace. Covers general coding conventions, scope discipline, and debugging/workfile hygiene."
applyTo: "**/*.{py,js,ts,tsx,jsx,cs,java,go,rs,php,rb,swift,kt,sql}"
---

# **1. Coding Guidelines**

## **1.1 Scope Discipline**

- Prefer minimal, readable, correct edits over broad refactors.
- Keep task scope focused on the asked problem; do not make unrelated edits to notes, logs, or generated artifacts unless explicitly requested.
- Validate only against relevant files and existing checks.

## **1.2 Language Practices**

- Follow best practices for the specific programming language involved when debugging or fixing code.
- Preserve existing project conventions (naming, structure, formatting) over introducing new ad hoc patterns.

## **1.3 Debugging and Workfiles**

- Treat original files as read-only when debugging and creating backups or new scripts for testing.
- Use the session workspace for temporary work scripts and remove them when finished; do not leave them in active source directories or move them into protected project paths.

## **1.4 Archived and Duplicate Content**

- Never propose changes based on files inside any `.archive/` directory; focus on current implementation, not historical backups.
- Assume references favor non-`.archive` versions when duplicates exist.

## **1.5 File Hygiene**

- After document edits, ensure UTF-8 (with BOM if required by tooling) and LF line endings.
- Ignore build artifacts, lockfiles, and temporary files (`*.tmp`, `*.temp`, `*.log`, `*.cache`, `*.bak`, `*.old`) unless explicitly requested.
