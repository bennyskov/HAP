---
name: hap-restart-chat
description: Re-anchor Copilot on the current HAP workspace so a stuck session can return with a clean, ready-to-work baseline.
---

# Skill Instructions

## Purpose

Use this skill when the current Copilot session feels stuck, confused, or overly influenced by earlier context and you want a clean return to the active HAP workspace.

## Objective

Re-establish a reliable working baseline for the next task by reloading the current workspace guidance, validating the core Copilot customization files, and confirming readiness to continue.

## Scope

This skill is for recovery and re-alignment only.

It should:
- Re-anchor the assistant on the current repository structure.
- Re-read the core workspace instructions and setup references.
- Validate that key Copilot customization files and core docs are present.
- Confirm that the assistant is ready for a new request.

It should not:
- Claim to erase platform-level memory or hidden system instructions.
- Update worklogs by default.
- Make unrelated code or document changes.

## Use When

Use this skill when:
- the current session feels confused or stale
- the assistant appears to have lost the active workspace context
- a recovery pass is needed before resuming the next task
- you need to verify the workspace baseline without making project changes

## Required Files To Re-Read

Reload and align against these files when they exist:
- `.github/copilot-instructions.md`
- `.github/instructions/copilot-ignore.instructions.md`
- `.github/instructions/copilot-coding.instructions.md`
- `.github/instructions/copilot-security.instructions.md`
- `.github/instructions/copilot-markdown.instructions.md`
- `.github/instructions/copilot-testings.instructions.md`
- `.github/chatmodes/hap-default.chatmode.md`

Also review the currently active file if the user already has one open and it is relevant to the next task.

## Recovery Flow

1. Acknowledge that the goal is to restart from a clean working baseline.
2. Re-read the current workspace instructions and core Copilot setup files.
3. Validate that the main customization folders are aligned:
   - `.github/chatmodes/`
   - `.github/docs/`
   - `.github/instructions/`
   - `.github/notes/`
   - `.github/prompts/`
   - `.github/skills/`
4. Check whether key referenced files still exist and note any stale references.
5. Re-state the current working baseline briefly:
   - what the workspace is for
   - which docs define scope
   - which files control Copilot behavior
6. Confirm that the session is ready for a new request.

## Guardrails

- Do not pretend that all memory is gone.
- Re-establish a clean, current, workspace-aligned starting point instead.
- Keep the recovery pass brief and focused on readiness.
- Prefer read-only validation over editing.

## Expected Output

Return a short recovery summary that includes:
- confirmation that the workspace baseline has been reloaded
- any missing or stale file references that should be fixed
- a short statement that the assistant is ready for the next task

## Rule of Thumb

The goal is not to pretend all memory is gone. The goal is to restore a clean, current, workspace-aligned starting point for the next request.
