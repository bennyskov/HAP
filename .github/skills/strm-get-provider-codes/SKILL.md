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
- `link_text` is the exact visible hyperlink text for flows that open an email
  link. `code_pattern` is the provider-specific regular expression used to
  extract a code; its first capture group is the delivered code.
- `search_string` matches the provider request email. `code_search_string`
  independently validates visible text in a code email, allowing request and
  code wording to differ without weakening provider validation.

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
- Forward every provider message involved in the current flow before deleting
  any of those messages.
- Delete only the exact processed source messages, and only after every
  required email forward and Telegram acknowledgement succeeds. If any
  forward or Telegram acknowledgement fails, retain all messages that have
  not already been deleted and surface only a sanitized error.

### **1.4.7 Step 6 — Apply provider-specific flow**

- Follow the provider-specific login procedure where needed.

#### **1.4.7.1 Viaplay**

- If the user is on the home network, they can log in directly.
- If the user is not on the home network, they can request a temporary code.
- Forward the matched Viaplay email to `bsjunk13@hotmail.com`, send the code
  through Telegram and require acknowledgement, and only then delete the exact
  original message.
- If either the email forward or Telegram acknowledgement fails, do not delete
  the original Viaplay message.

#### **1.4.7.2 TV2 Play**

- When reading a matching TV2 Play email, find the exact visible link text
  `Bekræft midlertidig adgang`.
- Resolve and open only the hyperlink directly associated with or beneath that
  text. Do not follow an unrelated link.
- Before making the request, validate that the resolved URL uses HTTPS and has
  an expected TV2-owned host.
- Consider activation successful only when the request returns HTTP 200 or an
  explicit `OK` success response. At that point, consider temporary access
  granted; do not refresh or reread the original request message to confirm it.
- After successful activation, wait for a separate, newly received TV2 Play
  confirmation email whose normalized visible heading or text is exactly
  `Midlertidig adgang er bekræftet.`. The confirmation normally arrives about
  one minute after activation.
- Poll the inbox every 30 seconds for up to 120 seconds. Match only a
  confirmation received at or after the activation/request message timestamp,
  or the activation start timestamp when that is the reliable boundary. The
  confirmation must have a different message ID from the request, and stale
  confirmations must not satisfy this gate.
- After confirmation, send exactly `TV2PLAY bekræftet` through the configured
  Telegram bot and destination and require acknowledgement. Then forward both
  the activation-request email and the separate confirmation email to
  `bsjunk13@hotmail.com`. If they have no login code, do not send a code
  message.
- Only after activation, confirmation, acknowledged Telegram success, and
  both email forwards succeed, delete the exact matched request and
  confirmation messages by their message IDs. Do not delete unrelated
  messages. If notification or either forward fails, retain both messages and
  surface only a sanitized error.
- If no qualifying confirmation arrives within 120 seconds, send exactly
  `TV2PLAY bekræftelse fejlede` and require acknowledgement. Then forward the
  processed request message. Only after both actions succeed, delete that
  exact request message and retain all unrelated mail. If acknowledgement or
  forwarding fails, retain the request message and surface a sanitized
  failure.
- If the activation response or request fails for any reason, including a
  reliably classified expired or already-used link, immediately stop success
  processing and send exactly `TV2PLAY bekræftelse fejlede` through the
  configured Telegram bot and destination.
- Treat normalized visible activation-response text or a heading that is
  exactly `Der skete en fejl` as an old or expired TV2 Play link. Do not match
  longer text or substring lookalikes.
- Require acknowledgement of the Telegram failure notification. If that
  notification fails, report it separately using only a sanitized status or
  category.
- After an activation response or request failure, forward every TV2 Play
  message actually involved or available in that run (normally the activation
  request, plus a matched confirmation if one was found). Delete only those
  exact messages, using their matched message IDs, and only after the Telegram
  failure notification and all required forwards are acknowledged. Do not send
  the success message.
- If the Telegram failure notification or any required forward is not
  acknowledged, retain all undeleted matched TV2 Play messages. Never delete
  unrelated messages or all historical messages.
- If URL validation fails, do not send the Telegram success message. Use the
  activation-failure flow above: acknowledge the failure notification, forward
  the exact request message, and only then delete it. Surface or log only
  sanitized failures without secrets, credentials, full URLs, paths, queries,
  response bodies, IDs, or tokens.

#### **1.4.7.3 Netflix**

- Run this flow through `provider_codes.py --provider netflix`.
- Find exactly one hyperlink whose normalized visible text equals the
  configured Netflix `link_text`; never select a nearby or unrelated link.
- Locally unwrap only recognized Microsoft Safe Links or AWS tracking wrappers,
  with a maximum depth of three. Require HTTPS, no URL credentials, only the
  standard HTTPS port, and a final Netflix-owned hostname. Top-level browser
  navigation and every top-level redirect must remain on a Netflix-owned
  hostname. Embedded verification frames may load third-party challenge
  resources, but must never change or relax the top-level hostname check.
- Use the browser adapter to enter the single configured account email and
  require the exact visible heading `Enter your info to sign in`, then press
  the unique exact `Continue` control to submit the email.
- Require the next page to show the exact heading
  `Enter the code we sent to your email`. Establish the fresh-message boundary
  only after the `Continue` action reaches the code-entry page. Do not press
  the code form's `Continue` control before entering the fresh code.
- If headless rendering does not expose the heading text, accept a single
  visible one-time-code input as the code-entry-page signal. Reject missing or
  ambiguous code inputs.
- Poll every 30 seconds for up to 120 seconds for a distinct Netflix code
  message received at or after the boundary. List recent inbox messages rather
  than relying on Graph `$search` indexing, then locally require the configured
  `code_search_string`, a Netflix-owned sender domain, the fresh boundary, and
  a distinct message ID. Extract the code with the configured `code_pattern`;
  reject stale messages, multiple fresh code messages, and any message
  containing multiple distinct codes.
- Match the code email subject exactly as `Netflix: Din loginkode` and extract
  the code only from normalized visible text matching
  `Indtast denne kode for at logge på [code]`.
- Submit the fresh code through the browser adapter. Require both a
  Netflix-owned final URL and an explicit visible success state, with no
  remaining visible error. Navigation by itself is not success.
- If the page instead shows exact visible text
  `Dette link er ikke gyldigt længere`, treat the request as expired. Send
  exactly `NETFLIX link udløbet` through Telegram and require acknowledgement,
  then forward both the request and code emails. Delete only those exact
  messages after Telegram and both forwards succeed. Do not send the code as a
  success notification. If notification or forwarding fails, retain all
  undeleted messages and surface a sanitized error.
- Also treat an old request as expired when submitting the account returns to
  the same `Enter your info to sign in` page with a visible password field
  instead of opening the temporary-code page. In that case, notify Telegram,
  forward, and delete only the request email because no code email is involved.
- After browser success, send the code through the configured Telegram
  destination and require acknowledgement. Then forward both the request and
  code emails to `bsjunk13@hotmail.com`.
- Delete only those exact source message IDs, and only after browser success,
  Telegram acknowledgement, and both forwards succeed. On any failure, retain
  all source messages that have not already been deleted and expose only a
  sanitized error without full URLs, queries, tokens, credentials, or message
  IDs.

## **1.5 Guardrails**

- Do not log secrets, passwords, or full credentials.
- Keep the implementation small, reusable, and testable.
- Prefer shared helpers over duplicated logic.

## **1.6 Supported Providers**

- Netflix
- Viaplay
- tv2play
