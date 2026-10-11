---
name: hap-propagate-standard
description: Use this skill to sync HAP's Copilot standard files into sibling subproject repos (BUD, STRM, future projects) and to bootstrap a new subproject's .github scaffold from HAP's templates.
---

# **1. Skill Instructions**

## **1.1 Purpose**

HAP, BUD, STRM, and future projects are **separate git repositories** living as siblings under `~/Projects/`. Copilot reads `.github/copilot-instructions.md` from whichever repo root is open, so there is no automatic inheritance between them — each repo must carry its own copy of the shared standard.

Use this skill to keep that copy current: propagate HAP's canonical `.github` template files into a subproject repo, or bootstrap `.github` from scratch in a subproject that doesn't have one yet (e.g. STRM).

## **1.2 File classes**

Not every `.github` file is copied the same way. Classify each file before syncing:

### **1.2.1 Shared, byte-identical (copy as-is)**

These carry no project name and must match HAP exactly:

- `.github/instructions/copilot-ignore.instructions.md`
- `.github/instructions/copilot-markdown.instructions.md`
- `.github/instructions/copilot-security.instructions.md`
- `.github/instructions/copilot-testings.instructions.md`

### **1.2.2 Templated (copy, then substitute the project name)**

These are structurally identical to HAP's version but reference the project name in the description, title, and a couple of section headers:

- `.github/instructions/copilot-coding.instructions.md`
- `.github/instructions/copilot-standard.instructions.md`
- `.github/docs/vscode-copilot-standard.document.md` (substitute the project name and rewrite the absolute file-link paths to the target project's own directory)
- `.github/docs/*-self-learning.document.md` (rename to `<project>-self-learning.document.md`)
- `.github/agents/*-default.agent.md` (rename to `<project>-default.agent.md`)

### **1.2.3 Project-owned (never copy from HAP; author per-project)**

These describe the project's own mission and must not be overwritten by a sync:

- `.github/copilot-instructions.md` (mission, sources of truth, project-specific overrides section)
- `.github/docs/*-objective.document.md`
- `.github/docs/base-hermes-overview.document.md` — HAP's copy is a living runtime snapshot updated by `hap-maintenance`; a subproject's copy should be a short, project-authored pointer back to HAP's install (see BUD's version for the established pattern), not a synced duplicate. Do not propagate HAP's copy verbatim into a subproject.
- `.github/skills/*` (project-specific workflows)
- Any project-specific `.github/instructions/*.instructions.md` beyond the shared four

## **1.3 Sync flow (existing subproject, e.g. BUD)**

1. In HAP, confirm the file is current: run the `hap-copilot-standard-check` skill first.
2. Diff each shared/templated file against the target repo's copy:

   ```bash
   diff /Users/bennyskov/Projects/HAP/.github/instructions/copilot-ignore.instructions.md \
        /Users/bennyskov/Projects/BUD/.github/instructions/copilot-ignore.instructions.md
   ```

3. For shared byte-identical files, copy directly.
4. For templated files, copy then substitute the project name/description (do not hand-edit structure, only the name).
5. Leave project-owned files untouched.
6. Commit the change **inside the target repo** (separate git history — this is not a cross-repo commit):

   ```bash
   cd /Users/bennyskov/Projects/BUD
   git add .github
   git commit -m "Sync Copilot standard files from HAP"
   ```

7. Re-run `hap-copilot-standard-check` inside the target repo to confirm the standard is upheld after the sync.

## **1.4 Bootstrap flow (new subproject with no `.github` yet, e.g. STRM)**

1. Create the standard directories: `.github/instructions/`, `.github/agents/`, `.github/docs/`, `.github/skills/`.
2. Copy the shared and templated files per **1.2**, substituting the new project's name.
3. Write a new `.github/copilot-instructions.md` for the project modeled on an existing one (BUD's is a good template), with its own mission, scope, and a final project-conventions section for intentional deviations.
4. Write a new `<project>-objective.document.md` describing the project's actual scope — move it from HAP's `docs/` if HAP was holding it as a placeholder before the subproject existed.
5. Write a new `<project>-default.agent.md` modeled on `hap-default.agent.md` / `bud-default.agent.md`.
6. Leave `.github/skills/` empty until project-specific workflows exist, or move skills in from HAP only once their referenced scripts/config actually live in the subproject (do not move a skill file ahead of the code/config it documents — that creates a scaffold that points at the wrong repo).
7. Run `hap-copilot-standard-check` inside the new subproject to confirm the scaffold is upheld.
8. If the repo isn't initialized in git yet, use the `hap-sync-copied-library` skill to init and push it.

## **1.5 Versioning note**

There is no formal version number on the standard. Treat the HAP copies as canonical and current-dated. When a shared or templated file changes in HAP, re-run **1.3** against every subproject rather than letting copies drift silently.

## **1.6 Guardrails**

- Never overwrite a project-owned file (1.2.3) during a sync.
- Never move a skill or script reference into a subproject before the code it governs has actually moved there — a skill pointing at paths in the wrong repo is worse than no skill.
- Do not invent a project name substitution scheme beyond what's already used (plain project name in descriptions/titles, as seen in BUD's copies).
