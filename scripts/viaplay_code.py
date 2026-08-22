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
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DEFAULT_ACCOUNT = "benny"
DEFAULT_STATUS_DIR = "/Users/bennyskov/Projects/HAP/data"
DEFAULT_STATUS_FILE = "viaplay_code.txt"

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


def get_token(account: str) -> str:
    """Fetch a fresh access token from ortie (auto-refreshes on read)."""
    try:
        out = subprocess.run(
            ["ortie", "token", "show", "-a", account, "--auto-refresh"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        sys.exit("ERROR: 'ortie' not found on PATH (expected in ~/.local/bin).")
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
            "$select": "subject,receivedDateTime,from,bodyPreview",
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


def main() -> int:
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
