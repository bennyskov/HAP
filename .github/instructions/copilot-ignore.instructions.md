---
description: "Defines which files and directories agents must ignore during validation, code search, and execution."
applyTo: "**/*"
---

# Agent Ignore Rules for Validation and Run Operations

## Purpose

Define which files and directories agents must exclude when validating code, selecting targets, and running project commands.

## Mandatory Exclusions

Agents must not use, parse, validate, execute, or modify content from the following paths unless the user explicitly requests it.

### Directories

- .archive/
- logs/
- logs-Copy/
- data/
- credentials/
- temp/
- bin/
- swql/
- node_modules/
- .git/
- .vs/
- obj/
- packages/
- TestResults/

### Files and Patterns

- .vscode/settings.json
- .gitignore
- README.md
- package-lock.json
- yarn.lock
- composer.lock
- *.tmp
- *.temp
- *.log
- *.cache
- *.bak
- *.old
- thumbs.db
- .DS_Store
- desktop.ini

## Validation Rules

- Do not include excluded paths in lint, test, build, static analysis, or search scopes.
- Do not use excluded files as references for code patterns or implementation decisions.
- Do not report findings from excluded paths as actionable project issues.

## Run Rules

- Do not execute scripts, binaries, or SQL files from excluded paths.
- Do not treat log, temp, cache, archive, or credential content as runnable project inputs.
- Resolve run targets only from active source locations in the maintained project tree.

## Security and Safety

- Never read or modify credential-related files unless explicitly requested by the user.
- Treat archive and backup material as historical only, not part of current runtime behavior.
- Ignore binary artifacts unless the user explicitly asks for binary inspection.

## Exception Handling

- Exclusions may be overridden only by an explicit user request.
- If the user asks to include an excluded path, limit work to the requested scope and avoid broad recursive actions.
- When uncertain whether a path is active or archived, prefer excluding it and ask for clarification.

## Agent Behavior Requirements

- Prioritize active, version-controlled source files in current project directories.
- Never suggest edits to excluded paths during normal coding, validation, or run workflows.
- If similarly named files exist in active and archived locations, always choose the active location.
