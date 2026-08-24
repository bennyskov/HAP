---
description: "Defines the HAP Copilot layout and operating standard."
applyTo: "**/*"
---

# Copilot Standard for HAP

## Purpose

This document defines the standard Copilot layout and operating rules for the HAP workspace.

## Standard layout

When creating or updating AI guidance, use this structure:

- `.github/copilot-instructions.md` — repo-wide baseline
- `.github/instructions/*.instructions.md` — scoped instruction files
- `.github/chatmodes/*.chatmode.md` — reusable chat modes
- `.github/prompts/*.prompt.md` — reusable prompts
- `.github/skills/*/SKILL.md` — reusable workflows and operating procedures
- `.github/docs/*.document.md` — project documents and standards

## Naming conventions

- Instruction files use the `*.instructions.md` suffix.
- Prompt files use the `*.prompt.md` suffix.
- Chat mode files use the `*.chatmode.md` suffix.
- Skill folders use a short descriptive name with a `SKILL.md` file inside.
- Project documents use the `*.document.md` suffix when they define repo rules or objectives.

## When to use each layer

### Repo baseline
Use `.github/copilot-instructions.md` for the global behavior, scope, and project standards.

### Scoped instructions
Use `.github/instructions/*.instructions.md` for focused rules such as coding, markdown, testing, security, and ignore behavior.

### Chat modes
Use `.github/chatmodes/*.chatmode.md` for reusable AI interaction modes such as maintenance, review, or debugging.

### Skills
Use `.github/skills/*/SKILL.md` when the task is a multi-step operating procedure that should be reusable and packaged clearly.

### Prompts
Use `.github/prompts/*.prompt.md` for single-purpose reusable prompts that are task-specific and cleanly scoped.

## Safety and scope rules

- Keep generated, archived, and credentialed content out of normal validation and execution paths.
- Ignore `.archive/`, `data/`, `logs/`, `credentials/`, `temp/`, `bin/`, and similar protected areas unless the task explicitly targets them.
- Prefer current source files over historical or duplicated artifacts.
- Avoid broad refactors and unrelated edits when handling a narrow request.

## HAP-specific standard

HAP uses a standards-aligned repo layout:

1. Global behavior lives in `.github/copilot-instructions.md`.
2. Scoped guidance lives in `.github/instructions/`.
3. Reusable operations live in `.github/skills/`.
4. Reusable interaction modes live in `.github/chatmodes/`.
5. Project documents and reference material live in `.github/docs/`.

This keeps Copilot behavior clear, discoverable, and easier to maintain than ad hoc rules or hidden custom logic.
