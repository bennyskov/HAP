---
name: hap-copilot-standard-check
description: Use this skill to verify the current HAP Copilot standard against the latest repo guidance and report whether it is upheld.
---

# Skill Instructions

## **1. Purpose**

Use this skill to check whether the current HAP Copilot standard is up to date and whether the repository still follows it.

## **1.1 Use When**

- reviewing Copilot instructions, docs, chatmodes, prompts, or skills
- checking for drift after edits
- validating that a new file belongs in the right Copilot location
- confirming whether the current standard is upheld

## **1.2 Standard Sources**

Re-read the latest current files before giving a verdict:

- `.github/copilot-instructions.md`
- `.github/instructions/*.instructions.md`
- `.github/chatmodes/*.chatmode.*`
- `.github/prompts/*.prompt.md`
- `.github/skills/*/SKILL.md`
- `.github/docs/*.document.md`
- repo-specific Copilot config files when they define behavior, such as `.github/chatmodes/custom_chatmode.json`

## **1.3 Check Flow**

1. Re-read the latest source files.
2. Compare the repo layout with the documented standard.
3. Flag stale names, missing files, ignored-path drift, and outdated references.
4. Decide whether the standard is upheld.
5. Report only concrete findings and a short verdict.

## **1.4 What to Verify**

- file type matches its role
- instructions live in the right scoped file
- docs stay short, current, and readable
- skills are reusable and action-oriented
- chatmodes are clearly scoped
- ignore and protected paths are respected
- headings and filenames follow repo conventions

## **1.5 Output**

Return:

- `Verdict: upheld / partially upheld / not upheld`
- concise findings
- files that need updates
- one short next step

## **1.6 Guardrails**

- Do not edit files unless explicitly asked
- Do not treat archived content as current
- Do not invent a standard that is not present in the repo

