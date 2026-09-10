---
description: "Defines the HAP Copilot layout and operating standard."
applyTo: "**/*"
---

# **1. Copilot Standard for HAP**

## **1.1 Purpose**

This document defines the standard Copilot layout and operating rules for the HAP workspace.

## **1.2 Standard layout**

When creating or updating AI guidance, use this structure:

- `.github/copilot-instructions.md` — repo-wide baseline
- `.github/instructions/*.instructions.md` — scoped instruction files
- `.github/agents/*.agent.md` — reusable custom agents
- `.github/prompts/*.prompt.md` — legacy prompt files retained only when compatibility requires them
- `.github/skills/*/SKILL.md` — reusable workflows and operating procedures
- `.github/docs/*.document.md` — project documents and standards

## **1.3 Naming conventions**

- Instruction files use the `*.instructions.md` suffix.
- Legacy prompt files use the `*.prompt.md` suffix.
- Custom agent files use the `*.agent.md` suffix.
- Skill folders use a short descriptive name with a `SKILL.md` file inside.
- Project documents use the `*.document.md` suffix when they define repo rules or objectives.

## **1.4 When to use each layer**

### **1.4.1 Repo baseline**
Use `.github/copilot-instructions.md` for the global behavior, scope, and project standards.

### **1.4.2 Scoped instructions**
Use `.github/instructions/*.instructions.md` for focused rules such as coding, markdown, testing, security, and ignore behavior.

### **1.4.3 Custom agents**
Use `.github/agents/*.agent.md` for reusable AI personas such as maintenance, review, or debugging.

### **1.4.4 Skills**
Use `.github/skills/*/SKILL.md` when the task is a multi-step operating procedure that should be reusable and packaged clearly.

### **1.4.5 Legacy prompts**
Do not create new `.github/prompts/*.prompt.md` files when a skill can provide the workflow. Prompt files are deprecated for Agent Host sessions and should be migrated to skills when encountered.

## **1.5 Safety and scope rules**

- Keep generated, archived, and credentialed content out of normal validation and execution paths.
- Ignore `.archive/`, `data/`, `logs/`, `credentials/`, `temp/`, `bin/`, and similar protected areas unless the task explicitly targets them.
- Prefer current source files over historical or duplicated artifacts.
- Avoid broad refactors and unrelated edits when handling a narrow request.

## **1.6 HAP-specific standard**

HAP uses a standards-aligned repo layout:

1. Global behavior lives in `.github/copilot-instructions.md`.
2. Scoped guidance lives in `.github/instructions/`.
3. Reusable operations live in `.github/skills/`.
4. Reusable custom agents live in `.github/agents/`.
5. Project documents and reference material live in `.github/docs/`.

This keeps Copilot behavior clear, discoverable, and easier to maintain than ad hoc rules or hidden custom logic.
