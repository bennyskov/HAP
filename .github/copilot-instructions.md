---
applyTo: "**/*"
---

# **1. Copilot Instructions for HAP**

## **1.1 Mission**

This repository is the HAP workspace for Hermes tooling, runtime maintenance, and project-level conventions in VS Code. Keep all work aligned with the active project structure and the current repo guidance.

## **1.2 Default behavior**

- Use the active repository as the source of truth.
- Prefer current files over archived, generated, or duplicate content.
- Keep scope narrow and directly tied to the user request.
- Prefer minimal, correct changes over broad refactors.
- Do not modify ignored or protected paths unless the task explicitly requires it.

## **1.3 Standard Copilot layout**

Use this structure for project guidance:

- `.github/copilot-instructions.md` — repo-wide baseline instructions
- `.github/instructions/*.instructions.md` — scoped rules for tasks and file types
- `.github/instructions/copilot-standard.instructions.md` — standard Copilot layout and conventions
- `.github/agents/*.agent.md` — reusable custom agents
- `.github/prompts/*.prompt.md` — legacy prompt files retained only when compatibility requires them; prefer skills for reusable workflows
- `.github/skills/*/SKILL.md` — reusable workflows and operating procedures
- `.github/docs/*.document.md` — project documents and reference material

## **1.4 Scope boundaries**

- Respect the ignore rules in `.github/instructions/copilot-ignore.instructions.md`.
- Treat `.archive/`, `logs/`, `data/`, `credentials/`, `temp/`, and similar generated or protected areas as out of scope unless explicitly requested.
- Do not touch hidden or system-managed files unless the task specifically requires it.

## **1.5 Working rules**

- Keep markdown headings structured and numbered consistently.
- Preserve project conventions over ad hoc formatting.
- Prefer concise, concrete guidance over long speculation.
- Use the active repo docs as the canonical source of intent.
- Read [`.github/instructions/copilot-standard.instructions.md`](/Users/bennyskov/Projects/HAP/.github/instructions/copilot-standard.instructions.md) when you need the HAP Copilot layout standard in one place.

## **1.6 Coding expectations**

- Prefer minimal, readable, correct edits.
- Keep task scope focused on the asked problem.
- Validate only against relevant files and existing checks.
- Do not make unrelated edits to notes, logs, or generated artifacts unless explicitly requested.

## **1.7 Naming conventions**

- Instruction files: `*.instructions.md`
- Legacy prompt files: `*.prompt.md`; do not create new ones when a skill can provide the workflow
- Custom agent files: `*.agent.md`
- Skill directories: `name/SKILL.md`
- Project docs: `*.document.md`

Use these standard file types before creating ad hoc JSON or custom one-off structures.
