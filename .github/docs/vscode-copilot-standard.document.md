# **1. VS Code Copilot Standard Essentials**

## **1.1 What the standard is**

The Copilot standard is the current HAP repo guidance that defines how Copilot should organize files, read instructions, and produce changes.

Treat the repository as the source of truth. Do not rely on memory when the live files disagree.

## **1.2 Source files**

Use these as the main standard references:

- [copilot-instructions.md](/Users/bennyskov/Projects/HAP/.github/copilot-instructions.md)
- [copilot-coding.instructions.md](/Users/bennyskov/Projects/HAP/.github/instructions/copilot-coding.instructions.md)
- [copilot-markdown.instructions.md](/Users/bennyskov/Projects/HAP/.github/instructions/copilot-markdown.instructions.md)
- [copilot-security.instructions.md](/Users/bennyskov/Projects/HAP/.github/instructions/copilot-security.instructions.md)
- [copilot-testings.instructions.md](/Users/bennyskov/Projects/HAP/.github/instructions/copilot-testings.instructions.md)
- [chatmodes/](/Users/bennyskov/Projects/HAP/.github/chatmodes)
- [prompts/](/Users/bennyskov/Projects/HAP/.github/prompts)
- [skills/](/Users/bennyskov/Projects/HAP/.github/skills)

## **1.3 Essentials**

- Keep each file in the standard location for its job.
- Use short, direct guidance.
- Keep scope narrow and avoid unrelated edits.
- Respect ignore and protected paths.
- Prefer minimal, correct changes.
- Use numbered markdown headings for repo docs.

## **1.4 What good looks like**

- The file type matches the task.
- Instructions are current and easy to follow.
- Skills are reusable and action-oriented.
- Chatmodes and prompts are clearly scoped.
- No stale references point to archived or ignored content.

## **1.5 Rule of thumb**

If a file helps Copilot behave better in HAP, it should be small, current, and placed where the repo already expects that kind of guidance.

