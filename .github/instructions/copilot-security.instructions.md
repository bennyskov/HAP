---
description: "Use when writing code that handles authentication, authorisation, user input, secrets, or any security-sensitive logic. Covers OWASP Top 10 mitigations."
applyTo: "**/*.{py,js,ts,tsx,jsx,cs,java,go,rs,php,rb,swift,kt,md,sql,yml,yaml,json}"
---
# Security Guidelines

## Input Validation
- Validate and sanitise all user-supplied input at system boundaries
- Use allowlists over blocklists
- Reject unexpected data shapes early with descriptive errors

## Secrets & Credentials
- Never hardcode secrets, tokens, or passwords — use environment variables
- Never log secrets, even partially
- Rotate secrets if accidentally committed; invalidate immediately

## Authentication & Authorisation
- Verify identity and permissions on every protected operation
- Never trust client-supplied identity claims without verification
- Enforce least-privilege — grant only what is needed

## SQL / NoSQL
- Always use parameterised queries or an ORM — never interpolate user input into queries
- Validate data types before querying

## Dependencies
- Keep dependencies up to date; check for known CVEs with `npm audit` / `pip-audit`
- Pin versions in lockfiles

## Output Encoding
- Encode output appropriately for the context (HTML, JSON, shell)
- Prevent XSS by avoiding `innerHTML` with user data

## Logging
- Do not log PII, passwords, tokens, or full request bodies
- Use structured logging with severity levels
