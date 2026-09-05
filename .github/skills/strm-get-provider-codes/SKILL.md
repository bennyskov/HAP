---
name: strm-get-provider-codes
description: Use this skill for repeatable maintenance of the streaming infrastructure and email handling.
---

# **1. Skill Instructions**

## **1.1 Purpose**

Use this skill for repeatable maintenance of streaming-provider login-code handling.

## **1.2 Run Mode**

- Use the Hermes agent to build and run this skill.
- Keep all scripts in `scripts/`.
- Use Python for all scripts.
- Keep scripts runnable from the command line and callable from other scripts.
- Use `framework.py` as the default shared framework.
- Prefer reusable functions in a shared functions module.
- Add any new dependencies to the project `requirements.txt`.
- Keep the implementation modular and covered by tests.
- The inbox poller should run every 30 seconds by default.
- The poller should load project credentials from `config/KEYS.md` and support the `BOT_EMAIL_*` aliases used by the workspace.

## **1.3 Runtime Inputs**

- Supported providers default to all configured providers.
- Allow a provider to be passed as an argument.

## **1.4 Workflow**

### **1.4.1 Start point**

- Start at Step 1 unless the user explicitly asks to resume from a later step.
- If the user gives a step number, begin from that step and continue to the end.
- If the user asks to rerun, restart from Step 1.

### **1.4.2 Step 1 — Load configuration**

- Read `config/code-forward-providers.csv` for supported providers and code-extraction patterns.

### **1.4.3 Step 2 — Validate the request**

- Confirm the requested provider is supported.

### **1.4.4 Step 3 — Monitor provider mail**

- Watch the inbox `bennyskov@hotmail.com` for incoming provider emails.
- Handle login-code emails only for supported providers.
- Run this skill as a scheduled poller every 30 seconds (for example via launchd or cron) so it regularly checks for new requests.

### **1.4.5 Step 4 — Extract the code**

- Extract the temporary login code from the email body or subject using the configured provider pattern.
- Save the extracted code in the project workflow or storage used by this skill.

### **1.4.6 Step 5 — Forward the email**

- Forward the received mail to `bsjunk13@hotmail.com`.
- Forward the code through the Telegram bot `@ViaplayCodeBot` using `TELEGRAM_TOKEN`.
- Read bot keys and IDs from environment variables.
- Use `config/code-forward-destinations.csv` for the Telegram chat id for `bsjunk13@hotmail.com`.
- Do not hardcode bot tokens, chat IDs, or other credentials.
- After successful processing and forwarding, delete the original mail from the inbox.

### **1.4.7 Step 6 — Apply provider-specific flow**

- Follow the provider-specific login procedure where needed.
- For Viaplay, if the user is on the home network, they can log in directly.
- If the user is not on the home network, they can request a temporary code.

## **1.5 Guardrails**

- Do not log secrets, passwords, or full credentials.
- Keep the implementation small, reusable, and testable.
- Prefer shared helpers over duplicated logic.

## **1.6 Supported Providers**

- Netflix
- Viaplay
- TV2Play
