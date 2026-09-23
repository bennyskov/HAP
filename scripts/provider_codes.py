#!/usr/bin/env python3
"""Process configured streaming-provider email workflows."""
from __future__ import annotations

import argparse
import csv
import http.cookiejar
import json
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Protocol

from viaplay_code import (
    FORWARD_EMAIL,
    GRAPH_BASE,
    delete_message,
    find_latest_viaplay_code,
    get_token,
    load_project_env,
    load_telegram_chat_id,
    process_viaplay_message,
    send_telegram_forward,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROVIDERS_FILE = PROJECT_ROOT / "config" / "code-forward-providers.csv"
TV2_LINK_TEXT = "Bekræft midlertidig adgang"
TV2_CONFIRMATION_TEXT = "Midlertidig adgang er bekræftet."
TV2_OLD_LINK_TEXT = "Der skete en fejl"
TV2_TELEGRAM_TEXT = "TV2PLAY bekræftet"
TV2_FAILURE_TELEGRAM_TEXT = "TV2PLAY bekræftelse fejlede"
TV2_HOSTS = ("tv2.dk", "tv2api.dk", "tv2play.dk")
MICROSOFT_SAFE_LINKS_SUFFIX = "safelinks.protection.outlook.com"
AWS_TRACK_HOST_PATTERN = re.compile(
    r"^[a-z0-9]+\.r\.[a-z0-9-]+\.awstrack\.me$",
    flags=re.IGNORECASE,
)
TV2_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)
TV2_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,*/*;q=0.8"
)
MAX_ACTIVATION_BODY_BYTES = 1_000_000
TV2_CONFIRMATION_POLL_INTERVAL_SECONDS = 30
TV2_CONFIRMATION_TIMEOUT_SECONDS = 120
NETFLIX_ACCOUNT_EMAIL = "bennyskov@hotmail.com"
NETFLIX_HOSTS = ("netflix.com", "netflix.net")
NETFLIX_SENDER_HOSTS = ("netflix.com",)
NETFLIX_CODE_POLL_INTERVAL_SECONDS = 30
NETFLIX_CODE_TIMEOUT_SECONDS = 120
NETFLIX_SIGN_IN_HEADING = "Enter your info to sign in"
NETFLIX_CONTINUE_TEXT = "Continue"
NETFLIX_CODE_HEADING = "Enter the code we sent to your email"
NETFLIX_EXPIRED_TEXT = "Dette link er ikke gyldigt længere"
NETFLIX_EXPIRED_TELEGRAM_TEXT = "NETFLIX link udløbet"
MAX_WRAPPER_DEPTH = 3


class _NetflixExpiredLinkError(RuntimeError):
    """Indicate that Netflix explicitly rejected an expired access request."""


class _NetflixBrowserStageError(RuntimeError):
    """Report a sanitized Netflix browser stage failure."""


class NetflixBrowserAdapter(Protocol):
    """Browser boundary used by the Netflix workflow and unit tests."""

    def open_request(self, url: str) -> None:
        """Open a validated Netflix request URL."""

    def submit_account_email(self, account_email: str) -> None:
        """Enter and submit the Netflix account email."""

    def submit_code(self, code: str) -> None:
        """Enter and submit the fresh Netflix verification code."""

    def require_explicit_success(self) -> None:
        """Raise unless Netflix displays an explicit, error-free success state."""


class PlaywrightNetflixBrowser:
    """Small Playwright adapter that blocks non-Netflix document navigation."""

    _EMAIL_SELECTORS = (
        "input[type='email']",
        "input[name='email']",
        "input[name='userLoginId']",
    )
    _CODE_SELECTORS = (
        "input[autocomplete='one-time-code']",
        "input[name='code']",
        "input[inputmode='numeric']",
    )
    _SUBMIT_SELECTORS = (
        "button[type='submit']",
        "input[type='submit']",
    )
    _SUCCESS_SELECTORS = (
        "[data-uia='travel-verification-success']",
        "[data-uia='temporary-access-success']",
        "[data-uia='login-success']",
    )
    _ERROR_SELECTOR = "[role='alert'], [data-uia*='error']"

    def __init__(self, *, headless: bool = True) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Netflix browser support requires the configured Playwright dependency."
            ) from exc

        playwright = None
        browser = None
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=headless)
            page = browser.new_page()
            self._navigation_rejection: str | None = None
            page.route("**/*", self._validate_route)
        except Exception as exc:
            if browser is not None:
                browser.close()
            if playwright is not None:
                playwright.stop()
            raise RuntimeError("Netflix browser could not be started.") from exc
        self._playwright = playwright
        self._browser = browser
        self._page = page

    def _validate_route(self, route) -> None:
        request = route.request
        is_top_level_navigation = (
            request.is_navigation_request()
            and request.frame == self._page.main_frame
        )
        if is_top_level_navigation:
            try:
                _validate_netflix_url(request.url)
            except ValueError:
                self._navigation_rejection = "non-Netflix navigation"
                route.abort()
                return
        route.continue_()

    @staticmethod
    def _first_visible(page, selectors: tuple[str, ...]):
        for selector in selectors:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible():
                return locator
        raise RuntimeError("Netflix browser did not expose the expected form control.")

    def _exact_visible_role(self, role: str, name: str):
        locator = self._page.get_by_role(role, name=name, exact=True)
        locator.first.wait_for(state="visible", timeout=10_000)
        visible = [
            locator.nth(index)
            for index in range(locator.count())
            if locator.nth(index).is_visible()
        ]
        if len(visible) != 1:
            raise RuntimeError("Netflix browser exposed an ambiguous page control.")
        return visible[0]

    def _has_exact_visible_text(self, text: str) -> bool:
        locator = self._page.get_by_text(text, exact=True)
        return any(
            locator.nth(index).is_visible()
            for index in range(locator.count())
        )

    def _require_exact_visible_text(self, text: str) -> None:
        locator = self._page.get_by_text(text, exact=True)
        locator.first.wait_for(state="visible", timeout=10_000)
        has_visible_match = any(
            locator.nth(index).is_visible()
            for index in range(locator.count())
        )
        if not has_visible_match:
            raise RuntimeError("Netflix browser did not expose the expected page text.")

    def _require_code_entry_page(self) -> None:
        body = self._page.locator("body")
        body.wait_for(state="visible", timeout=10_000)
        normalized_text = " ".join(body.inner_text().split())
        if NETFLIX_CODE_HEADING in normalized_text:
            return

        selector = ", ".join(self._CODE_SELECTORS)
        code_inputs = self._page.locator(selector)
        code_inputs.first.wait_for(state="visible", timeout=10_000)
        visible_count = sum(
            code_inputs.nth(index).is_visible()
            for index in range(code_inputs.count())
        )
        if visible_count != 1:
            raise RuntimeError("Netflix browser did not expose a unique code input.")

    def _is_password_sign_in_page(self) -> bool:
        if not self._has_exact_visible_text(NETFLIX_SIGN_IN_HEADING):
            return False
        passwords = self._page.locator("input[type='password']")
        return any(
            passwords.nth(index).is_visible()
            for index in range(passwords.count())
        )

    def _raise_navigation_rejection(self) -> None:
        if self._navigation_rejection:
            raise RuntimeError("Netflix browser rejected an unsafe navigation.")
        _validate_netflix_url(self._page.url)

    def open_request(self, url: str) -> None:
        try:
            self._page.goto(
                _validate_netflix_url(url),
                wait_until="domcontentloaded",
            )
            self._raise_navigation_rejection()
        except Exception as exc:
            raise RuntimeError("Netflix request navigation failed.") from exc

    def submit_account_email(self, account_email: str) -> None:
        try:
            self._require_exact_visible_text(NETFLIX_SIGN_IN_HEADING)
        except Exception as exc:
            raise _NetflixBrowserStageError(
                "Netflix sign-in prompt was not found."
            ) from exc
        try:
            self._first_visible(self._page, self._EMAIL_SELECTORS).fill(account_email)
            self._exact_visible_role("button", NETFLIX_CONTINUE_TEXT).click()
            self._page.wait_for_load_state("domcontentloaded")
            self._raise_navigation_rejection()
        except Exception as exc:
            raise _NetflixBrowserStageError(
                "Netflix Continue action failed."
            ) from exc
        try:
            self._require_code_entry_page()
        except Exception as exc:
            if self._is_password_sign_in_page():
                raise _NetflixExpiredLinkError(
                    "Netflix access request was expired."
                ) from exc
            raise _NetflixBrowserStageError(
                "Netflix code-entry prompt was not found."
            ) from exc

    def submit_code(self, code: str) -> None:
        try:
            self._first_visible(self._page, self._CODE_SELECTORS).fill(code)
            self._first_visible(self._page, self._SUBMIT_SELECTORS).click()
            self._page.wait_for_load_state("domcontentloaded")
            self._raise_navigation_rejection()
        except Exception as exc:
            raise RuntimeError("Netflix code form submission failed.") from exc

    def require_explicit_success(self) -> None:
        self._raise_navigation_rejection()
        if self._has_exact_visible_text(NETFLIX_EXPIRED_TEXT):
            raise _NetflixExpiredLinkError(
                "Netflix access request was expired."
            )
        error = self._page.locator(self._ERROR_SELECTOR).first
        if error.count() and error.is_visible():
            raise RuntimeError("Netflix displayed an error after code submission.")
        success_visible = False
        for selector in self._SUCCESS_SELECTORS:
            success = self._page.locator(selector).first
            if success.count() and success.is_visible():
                success_visible = True
                break
        if not success_visible:
            raise RuntimeError("Netflix did not display an explicit success state.")

    def close(self) -> None:
        try:
            self._browser.close()
            self._playwright.stop()
        except Exception as exc:
            raise RuntimeError("Netflix browser cleanup failed.") from exc

    def __enter__(self) -> PlaywrightNetflixBrowser:
        return self

    def __exit__(self, *_args: object) -> None:
        del _args
        self.close()


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._href: str | None = None
        self._text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a" and self._href is None:
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = " ".join("".join(self._text).split())
            self.links.append((text, self._href))
            self._href = None
            self._text = []


