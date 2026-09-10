---
description: "Use when writing code that handles authentication, authorisation, user input, secrets, or any security-sensitive logic. Covers OWASP Top 10 mitigations."
applyTo: "**/*.{py,js,ts,tsx,jsx,cs,java,go,rs,php,rb,swift,kt,md,sql,yml,yaml,json}"
---
# **1. Security Guidelines**

## **1.1 Input Validation**
- Validate and sanitise all user-supplied input at system boundaries
- Use allowlists over blocklists
- Reject unexpected data shapes early with descriptive errors

## **1.2 Secrets & Credentials**
- Never hardcode secrets, tokens, or passwords — use environment variables
- Never log secrets, even partially
- Rotate secrets if accidentally committed; invalidate immediately

## **1.3 Authentication & Authorisation**
- Verify identity and permissions on every protected operation
- Never trust client-supplied identity claims without verification
- Enforce least-privilege — grant only what is needed

## **1.4 SQL / NoSQL**
- Always use parameterised queries or an ORM — never interpolate user input into queries
- Validate data types before querying

## **1.5 Dependencies**
- Keep dependencies up to date; check for known CVEs with `npm audit` / `pip-audit`
- Pin versions in lockfiles

## **1.6 Output Encoding**
- Encode output appropriately for the context (HTML, JSON, shell)
- Prevent XSS by avoiding `innerHTML` with user data

## **1.7 Logging**
- Do not log PII, passwords, tokens, or full request bodies
- Use structured logging with severity levels
