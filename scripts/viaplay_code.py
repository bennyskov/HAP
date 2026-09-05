#!/usr/bin/env python3
"""
Read the latest Viaplay one-time-code email in bennyskov@hotmail.com and
save the code to a status file.

Pipeline: ortie (OAuth token broker, macOS Keychain) -> Microsoft Graph API.

The email subject looks like:
    "Viaplay midlertidig engangskode: S9H4"
We search the inbox for that phrase, take the most recent match, extract the
code that follows the colon, and write it to the status file.

Usage:
    ./viaplay_code.py                # account 'benny', default status file
    ./viaplay_code.py -a benny       # explicit account
    ./viaplay_code.py --json         # print result as JSON

Exit codes:
    0  code found and written
    2  no matching email found
    3  matching email found but no code could be parsed
    4  auth / Graph API error
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import smtplib
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

DEFAULT_ACCOUNT = "benny"
DEFAULT_STATUS_DIR = "/Users/bennyskov/Projects/HAP/data"
DEFAULT_STATUS_FILE = "viaplay_code.txt"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
KEYS_FILE = PROJECT_ROOT / "config" / "KEYS.md"
DESTINATIONS_FILE = PROJECT_ROOT / "config" / "code-forward-destinations.csv"
FORWARD_EMAIL = "bsjunk13@hotmail.com"
TELEGRAM_BOT_NAME = "@ViaplayCodeBot"
DEFAULT_ORTIE_BIN = "/Users/bennyskov/.local/bin/ortie"

# The phrase that identifies the OTP email (Danish: "temporary one-time code").
SEARCH_PHRASE = "Viaplay midlertidig engangskode"

# Extract the code that follows the colon in the subject, e.g. "...: S9H4".
# The code is alphanumeric; Viaplay currently uses 4 chars but we allow 4-8
# so a format change doesn't silently break extraction.
CODE_RE = re.compile(
    r"engangskode\s*:?\s*([A-Za-z0-9]{4,8})\b",
    re.IGNORECASE,
)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def load_project_env() -> None:
    if not KEYS_FILE.exists():
        return

    with KEYS_FILE.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip().replace("\r", "")
            if not line.startswith("export ") or "=" not in line:
                continue
            assignment = line[len("export ") :]
            name, value = assignment.split("=", 1)
            name = name.strip()
            value = value.strip().strip('"').strip("'")
            if name and value and not os.environ.get(name):
                os.environ[name] = value

    aliases = {
        "EMAIL_ADDRESS": "BOT_EMAIL_ADDRESS",
        "EMAIL_PASSWORD": "BOT_EMAIL_PASSWORD",
        "EMAIL_SMTP_HOST": "BOT_EMAIL_SMTP_HOST",
        "EMAIL_IMAP_HOST": "BOT_EMAIL_IMAP_HOST",
        "EMAIL_SMTP_USER": "BOT_EMAIL_ADDRESS",
    }
    for target, source in aliases.items():
        if not os.environ.get(target) and os.environ.get(source):
            os.environ[target] = os.environ[source]


def get_token(account: str) -> str:
    """Fetch a fresh access token from ortie (auto-refreshes on read)."""
    ortie_bin = os.environ.get("ORTIE_BIN", DEFAULT_ORTIE_BIN).strip()
    try:
        out = subprocess.run(
            [ortie_bin, "token", "show", "-a", account, "--auto-refresh"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        sys.exit(f"ERROR: 'ortie' not found at {ortie_bin}.")
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr or "")
        raise SystemExit(4) from e
    token = out.stdout.strip().splitlines()[-1].strip() if out.stdout.strip() else ""
    if not token:
        raise SystemExit(4)
    return token


def graph_get(token: str, path: str, params: dict) -> dict:
    url = f"{GRAPH_BASE}{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        sys.stderr.write(f"Graph API error {e.code}: {detail}\n")
        raise SystemExit(4) from e


def find_latest_viaplay_code(token: str) -> tuple[str, dict] | tuple[None, None]:
    """Search the inbox and return (code, message) for the most recent match."""
    # $search matches subject + body + from. We then filter/sort client-side
    # because $search results cannot be combined with $orderby on Graph.
    data = graph_get(
        token,
        "/me/mailFolders/inbox/messages",
        {
            "$search": f'"{SEARCH_PHRASE}"',
            "$select": "id,subject,receivedDateTime,from,bodyPreview",
            "$top": "25",
        },
    )
    candidates = []
    for m in data.get("value", []):
        subject = m.get("subject", "") or ""
        if SEARCH_PHRASE.lower() not in subject.lower():
            continue
        match = CODE_RE.search(subject)
        if not match:
            # Fall back to searching the body preview.
            match = CODE_RE.search(m.get("bodyPreview", "") or "")
        if match:
            candidates.append((m.get("receivedDateTime", ""), match.group(1), m))

    if not candidates:
        return None, None

    # Most recent by receivedDateTime (ISO 8601 sorts lexicographically).
    candidates.sort(key=lambda c: c[0], reverse=True)
    _, code, message = candidates[0]
    return code, message


def delete_message(token: str, message_id: str) -> None:
    if not message_id:
        raise SystemExit("ERROR: cannot delete processed mail without a message id.")

    url = f"{GRAPH_BASE}/me/messages/{urllib.parse.quote(message_id, safe='')}"
    req = urllib.request.Request(
        url,
        method="DELETE",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30):
            return
    except urllib.error.HTTPError as e:
        if e.code == 404:
            sys.stderr.write(f"Graph delete warning 404: message {message_id} was already gone.\n")
            return
        detail = e.read().decode("utf-8", "replace")
        sys.stderr.write(f"Graph delete error {e.code}: {detail}\n")
        raise SystemExit(4) from e


def load_telegram_chat_id(recipient_email: str) -> str:
    """Resolve the Telegram chat id for the configured forwarding address."""
    if not DESTINATIONS_FILE.exists():
        raise SystemExit(f"ERROR: destination file not found: {DESTINATIONS_FILE}")

    with DESTINATIONS_FILE.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if (row.get("forward_to") or "").strip().lower() != recipient_email.lower():
                continue
            chat_id = (row.get("telegram_chat_id") or "").strip()
            if chat_id:
                return chat_id

    fallback = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if fallback:
        return fallback
    raise SystemExit(f"ERROR: no Telegram chat id found for {recipient_email}")


def build_forward_text(code: str, message: dict) -> str:
    subject = message.get("subject", "") or ""
    received = message.get("receivedDateTime", "") or ""
    sender = ((message.get("from") or {}).get("emailAddress") or {}).get("address", "") or ""
    return "\n".join(
        [
            "Viaplay temporary code",
            f"Code: {code}",
            f"Subject: {subject}",
            f"From: {sender}",
            f"Received: {received}",
        ]
    )


def send_email_forward(subject: str, body: str, recipient: str) -> None:
    email_address = os.environ.get("EMAIL_ADDRESS", os.environ.get("BOT_EMAIL_ADDRESS", "")).strip()
    email_password = os.environ.get("EMAIL_PASSWORD", os.environ.get("BOT_EMAIL_PASSWORD", "")).strip()
    smtp_host = os.environ.get("EMAIL_SMTP_HOST", os.environ.get("BOT_EMAIL_SMTP_HOST", "")).strip()
    smtp_port = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
    smtp_user = os.environ.get("EMAIL_SMTP_USER", email_address).strip()

    if not email_address or not email_password or not smtp_host:
        raise SystemExit("ERROR: EMAIL_ADDRESS, EMAIL_PASSWORD, and EMAIL_SMTP_HOST must be set.")

    msg = EmailMessage()
    msg["From"] = email_address
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    try:
        if smtp_port == 465 or os.environ.get("EMAIL_SMTP_SSL", "").strip() == "1":
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=30) as server:
                server.login(smtp_user, email_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.ehlo()
                if os.environ.get("EMAIL_SMTP_STARTTLS", "1").strip() != "0":
                    server.starttls(context=context)
                    server.ehlo()
                server.login(smtp_user, email_password)
                server.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        raise SystemExit(f"ERROR: email forward failed: {exc}") from exc


def send_telegram_forward(chat_id: str, text: str) -> None:
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    if not token:
        raise SystemExit("ERROR: TELEGRAM_TOKEN must be set.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"ERROR: Telegram forward failed {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"ERROR: Telegram forward failed: {exc}") from exc


def forward_result(code: str, message: dict) -> None:
    text = build_forward_text(code, message)
    subject = f"Viaplay code {code}"

    send_email_forward(subject, text, FORWARD_EMAIL)

    chat_id = load_telegram_chat_id(FORWARD_EMAIL)
    telegram_text = f"{TELEGRAM_BOT_NAME}\n{text}"
    send_telegram_forward(chat_id, telegram_text)


def main() -> int:
    load_project_env()
    ap = argparse.ArgumentParser(description="Extract latest Viaplay OTP code from email.")
    ap.add_argument("-a", "--account", default=DEFAULT_ACCOUNT,
                    help=f"ortie/himalaya account (default: {DEFAULT_ACCOUNT})")
    ap.add_argument("-o", "--out", default=os.path.join(DEFAULT_STATUS_DIR, DEFAULT_STATUS_FILE),
                    help="status file path")
    ap.add_argument("--json", action="store_true", help="print result as JSON")
    args = ap.parse_args()

    token = get_token(args.account)
    code, message = find_latest_viaplay_code(token)

    if code is None:
        msg = f"No email matching '{SEARCH_PHRASE}' found in {args.account} inbox."
        print(json.dumps({"found": False, "error": msg}) if args.json else msg,
              file=sys.stderr)
        return 2

    # Write the code to the status file (create parent dir if needed).
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        f.write(code + "\n")

    forward_result(code, message)
    delete_message(token, message.get("id", "") or "")

    received = message.get("receivedDateTime", "")
    result = {
        "found": True,
        "code": code,
        "subject": message.get("subject", ""),
        "received": received,
        "status_file": args.out,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"Code:    {code}")
        print(f"Subject: {result['subject']}")
        print(f"Received:{received}")
        print(f"Saved to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
