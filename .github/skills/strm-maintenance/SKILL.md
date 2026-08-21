---
name: strm-maintenance
description: Use this skill for repeatable maintenance of the streaming infrastructure.
---

# Skill Instructions

## Purpose

Use this skill for repeatable maintenance and operation of the `strm` streaming-support workflows.

The skill covers request-driven flows that retrieve streaming access codes or activation outcomes for approved requesters, while keeping the process safe, traceable, and easy to maintain.

## Scope Boundary

- This skill is limited to streaming-provider support workflows and their operational maintenance.
- It is appropriate for trigger validation, provider-specific code retrieval, email matching, fallback handling, state tracking, and related checks.
- It does not cover general framework maintenance, macOS maintenance, or unrelated messaging automation.

## Use When

- Verifying or maintaining the streaming code-retrieval workflow.
- Checking whether trigger handling still works for a supported provider.
- Reviewing provider-specific matching, extraction, or fallback logic.
- Validating allowlist routing, state files, or deduplication behavior.
- Updating or checking the scripts that support Netflix, Viaplay, or TV2 Play flows.
- Reviewing logs, state files, or test coverage related to the streaming-support process.

## Inputs

- Provider name, such as `netflix`, `viaplay`, or `tv2play`.
- Trigger source or trigger example when relevant.
- Expected outcome to validate, such as code extraction, expired-link handling, forwarding, or duplicate prevention.
- Optional scope: `trigger`, `provider`, `routing`, `state`, `tests`, `docs`.

## Trigger Model

The standard request pattern is:

```text
<phone_number>: <provider> code
```

Example:

```text
+4512345678: netflix code
```

Core rules:
- The requester must be allowlisted.
- Only approved requesters may receive a reply.
- The workflow must not fabricate a successful result when the provider email, link, or code cannot be verified.

## Important Components

Typical files involved in this skill include:
- `scripts/wait-for-netflix-email`
- `scripts/wait-for-viaplay-email`
- `scripts/install-wait-for-netflix-email-schedule.sh`
- `scripts/install-wait-for-viaplay-email-schedule.sh`
- `tests/test_netflix_flow.py`
- `config/code-forward-destinations.csv`
- provider-specific state files under `config/`

Use the project objective in `.github/docs/strm-project-objective.document.md` as the scope reference when deciding whether a task belongs in `strm`.

## Standard Workflow

1. Identify the provider and the expected behavior to validate.
2. Confirm that the requester validation path is clear.
3. Confirm which script, state file, and routing file are involved.
4. Check provider-specific matching and extraction logic.
5. Verify fallback behavior for missing emails, expired links, unknown DOM states, or duplicate events.
6. Check whether forwarding, optional deletion, and state persistence still follow the intended rules.
7. Review or run relevant tests when available.
8. Update documentation only when the workflow, supported providers, or operational behavior changed.

## Provider Maintenance Checklist

For a supported provider, validate these areas:
- trigger recognition
- allowlist validation
- email or activation lookup
- code or state extraction
- fallback responses
- forwarding behavior
- duplicate prevention
- state file updates
- log clarity

## Safety Rules

- Never expose tokens, credentials, or secret values in docs, logs, or commits.
- Never send responses to requesters who are not allowlisted.
- Report failure conditions directly instead of improvising a success result.
- Keep logs useful for troubleshooting without leaking sensitive data.
- Treat live provider behavior as variable over time; if the upstream service changes, record the mismatch clearly.

## Outputs

- A short summary of what part of the streaming workflow was checked.
- Pass/fail status for the relevant provider behavior.
- Any routing, extraction, or state-management issue found.
- Suggested follow-up actions, such as script updates, test updates, or doc updates, when needed.
