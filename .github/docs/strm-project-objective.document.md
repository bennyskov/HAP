# Project Objective: Hermes Streaming Maintenance (STRM)

## Objective

The purpose of `STRM` is to build and maintain a reliable streaming-support workflow that can receive approved trigger messages, retrieve the latest one-time access code or activation state for a supported provider, and return a safe, traceable response to the requester.

This project is focused on streaming access-code handling and related maintenance workflows. It should turn a manual, repetitive process into a controlled and repeatable automation flow.

## Scope

`STRM` is limited to streaming-provider support workflows and the automation required to keep them working.

Included in scope:
- Request-driven retrieval of one-time streaming access codes.
- Approved trigger handling through configured messaging channels.
- Provider-specific extraction logic for supported streaming services.
- Forwarding, optional cleanup, deduplication, and state tracking.
- Logging, traceability, and maintenance of the streaming support flow.
- Validation of provider-specific behavior such as expired links, missing emails, and fallback responses.

Excluded from scope:
- General framework maintenance.
- macOS or Hermes runtime maintenance.
- Unrelated messaging automation.
- Broad media-management or subscription-management tasks outside the code-retrieval flow.

## Naming and Structure Alignment

This document is aligned to the current project file name `strm-project-objective.document.md` and the related skill name `strm-streaming-maintenance`.

The previous title `hermes-code-activations (STCA)` did not match the active file structure. The current project name should be treated as:
- **Hermes Streaming Maintenance** (`STRM`)

## Business Outcome

The project should:
- Reduce manual effort when retrieving streaming login or activation codes.
- Provide quick, request-driven responses for supported providers.
- Keep a traceable and repeatable process with clear logging and deduplication.
- Make streaming support workflows easier to maintain as providers change behavior over time.

## What This Project Should Do

`STRM` should help answer practical questions such as:

- Did an approved requester send a valid trigger?
- Was a matching provider email found?
- Was the code or activation state extracted successfully?
- Is the link or code still valid?
- Was the requester notified with the correct response?
- Was the event logged and persisted so duplicates are avoided?

## Trigger Model

The current request pattern is based on a provider-specific trigger message in the form:

```text
<phone_number>: <provider> code
```

Example:
- `+4512345678: netflix code`

Core trigger rules:
- The requester handle must be allowlisted.
- Only approved handles may receive a response.
- Trigger ingestion may come from configured sources such as gateway logs, WhatsApp bridge integrations, or Telegram bot polling.

## Supported Flow Pattern

The shared workflow for supported providers should be:

1. Detect an incoming trigger.
2. Validate the requester against the allowlist.
3. Run the provider-specific lookup and extraction flow.
4. Return a status message or code to the requester.
5. Forward the matched email where required.
6. Optionally delete the original message if configured.
7. Persist state so the same trigger is not processed twice.

## Current Provider Direction

The active project direction includes support for flows such as:
- Viaplay
- Netflix
- TV2 Play

Provider implementations may differ, but they should follow the same framework of:
- trigger validation
- email or activation lookup
- provider-specific extraction
- fallback handling
- logging and deduplication

## Important Components

This project is supported by assets such as:
- provider-specific scripts under `scripts/`
- scheduler or launchd installation helpers under `scripts/`
- tests under `tests/`
- state and routing files under `config/`

Typical examples in the current structure include:
- `scripts/wait-for-viaplay-email`
- `scripts/wait-for-netflix-email`
- `scripts/install-wait-for-viaplay-email-schedule.sh`
- `scripts/install-wait-for-netflix-email-schedule.sh`
- `tests/test_netflix_flow.py`
- `config/code-forward-destinations.csv`
- provider-specific state files in `config/`

## Security and Control Requirements

This project must preserve strict control over access and secrets.

Important requirements:
- Only allowlisted requester handles may receive codes or status replies.
- Tokens, credentials, and secret values must never be hardcoded in documents, logs, or commits.
- Sensitive values must be loaded from local configuration or environment variables.
- Logs must support troubleshooting without exposing secrets.
- Failure conditions must be reported honestly instead of guessing or fabricating successful outcomes.

## Success Criteria

The project is successful when:
- A valid trigger from an approved requester returns the correct code or a clear status response.
- Duplicate events do not produce duplicate replies.
- Expired or invalid provider states are detected and reported clearly.
- Logs and state files provide enough traceability for troubleshooting.
- Provider workflows remain maintainable as scripts, tests, and state handling evolve.

## Responsibility Boundary

`STRM` should answer the question: "How do we keep request-driven streaming support workflows reliable, safe, and easy to operate?"

If the work is about shared tooling or reusable automation patterns, it belongs in `FRWK`.
If the work is about maintaining the machine or Hermes runtime, it belongs in `BASE`.
