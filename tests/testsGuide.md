# **1. Tests Guide**

## **1.1 Provider Code Tests**

`test_provider_codes.py` verifies exact TV2 Play link selection, HTTPS and
TV2-owned-host validation, safe local resolution of the observed nested
Microsoft Safe Links and AWS tracking shape, rejection of wrapper and
destination lookalikes or ambiguous destinations, successful gated processing,
browser-like GET request headers, cookie and validated-redirect handling,
sanitized HTTP/timeout/TLS/DNS/redirect error classification, and polling for a
separate confirmation email after activation. Confirmation tests cover a
delayed later poll without real sleeping, rejection of stale or same-ID
messages, and exact normalized visible text across nested HTML while ignoring
hidden, script, and style content.

The tests also verify the 30-second polling and 120-second timeout defaults,
the exact acknowledged Telegram success message before forwarding both
processed messages and deleting only the matched request and confirmation
messages. The timeout path verifies the exact acknowledged failure
notification, request forwarding, and deletion of only that processed request.
Forwarding failures retain both success-path messages, and cleanup failures are
checked for sanitized reporting. A failed success-message Telegram
acknowledgement also retains both messages without forwarding them.
It also verifies that generic activation failures and trustworthy expired or
already-used classifications—including an exact normalized visible
`Der skete en fejl` HTML heading on HTTP 404 or HTTP 200, but not longer
lookalikes—send only `TV2PLAY bekræftelse fejlede` through Telegram, forward
the matched request, then delete exactly that message after both actions
succeed. A failed Telegram notification acknowledgement is reported separately
and retains the matched message.

## **1.2 Viaplay Code Tests**

`test_viaplay_code.py` verifies that the matched Viaplay email is forwarded,
the Telegram code delivery is acknowledged, and only then the exact original
message is deleted. Email-forward and Telegram failures both retain the source
message.

## **1.3 Netflix Provider Tests**

The Netflix cases in `test_provider_codes.py` verify exact configured
`Hent kode` link-text selection among unrelated Netflix-owned links, bounded
local unwrapping of recognized safe email wrappers, strict
HTTPS Netflix-owned hostname validation, and rejection of URL credentials,
nonstandard ports, and hostname lookalikes. The injectable browser contract is
covered for account-email entry, request-boundary placement, code submission,
redirect rejection, explicit success validation, and error-free completion.

Mailbox tests use injected clocks and sleep functions to cover a delayed fresh
code without real waiting, the 30-second interval and 120-second timeout, and
recent-message listing without Graph `$search` indexing. Local validation
requires the independently configured code text, a Netflix-owned sender,
the fresh timestamp boundary, a distinct message ID, and exactly one
six-digit candidate; tests reject stale, unrelated, sender-mismatched, and
ambiguous mail. The retained request-only inbox shape observed during the
mailbox diagnosis is also covered and must not qualify as a code message.
Browser-flow tests also cover the exact sign-in heading, the single account
`Continue` action, prevention of an empty code-form submission, the code-entry
heading, exact `Netflix: Din loginkode`
subject matching, phrase-bound code extraction, and the explicit
`Dette link er ikke gyldigt længere` expiry outcome. The expiry lifecycle sends
`NETFLIX link udløbet`, forwards both matched emails, and deletes them only
after acknowledgement and both forwards succeed.
Lifecycle tests require browser
completion before acknowledged Telegram delivery, both exact email forwards,
and exact-ID deletion. Browser, timeout, Telegram, forwarding, and cleanup
failure cases verify sanitized failures and retention of every source message
that has not already been deleted.