class _VisibleTextParser(HTMLParser):
    """Collect normalized text from visible HTML elements."""

    _NON_VISIBLE_TAGS = frozenset({"head", "noscript", "script", "style", "template"})
    _TEXT_CONTAINER_TAGS = frozenset(
        {
            "article",
            "aside",
            "body",
            "dd",
            "div",
            "dt",
            "figcaption",
            "footer",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "header",
            "li",
            "main",
            "nav",
            "p",
            "pre",
            "section",
            "td",
            "th",
        }
    )
    _VOID_TAGS = frozenset(
        {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[dict[str, object]] = []
        self._document_text: list[str] = []
        self.texts: set[str] = set()

    @staticmethod
    def _element_is_hidden(tag: str, attrs: list[tuple[str, str | None]]) -> bool:
        attributes = {name.casefold(): value or "" for name, value in attrs}
        style = attributes.get("style", "")
        return (
            tag in _VisibleTextParser._NON_VISIBLE_TAGS
            or "hidden" in attributes
            or attributes.get("aria-hidden", "").strip().casefold() == "true"
            or bool(
                re.search(
                    r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)"
                    r"\s*(?:;|$)",
                    style,
                    flags=re.IGNORECASE,
                )
            )
        )

    @staticmethod
    def _normalize(parts: list[str]) -> str:
        return " ".join("".join(parts).split())

    def _record(self, frame: dict[str, object]) -> None:
        if frame["hidden"] or frame["tag"] not in self._TEXT_CONTAINER_TAGS:
            return
        text = self._normalize(frame["parts"])
        if text:
            self.texts.add(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        parent_hidden = bool(self._stack and self._stack[-1]["hidden"])
        hidden = parent_hidden or self._element_is_hidden(tag, attrs)
        if tag in self._VOID_TAGS:
            if tag in {"br", "hr"} and not hidden:
                self.handle_data(" ")
            return
        self._stack.append({"tag": tag, "hidden": hidden, "parts": []})

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.casefold() not in self._VOID_TAGS:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._stack and self._stack[-1]["hidden"]:
            return
        self._document_text.append(data)
        for frame in self._stack:
            if not frame["hidden"]:
                frame["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        matching_index = next(
            (
                index
                for index in range(len(self._stack) - 1, -1, -1)
                if self._stack[index]["tag"] == tag
            ),
            None,
        )
        if matching_index is None:
            return
        for frame in reversed(self._stack[matching_index:]):
            self._record(frame)
        del self._stack[matching_index:]

    def contains_exact_text(self, expected: str) -> bool:
        for frame in self._stack:
            self._record(frame)
        document_text = self._normalize(self._document_text)
        return expected == document_text or expected in self.texts

    def normalized_document_text(self) -> str:
        """Return only normalized text collected from visible HTML nodes."""
        return self._normalize(self._document_text)


def _load_providers(path: Path = PROVIDERS_FILE) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        providers = {
            (row.get("provider") or "").strip().lower(): (row.get("search_string") or "").strip()
            for row in csv.DictReader(handle)
        }
    return {name: search for name, search in providers.items() if name and search}


def _load_netflix_config(path: Path = PROVIDERS_FILE) -> tuple[str, str, str, str]:
    """Return Netflix request matching, link text, code matching, and pattern."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if (row.get("provider") or "").strip().casefold() == "netflix"
        ]
    if len(rows) != 1:
        raise ValueError("Expected exactly one Netflix provider configuration.")
    row = rows[0]
    search_string = (row.get("search_string") or "").strip()
    link_text = (row.get("link_text") or search_string).strip()
    code_search_string = (row.get("code_search_string") or search_string).strip()
    code_pattern = (row.get("code_pattern") or "").strip()
    if not search_string or not link_text or not code_search_string or not code_pattern:
        raise ValueError("Netflix provider configuration was incomplete.")
    try:
        re.compile(code_pattern)
    except re.error as exc:
        raise ValueError("Netflix code extraction pattern was invalid.") from exc
    return search_string, link_text, code_search_string, code_pattern


def _graph_json(token: str, path: str, params: dict[str, str] | None = None) -> dict:
    url = f"{GRAPH_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError("Microsoft Graph request failed.") from exc


def _graph_post(token: str, path: str, payload: dict) -> int:
    request = urllib.request.Request(
        f"{GRAPH_BASE}{path}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return int(response.status)
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise RuntimeError("Microsoft Graph action failed.") from exc


def _find_latest_message(token: str, search_string: str) -> dict | None:
    result = _graph_json(
        token,
        "/me/mailFolders/inbox/messages",
        {
            "$search": f'"{search_string}"',
            "$select": "id,subject,receivedDateTime,body,bodyPreview",
            "$top": "25",
        },
    )
    needle = search_string.casefold()
    matches = []
    for message in result.get("value", []):
        searchable = " ".join(
            [
                message.get("subject", "") or "",
                message.get("bodyPreview", "") or "",
                (message.get("body") or {}).get("content", "") or "",
            ]
        )
        if needle in searchable.casefold() and message.get("id"):
            matches.append(message)
    return max(matches, key=lambda item: item.get("receivedDateTime", ""), default=None)


def _extract_exact_link(html: str, visible_text: str = TV2_LINK_TEXT) -> str:
    parser = _LinkParser()
    parser.feed(html)
    matches = [href for text, href in parser.links if text == visible_text]
    if len(matches) != 1:
        raise ValueError("Expected exactly one link with the configured visible text.")
    return matches[0]


def _validate_tv2_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").rstrip(".").lower()
    owned_host = any(host == suffix or host.endswith(f".{suffix}") for suffix in TV2_HOSTS)
    if (
        parsed.scheme.lower() != "https"
        or not owned_host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise ValueError("TV2 Play activation URL failed validation.")
    return url


def _validate_https_url(url: str) -> urllib.parse.SplitResult:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise ValueError("Activation wrapper URL failed validation.")
    return parsed


def _unwrap_microsoft_safe_link(parsed: urllib.parse.SplitResult) -> str:
    values = urllib.parse.parse_qs(
        parsed.query,
        keep_blank_values=True,
        strict_parsing=True,
    ).get("url", [])
    if len(values) != 1 or not values[0]:
        raise ValueError("Microsoft Safe Links destination was invalid.")
    return values[0]


def _unwrap_aws_track_link(parsed: urllib.parse.SplitResult) -> str:
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 2 or segments[0] not in {"L0", "L1"}:
        raise ValueError("AWS tracking destination was invalid.")
    destination = urllib.parse.unquote(segments[1])
    if not destination.lower().startswith("https://"):
        raise ValueError("AWS tracking destination was invalid.")
    return destination


def _resolve_tv2_url(url: str) -> str:
    current = url
    for _ in range(3):
        parsed = _validate_https_url(current)
        host = (parsed.hostname or "").rstrip(".").lower()
        if any(host == suffix or host.endswith(f".{suffix}") for suffix in TV2_HOSTS):
            return _validate_tv2_url(current)
        if host == MICROSOFT_SAFE_LINKS_SUFFIX or host.endswith(
            f".{MICROSOFT_SAFE_LINKS_SUFFIX}"
        ):
            current = _unwrap_microsoft_safe_link(parsed)
            continue
        if AWS_TRACK_HOST_PATTERN.fullmatch(host):
            current = _unwrap_aws_track_link(parsed)
            continue
        raise ValueError("Activation URL host was not recognized.")
    raise ValueError("Activation URL exceeded the supported wrapper depth.")


def _validate_netflix_url(url: str) -> str:
    parsed = _validate_https_url(url)
    host = (parsed.hostname or "").rstrip(".").casefold()
    if not any(
        host == suffix or host.endswith(f".{suffix}") for suffix in NETFLIX_HOSTS
    ):
        raise ValueError("Netflix URL host failed validation.")
    return url


def _resolve_netflix_url(url: str) -> str:
    """Locally unwrap only recognized mail wrappers, with a fixed depth bound."""
    current = url
    for _ in range(MAX_WRAPPER_DEPTH):
        parsed = _validate_https_url(current)
        host = (parsed.hostname or "").rstrip(".").casefold()
        if any(
            host == suffix or host.endswith(f".{suffix}") for suffix in NETFLIX_HOSTS
        ):
            return _validate_netflix_url(current)
        if host == MICROSOFT_SAFE_LINKS_SUFFIX or host.endswith(
            f".{MICROSOFT_SAFE_LINKS_SUFFIX}"
        ):
            current = _unwrap_microsoft_safe_link(parsed)
            continue
        if AWS_TRACK_HOST_PATTERN.fullmatch(host):
            current = _unwrap_aws_track_link(parsed)
            continue
        raise ValueError("Netflix link wrapper host was not recognized.")
    raise ValueError("Netflix link exceeded the supported wrapper depth.")


class _TV2ActivationError(RuntimeError):
    """Carry only sanitized activation failure facts."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.reason = reason


class _RedirectHostRejected(_TV2ActivationError):
    """Indicate that an activation redirect did not remain on a TV2 host."""


class _TV2FailureNotificationError(RuntimeError):
    """Indicate that the required activation-failure notification failed."""


class _ValidatedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            safe_url = _validate_tv2_url(urllib.parse.urljoin(req.full_url, newurl))
        except ValueError as exc:
            raise _RedirectHostRejected(
                "TV2 Play activation failed: redirect host rejection.",
                reason="redirect host rejection",
            ) from exc
        return super().redirect_request(req, fp, code, msg, headers, safe_url)


def _is_explicit_ok(body: str) -> bool:
    return body.strip().casefold() == "ok" or bool(
        re.search(r'"ok"\s*:\s*true', body, flags=re.IGNORECASE)
    )


def _benign_http_reason(body: str) -> str | None:
    parser = _VisibleTextParser()
    parser.feed(body)
    parser.close()
    if parser.contains_exact_text(TV2_OLD_LINK_TEXT):
        return "expired"

    normalized = " ".join(body.casefold().split())
    if any(term in normalized for term in ("already used", "already-used", "allerede brugt")):
        return "already-used"
    if any(term in normalized for term in ("expired", "udløbet", "udloebet")):
        return "expired"
    return None


def _http_status_category(code: int) -> str:
    if 400 <= code <= 499:
        return "client error"
    if 500 <= code <= 599:
        return "server error"
    if 300 <= code <= 399:
        return "redirect response"
    return "unexpected response"


def _read_activation_body(response) -> str:
    return response.read(MAX_ACTIVATION_BODY_BYTES).decode("utf-8", "replace")


def _activate_tv2(url: str) -> tuple[int, bool]:
    opener = urllib.request.build_opener(
        _ValidatedRedirectHandler(),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )
    request = urllib.request.Request(
        _validate_tv2_url(url),
        method="GET",
        headers={
            "Accept": TV2_ACCEPT,
            "User-Agent": TV2_BROWSER_USER_AGENT,
        },
    )
    try:
        with opener.open(request, timeout=30) as response:
            try:
                _validate_tv2_url(response.geturl())
            except ValueError as exc:
                raise _RedirectHostRejected(
                    "TV2 Play activation failed: redirect host rejection.",
                    reason="redirect host rejection",
                ) from exc
            status = int(response.status)
            body = _read_activation_body(response)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        try:
            body = _read_activation_body(exc)
        finally:
            exc.close()
        reason = _benign_http_reason(body)
        if reason:
            detail = (
                f"HTTP {status} ({_http_status_category(status)}); reason: {reason}"
            )
            raise _TV2ActivationError(
                f"TV2 Play activation failed: {detail}.",
                http_status=status,
                reason=reason,
            ) from exc
        explicit_ok = _is_explicit_ok(body)
        if explicit_ok:
            return status, True
        detail = f"HTTP {status} ({_http_status_category(status)})"
        raise _TV2ActivationError(
            f"TV2 Play activation failed: {detail}.",
            http_status=status,
        ) from exc
    except _RedirectHostRejected:
        raise
    except (socket.timeout, TimeoutError) as exc:
        raise _TV2ActivationError(
            "TV2 Play activation failed: timeout.",
            reason="timeout",
        ) from exc
    except ssl.SSLError as exc:
        raise _TV2ActivationError(
            "TV2 Play activation failed: TLS error.",
            reason="TLS error",
        ) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (socket.timeout, TimeoutError)):
            classification = "timeout"
        elif isinstance(exc.reason, ssl.SSLError):
            classification = "TLS error"
        elif isinstance(exc.reason, socket.gaierror):
            classification = "DNS error"
        else:
            classification = "network error"
        raise _TV2ActivationError(
            f"TV2 Play activation failed: {classification}.",
            reason=classification,
        ) from exc
    except OSError as exc:
        raise _TV2ActivationError(
            "TV2 Play activation failed: network error.",
            reason="network error",
        ) from exc
    except ValueError as exc:
        raise _TV2ActivationError(
            "TV2 Play activation failed: invalid response.",
            reason="invalid response",
        ) from exc

    explicit_ok = _is_explicit_ok(body)
    reason = _benign_http_reason(body)
    if reason:
        raise _TV2ActivationError(
            "TV2 Play activation failed: "
            f"HTTP {status} ({_http_status_category(status)}); reason: {reason}.",
            http_status=status,
            reason=reason,
        )
    if status != 200 and not explicit_ok:
        raise _TV2ActivationError(
            "TV2 Play activation failed: "
            f"HTTP {status} ({_http_status_category(status)}).",
            http_status=status,
            reason=_http_status_category(status),
        )
    return status, explicit_ok


def _has_confirmation(message: dict) -> bool:
    parser = _VisibleTextParser()
    parser.feed((message.get("body") or {}).get("content", "") or "")
    parser.close()
    return parser.contains_exact_text(TV2_CONFIRMATION_TEXT)


def _parse_graph_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _find_tv2_confirmation(
    token: str,
    *,
    not_before: datetime,
    excluded_message_ids: set[str],
) -> dict | None:
    result = _graph_json(
        token,
        "/me/mailFolders/inbox/messages",
        {
            "$search": f'"{TV2_CONFIRMATION_TEXT}"',
            "$select": "id,receivedDateTime,body",
            "$top": "25",
        },
    )
    matches: list[tuple[datetime, dict]] = []
    for message in result.get("value", []):
        message_id = message.get("id")
        received_at = _parse_graph_datetime(message.get("receivedDateTime"))
        if (
            not message_id
            or message_id in excluded_message_ids
            or received_at is None
            or received_at < not_before
            or not _has_confirmation(message)
        ):
            continue
        matches.append((received_at, message))
    if not matches:
        return None
    return max(matches, key=lambda match: match[0])[1]


def _poll_for_tv2_confirmation(
    token: str,
    *,
    not_before: datetime,
    excluded_message_ids: set[str],
    poll_interval_seconds: float = TV2_CONFIRMATION_POLL_INTERVAL_SECONDS,
    timeout_seconds: float = TV2_CONFIRMATION_TIMEOUT_SECONDS,
    sleep_fn: Callable[[float], None] | None = None,
    monotonic_fn: Callable[[], float] | None = None,
) -> dict | None:
    if poll_interval_seconds <= 0 or timeout_seconds < 0:
        raise ValueError("TV2 Play confirmation polling settings were invalid.")
    sleeper = sleep_fn or time.sleep
    monotonic = monotonic_fn or time.monotonic
    deadline = monotonic() + timeout_seconds

    while True:
        confirmation = _find_tv2_confirmation(
            token,
            not_before=not_before,
            excluded_message_ids=excluded_message_ids,
        )
        if confirmation is not None:
            return confirmation
        remaining = deadline - monotonic()
        if remaining <= 0:
            return None
        sleeper(min(poll_interval_seconds, remaining))


def _forward_message(token: str, message_id: str) -> None:
    path = f"/me/messages/{urllib.parse.quote(message_id, safe='')}/forward"
    status = _graph_post(
        token,
        path,
        {
            "comment": "",
            "toRecipients": [{"emailAddress": {"address": FORWARD_EMAIL}}],
        },
    )
    if status not in (200, 202):
        raise RuntimeError("Email forward was not acknowledged.")


def _notify_tv2_activation_failure() -> None:
    try:
        chat_id = load_telegram_chat_id(FORWARD_EMAIL)
        send_telegram_forward(chat_id, TV2_FAILURE_TELEGRAM_TEXT)
    except (RuntimeError, ValueError, SystemExit) as exc:
        raise _TV2FailureNotificationError(
            "TV2 Play activation failed; Telegram failure notification "
            "was not acknowledged."
        ) from exc


def _forward_tv2_messages(token: str, message_ids: list[str]) -> None:
    try:
        for message_id in message_ids:
            _forward_message(token, message_id)
    except (RuntimeError, ValueError, SystemExit) as exc:
        raise RuntimeError("TV2 Play email forwarding failed.") from exc


def _delete_tv2_messages(token: str, message_ids: list[str]) -> None:
    try:
        for message_id in message_ids:
            delete_message(token, message_id)
    except (RuntimeError, ValueError, SystemExit) as exc:
        raise RuntimeError("TV2 Play email cleanup failed.") from exc


def _complete_tv2_failure(
    token: str,
    message_ids: list[str],
    status: dict[str, object],
) -> dict[str, object]:
    _notify_tv2_activation_failure()
    status["failure_telegram_acknowledged"] = True
    status["telegram_delivered"] = True
    _forward_tv2_messages(token, message_ids)
    status["email_forwarded"] = True
    status["confirmation_email_forwarded"] = len(message_ids) > 1
    _delete_tv2_messages(token, message_ids)
    status["original_deleted"] = True
    status["confirmation_deleted"] = len(message_ids) > 1
    return status


def _process_tv2play(
    token: str,
    search_string: str,
    *,
    sleep_fn: Callable[[float], None] | None = None,
    monotonic_fn: Callable[[], float] | None = None,
    now_fn: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    status: dict[str, object] = {
        "provider": "tv2play",
        "link_validated": False,
        "http_outcome": None,
        "activation_failed": False,
        "activation_failure_category": None,
        "link_expired": False,
        "confirmation_text": False,
        "email_forwarded": False,
        "confirmation_email_forwarded": False,
        "telegram_delivered": False,
        "failure_telegram_acknowledged": False,
        "original_deleted": False,
        "confirmation_deleted": False,
    }
    message = _find_latest_message(token, search_string)
    if message is None:
        raise RuntimeError("No matching TV2 Play email was found.")
    message_id = message["id"]

    activation_started_at = (now_fn or (lambda: datetime.now(timezone.utc)))()
    if activation_started_at.tzinfo is None:
        raise ValueError("TV2 Play activation start time was invalid.")
    activation_started_at = activation_started_at.astimezone(timezone.utc)
    try:
        html = (message.get("body") or {}).get("content", "") or ""
        link = _extract_exact_link(html)
        activation_url = _resolve_tv2_url(link)
        status["link_validated"] = True
        http_status, explicit_ok = _activate_tv2(activation_url)
    except (RuntimeError, ValueError) as exc:
        status["activation_failed"] = True
        if isinstance(exc, _TV2ActivationError):
            if exc.http_status is not None:
                status["http_outcome"] = f"HTTP {exc.http_status}"
                category = exc.reason or _http_status_category(exc.http_status)
            else:
                category = exc.reason or "request failure"
        else:
            category = "request failure"
        status["activation_failure_category"] = category
        status["link_expired"] = category in {"expired", "already-used"}
        return _complete_tv2_failure(token, [message_id], status)

    status["http_outcome"] = "HTTP 200" if http_status == 200 else "explicit OK"
    if http_status != 200 and not explicit_ok:
        raise RuntimeError("TV2 Play activation was not acknowledged.")

    request_received_at = _parse_graph_datetime(message.get("receivedDateTime"))
    confirmation = _poll_for_tv2_confirmation(
        token,
        not_before=request_received_at or activation_started_at,
        excluded_message_ids={message_id},
        sleep_fn=sleep_fn,
        monotonic_fn=monotonic_fn,
    )
    if confirmation is None:
        status["activation_failed"] = True
        status["activation_failure_category"] = "confirmation timeout"
        return _complete_tv2_failure(token, [message_id], status)

    confirmation_id = confirmation["id"]
    status["confirmation_text"] = True

    try:
        chat_id = load_telegram_chat_id(FORWARD_EMAIL)
        send_telegram_forward(chat_id, TV2_TELEGRAM_TEXT)
    except (RuntimeError, ValueError, SystemExit) as exc:
        raise RuntimeError(
            "TV2 Play success notification was not acknowledged."
        ) from exc
    status["telegram_delivered"] = True

    message_ids = [message_id, confirmation_id]
    _forward_tv2_messages(token, message_ids)
    status["email_forwarded"] = True
    status["confirmation_email_forwarded"] = True
    _delete_tv2_messages(token, message_ids)
    status["original_deleted"] = True
    status["confirmation_deleted"] = True
    return status


def _message_visible_text(message: dict) -> str:
    parser = _VisibleTextParser()
    parser.feed((message.get("body") or {}).get("content", "") or "")
    parser.close()
    return " ".join(
        part
        for part in (
            message.get("subject", "") or "",
            message.get("bodyPreview", "") or "",
            parser.normalized_document_text(),
        )
        if part
    )


def _is_netflix_sender(message: dict) -> bool:
    address = (
        ((message.get("from") or {}).get("emailAddress") or {}).get("address") or ""
    )
    if "@" not in address:
        return False
    host = address.rsplit("@", 1)[1].rstrip(".").casefold()
    return any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in NETFLIX_SENDER_HOSTS
    )


def _find_netflix_code(
    token: str,
    *,
    code_search_string: str,
    code_pattern: str,
    not_before: datetime,
    excluded_message_ids: set[str],
) -> tuple[str, dict] | None:
    result = _graph_json(
        token,
        "/me/mailFolders/inbox/messages",
        {
            "$select": "id,subject,receivedDateTime,from,body,bodyPreview",
            "$orderby": "receivedDateTime desc",
            "$top": "25",
        },
    )
    pattern = re.compile(code_pattern)
    text_needle = code_search_string.casefold()
    matches: list[tuple[datetime, str, dict]] = []
    for message in result.get("value", []):
        message_id = message.get("id")
        received_at = _parse_graph_datetime(message.get("receivedDateTime"))
        if (
            not message_id
            or message_id in excluded_message_ids
            or received_at is None
            or received_at < not_before
            or not _is_netflix_sender(message)
        ):
            continue
        visible_text = _message_visible_text(message)
        subject = " ".join((message.get("subject") or "").split())
        if subject.casefold() != text_needle:
            continue
        found = {
            match.group(1) if match.lastindex else match.group(0)
            for match in pattern.finditer(visible_text)
        }
        if len(found) > 1:
            raise RuntimeError("Netflix code email contained multiple distinct codes.")
        if found:
            matches.append((received_at, found.pop(), message))

    distinct_codes = {match[1] for match in matches}
    if len(matches) > 1 or len(distinct_codes) > 1:
        raise RuntimeError("Multiple fresh Netflix code emails were found.")
    if not matches:
        return None
    _, code, message = matches[0]
    return code, message


def _poll_for_netflix_code(
    token: str,
    *,
    code_search_string: str,
    code_pattern: str,
    not_before: datetime,
    excluded_message_ids: set[str],
    poll_interval_seconds: float = NETFLIX_CODE_POLL_INTERVAL_SECONDS,
    timeout_seconds: float = NETFLIX_CODE_TIMEOUT_SECONDS,
    sleep_fn: Callable[[float], None] | None = None,
    monotonic_fn: Callable[[], float] | None = None,
) -> tuple[str, dict] | None:
    if poll_interval_seconds <= 0 or timeout_seconds < 0:
        raise ValueError("Netflix code polling settings were invalid.")
    sleeper = sleep_fn or time.sleep
    monotonic = monotonic_fn or time.monotonic
    deadline = monotonic() + timeout_seconds

    while True:
        match = _find_netflix_code(
            token,
            code_search_string=code_search_string,
            code_pattern=code_pattern,
            not_before=not_before,
            excluded_message_ids=excluded_message_ids,
        )
        if match is not None:
            return match
        remaining = deadline - monotonic()
        if remaining <= 0:
            return None
        sleeper(min(poll_interval_seconds, remaining))


def _complete_netflix_expiry(
    token: str,
    message_ids: list[str],
) -> dict[str, object]:
    try:
        chat_id = load_telegram_chat_id(FORWARD_EMAIL)
        send_telegram_forward(chat_id, NETFLIX_EXPIRED_TELEGRAM_TEXT)
    except (RuntimeError, ValueError, SystemExit) as exc:
        raise RuntimeError(
            "Netflix expiry notification was not acknowledged."
        ) from exc
    try:
        for message_id in message_ids:
            _forward_message(token, message_id)
    except (RuntimeError, ValueError, SystemExit) as exc:
        raise RuntimeError("Netflix expired-email forwarding failed.") from exc
    try:
        for message_id in message_ids:
            delete_message(token, message_id)
    except (RuntimeError, ValueError, SystemExit) as exc:
        raise RuntimeError("Netflix expired-email cleanup failed.") from exc
    return {
        "provider": "netflix",
        "browser_completed": False,
        "activation_failed": True,
        "link_expired": True,
        "telegram_delivered": True,
        "emails_forwarded": True,
        "messages_deleted": True,
    }


def _process_netflix(
    token: str,
    request_search_string: str,
    link_text: str,
    code_search_string: str,
    code_pattern: str,
    browser: NetflixBrowserAdapter,
    *,
    sleep_fn: Callable[[float], None] | None = None,
    monotonic_fn: Callable[[], float] | None = None,
    now_fn: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    request_message = _find_latest_message(token, request_search_string)
    if request_message is None:
        raise RuntimeError("No matching Netflix request email was found.")
    request_id = request_message["id"]

    html = (request_message.get("body") or {}).get("content", "") or ""
    try:
        request_url = _resolve_netflix_url(_extract_exact_link(html, link_text))
        browser.open_request(request_url)
    except (RuntimeError, ValueError) as exc:
        raise RuntimeError("Netflix request navigation failed.") from exc
    try:
        browser.submit_account_email(NETFLIX_ACCOUNT_EMAIL)
    except _NetflixExpiredLinkError:
        return _complete_netflix_expiry(token, [request_id])
    except _NetflixBrowserStageError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise RuntimeError("Netflix account interaction failed.") from exc

    boundary = (now_fn or (lambda: datetime.now(timezone.utc)))()
    if boundary.tzinfo is None:
        raise ValueError("Netflix request boundary was invalid.")
    boundary = boundary.astimezone(timezone.utc)
    try:
        code_match = _poll_for_netflix_code(
            token,
            code_search_string=code_search_string,
            code_pattern=code_pattern,
            not_before=boundary,
            excluded_message_ids={request_id},
            sleep_fn=sleep_fn,
            monotonic_fn=monotonic_fn,
        )
    except (RuntimeError, ValueError) as exc:
        raise RuntimeError("Netflix code lookup failed.") from exc
    if code_match is None:
        raise RuntimeError("Netflix code email did not arrive before timeout.")
    code, code_message = code_match
    code_id = code_message["id"]

    try:
        browser.submit_code(code)
        browser.require_explicit_success()
    except _NetflixExpiredLinkError:
        return _complete_netflix_expiry(token, [request_id, code_id])
    except (RuntimeError, ValueError) as exc:
        raise RuntimeError("Netflix code submission was not successful.") from exc

    try:
        chat_id = load_telegram_chat_id(FORWARD_EMAIL)
        send_telegram_forward(chat_id, code)
    except (RuntimeError, ValueError, SystemExit) as exc:
        raise RuntimeError(
            "Netflix Telegram notification was not acknowledged."
        ) from exc

    message_ids = [request_id, code_id]
    try:
        for message_id in message_ids:
            _forward_message(token, message_id)
    except (RuntimeError, ValueError, SystemExit) as exc:
        raise RuntimeError("Netflix email forwarding failed.") from exc

    try:
        for message_id in message_ids:
            delete_message(token, message_id)
    except (RuntimeError, ValueError, SystemExit) as exc:
        raise RuntimeError("Netflix email cleanup failed.") from exc

    return {
        "provider": "netflix",
        "browser_completed": True,
        "telegram_delivered": True,
        "emails_forwarded": True,
        "messages_deleted": True,
    }


def _process_viaplay(token: str) -> dict[str, object]:
    code, message = find_latest_viaplay_code(token)
    if code is None or message is None:
        raise RuntimeError("No matching Viaplay code email was found.")
    process_viaplay_message(token, code, message)
    return {"provider": "viaplay", "completed": True}


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Process provider login email workflows.")
    parser.add_argument("--provider", required=True)
    parser.add_argument("-a", "--account", default="benny")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    providers = _load_providers()
    provider = args.provider.strip().lower()
    if provider not in providers:
        print("ERROR: requested provider is not configured.", file=sys.stderr)
        return 2
    try:
        token = get_token(args.account)
        if provider == "tv2play":
            result = _process_tv2play(token, providers[provider])
        elif provider == "viaplay":
            result = _process_viaplay(token)
        elif provider == "netflix":
            (
                request_search_string,
                link_text,
                code_search_string,
                code_pattern,
            ) = _load_netflix_config()
            with PlaywrightNetflixBrowser() as browser:
                result = _process_netflix(
                    token,
                    request_search_string,
                    link_text,
                    code_search_string,
                    code_pattern,
                    browser,
                )
        else:
            print("ERROR: requested provider is not implemented.", file=sys.stderr)
            return 2
    except (RuntimeError, ValueError, SystemExit) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4

    print(
        json.dumps(result, ensure_ascii=False)
        if args.json
        else f"{provider} workflow completed."
    )
    return 4 if result.get("activation_failed") else 0


if __name__ == "__main__":
    sys.exit(main())
