import io
import socket
import ssl
import sys
import unittest
import urllib.error
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import provider_codes


class ProviderCodesTests(unittest.TestCase):
    def test_extract_exact_link_accepts_only_exact_visible_text(self):
        html = '<a href="https://login.tv2.dk/activate">Bekræft midlertidig adgang</a>'
        self.assertEqual(
            provider_codes._extract_exact_link(html),
            "https://login.tv2.dk/activate",
        )

    def test_extract_exact_link_rejects_unrelated_link(self):
        html = '<a href="https://login.tv2.dk/activate">Andet link</a>'
        with self.assertRaises(ValueError):
            provider_codes._extract_exact_link(html)

    def test_validate_tv2_url_rejects_non_https_and_unowned_hosts(self):
        invalid_urls = (
            "http://login.tv2.dk/activate",
            "https://tv2.dk.example.org/activate",
            "https://user@tv2.dk/activate",
        )
        for url in invalid_urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                provider_codes._validate_tv2_url(url)

    def test_resolve_tv2_url_accepts_real_nested_wrapper_shape(self):
        destination = (
            "https://anti-sharing-graph.discovery.tv2api.dk/activate"
            "?token=opaque"
        )
        aws_url = (
            "https://w9hhrd9t.r.eu-central-1.awstrack.me/L0/"
            f"{urllib.parse.quote(destination, safe=':')}/1/opaque/opaque/opaque"
        )
        safe_link = (
            "https://emea01.safelinks.protection.outlook.com/"
            f"?url={urllib.parse.quote(aws_url, safe='')}&data=opaque"
        )

        self.assertEqual(provider_codes._resolve_tv2_url(safe_link), destination)

    def test_resolve_tv2_url_rejects_wrapper_and_destination_lookalikes(self):
        malicious_urls = (
            (
                "https://emea01.safelinks.protection.outlook.com.example.org/"
                "?url=https%3A%2F%2Flogin.tv2.dk%2Factivate"
            ),
            (
                "https://emea01.safelinks.protection.outlook.com/"
                "?url=https%3A%2F%2Flogin.tv2.dk.example.org%2Factivate"
            ),
            (
                "https://tracking.r.eu-central-1.awstrack.me.example.org/L0/"
                "https:%2F%2Flogin.tv2.dk%2Factivate/1/opaque"
            ),
            (
                "https://tracking.r.eu-central-1.awstrack.me/L0/"
                "http:%2F%2Flogin.tv2.dk%2Factivate/1/opaque"
            ),
        )
        for url in malicious_urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                provider_codes._resolve_tv2_url(url)

    def test_resolve_tv2_url_rejects_ambiguous_safe_link_destination(self):
        url = (
            "https://emea01.safelinks.protection.outlook.com/"
            "?url=https%3A%2F%2Flogin.tv2.dk%2Fone"
            "&url=https%3A%2F%2Flogin.tv2.dk%2Ftwo"
        )

        with self.assertRaises(ValueError):
            provider_codes._resolve_tv2_url(url)

    @patch("provider_codes.urllib.request.build_opener")
    def test_activate_tv2_uses_browser_get_headers_and_cookie_support(self, build_opener):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.geturl.return_value = "https://login.tv2.dk/activate"
        response.read.return_value = b"OK"
        build_opener.return_value.open.return_value = response

        result = provider_codes._activate_tv2("https://login.tv2.dk/activate")

        self.assertEqual(result, (200, True))
        request = build_opener.return_value.open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIn("text/html", request.get_header("Accept"))
        self.assertTrue(request.get_header("User-agent").startswith("Mozilla/5.0"))
        self.assertTrue(
            any(
                isinstance(handler, provider_codes.urllib.request.HTTPCookieProcessor)
                for handler in build_opener.call_args.args
            )
        )

    @patch("provider_codes.urllib.request.build_opener")
    def test_activate_tv2_reports_sanitized_http_reason(self, build_opener):
        error = urllib.error.HTTPError(
            "https://login.tv2.dk/private?token=secret",
            410,
            "secret server message",
            {},
            io.BytesIO(b'{"detail":"Activation link expired","token":"secret"}'),
        )
        build_opener.return_value.open.side_effect = error

        with self.assertRaisesRegex(
            RuntimeError,
            r"HTTP 410 \(client error\); reason: expired",
        ) as raised:
            provider_codes._activate_tv2("https://login.tv2.dk/activate")

        text = str(raised.exception)
        self.assertNotIn("secret", text)
        self.assertNotIn("private", text)

    @patch("provider_codes.urllib.request.build_opener")
    def test_activate_tv2_classifies_already_used_as_trustworthy_expiry(self, build_opener):
        error = urllib.error.HTTPError(
            "https://login.tv2.dk/activate",
            410,
            "Gone",
            {},
            io.BytesIO(b'{"detail":"Activation link already used"}'),
        )
        build_opener.return_value.open.side_effect = error

        with self.assertRaises(provider_codes._TV2ActivationError) as raised:
            provider_codes._activate_tv2("https://login.tv2.dk/activate")

        self.assertEqual(raised.exception.reason, "already-used")
        self.assertEqual(raised.exception.http_status, 410)

    @patch("provider_codes.urllib.request.build_opener")
    def test_activate_tv2_classifies_404_html_error_heading_as_expired(
        self,
        build_opener,
    ):
        error = urllib.error.HTTPError(
            "https://login.tv2.dk/activate",
            404,
            "Not Found",
            {},
            io.BytesIO(
                b"<html><body><h1> Der <span>skete en fejl</span> </h1></body></html>"
            ),
        )
        build_opener.return_value.open.side_effect = error

        with self.assertRaises(provider_codes._TV2ActivationError) as raised:
            provider_codes._activate_tv2("https://login.tv2.dk/activate")

        self.assertEqual(raised.exception.reason, "expired")
        self.assertEqual(raised.exception.http_status, 404)
        self.assertNotIn("Der skete en fejl", str(raised.exception))

    @patch("provider_codes.urllib.request.build_opener")
    def test_activate_tv2_classifies_200_html_error_heading_as_expired(
        self,
        build_opener,
    ):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.geturl.return_value = "https://login.tv2.dk/activate"
        response.read.return_value = (
            b"<html><body><h1>\n Der skete en fejl \t</h1></body></html>"
        )
        build_opener.return_value.open.return_value = response

        with self.assertRaises(provider_codes._TV2ActivationError) as raised:
            provider_codes._activate_tv2("https://login.tv2.dk/activate")

        self.assertEqual(raised.exception.reason, "expired")
        self.assertEqual(raised.exception.http_status, 200)
        self.assertNotIn("Der skete en fejl", str(raised.exception))

    @patch("provider_codes.urllib.request.build_opener")
    def test_activate_tv2_does_not_classify_html_error_heading_lookalike(
        self,
        build_opener,
    ):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.geturl.return_value = "https://login.tv2.dk/activate"
        response.read.return_value = (
            b"<html><body><script>Der skete en fejl</script>"
            b"<h1><span>Der skete en fejl</span> igen</h1></body></html>"
        )
        build_opener.return_value.open.return_value = response

        result = provider_codes._activate_tv2("https://login.tv2.dk/activate")

        self.assertEqual(result, (200, False))

    @patch("provider_codes.urllib.request.build_opener")
    def test_activate_tv2_classifies_timeout_tls_and_dns_without_details(self, build_opener):
        failures = (
            (TimeoutError("sensitive timeout detail"), "timeout"),
            (urllib.error.URLError(ssl.SSLError("sensitive TLS detail")), "TLS error"),
            (urllib.error.URLError(socket.gaierror("sensitive DNS detail")), "DNS error"),
        )
        for failure, classification in failures:
            with self.subTest(classification=classification):
                build_opener.return_value.open.side_effect = failure
                with self.assertRaisesRegex(RuntimeError, classification) as raised:
                    provider_codes._activate_tv2("https://login.tv2.dk/activate")
                self.assertNotIn("sensitive", str(raised.exception))

    def test_redirect_handler_rejects_non_tv2_destination_safely(self):
        handler = provider_codes._ValidatedRedirectHandler()
        request = urllib.request.Request("https://login.tv2.dk/activate")

        with self.assertRaisesRegex(
            provider_codes._RedirectHostRejected,
            "redirect host rejection",
        ) as raised:
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://wrapper.example/path?token=secret",
            )

        self.assertNotIn("wrapper", str(raised.exception))
        self.assertNotIn("secret", str(raised.exception))

    def test_confirmation_requires_exact_normalized_visible_text(self):
        exact = {
            "body": {
                "content": (
                    "<html><body><h1>Midlertidig <span>adgang er</span> "
                    "bekræftet.</h1><script>Midlertidig adgang er bekræftet.</script>"
                    "</body></html>"
                )
            }
        }
        hidden_only = {
            "body": {
                "content": (
                    "<style>.x{display:none}</style>"
                    "<div hidden>Midlertidig adgang er bekræftet.</div>"
                    "<p>Midlertidig adgang er bekræftet. igen</p>"
                )
            }
        }

        self.assertTrue(provider_codes._has_confirmation(exact))
        self.assertFalse(provider_codes._has_confirmation(hidden_only))

    @patch("provider_codes._graph_json")
    def test_find_confirmation_rejects_stale_and_request_messages(self, graph_json):
        graph_json.return_value = {
            "value": [
                {
                    "id": "stale-confirmation",
                    "receivedDateTime": "2026-09-12T12:59:59Z",
                    "body": {"content": "Midlertidig adgang er bekræftet."},
                },
                {
                    "id": "request-id",
                    "receivedDateTime": "2026-09-12T13:01:00Z",
                    "body": {"content": "Midlertidig adgang er bekræftet."},
                },
            ]
        }

        result = provider_codes._find_tv2_confirmation(
            "token",
            not_before=provider_codes._parse_graph_datetime(
                "2026-09-12T13:00:00Z"
            ),
            excluded_message_ids={"request-id"},
        )

        self.assertIsNone(result)

    @patch("provider_codes._find_tv2_confirmation")
    def test_poll_confirmation_finds_delayed_message_without_real_sleep(self, find):
        confirmation = {"id": "confirmation-id"}
        find.side_effect = [None, None, confirmation]
        clock = [0.0]
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)
            clock[0] += seconds

        result = provider_codes._poll_for_tv2_confirmation(
            "token",
            not_before=provider_codes._parse_graph_datetime(
                "2026-09-12T13:00:00Z"
            ),
            excluded_message_ids={"request-id"},
            sleep_fn=fake_sleep,
            monotonic_fn=lambda: clock[0],
        )

        self.assertEqual(result, confirmation)
        self.assertEqual(sleeps, [30, 30])
        self.assertEqual(
            provider_codes.TV2_CONFIRMATION_TIMEOUT_SECONDS,
            120,
        )

    @patch("provider_codes.delete_message")
    @patch("provider_codes.send_telegram_forward")
    @patch("provider_codes.load_telegram_chat_id", return_value="configured-chat")
    @patch("provider_codes._forward_message")
    @patch(
        "provider_codes._poll_for_tv2_confirmation",
        return_value={"id": "confirmation-id"},
    )
    @patch("provider_codes._activate_tv2", return_value=(200, False))
    @patch("provider_codes._find_latest_message")
    def test_process_tv2play_confirms_then_cleans_exact_messages(
        self,
        find_message,
        activate,
        poll_confirmation,
        forward_message,
        load_chat,
        telegram,
        delete,
    ):
        find_message.return_value = {
            "id": "request-id",
            "receivedDateTime": "2026-09-12T13:00:00Z",
            "body": {
                "content": (
                    '<a href="https://login.tv2.dk/activate">'
                    "Bekræft midlertidig adgang</a>"
                )
            },
        }
        actions = MagicMock()
        actions.attach_mock(telegram, "telegram")
        actions.attach_mock(forward_message, "forward")
        actions.attach_mock(delete, "delete")

        result = provider_codes._process_tv2play("token", "configured search")

        self.assertTrue(result["confirmation_text"])
        self.assertTrue(result["email_forwarded"])
        self.assertTrue(result["confirmation_email_forwarded"])
        self.assertTrue(result["original_deleted"])
        self.assertTrue(result["confirmation_deleted"])
        activate.assert_called_once_with("https://login.tv2.dk/activate")
        telegram.assert_called_once_with("configured-chat", "TV2PLAY bekræftet")
        self.assertEqual(
            forward_message.call_args_list,
            [
                unittest.mock.call("token", "request-id"),
                unittest.mock.call("token", "confirmation-id"),
            ],
        )
        self.assertEqual(
            actions.mock_calls,
            [
                unittest.mock.call.telegram(
                    "configured-chat",
                    "TV2PLAY bekræftet",
                ),
                unittest.mock.call.forward("token", "request-id"),
                unittest.mock.call.forward("token", "confirmation-id"),
                unittest.mock.call.delete("token", "request-id"),
                unittest.mock.call.delete("token", "confirmation-id"),
            ],
        )

    @patch(
        "provider_codes.delete_message",
        side_effect=[None, RuntimeError("sensitive confirmation id")],
    )
    @patch("provider_codes.send_telegram_forward")
    @patch("provider_codes.load_telegram_chat_id", return_value="configured-chat")
    @patch("provider_codes._forward_message")
    @patch(
        "provider_codes._poll_for_tv2_confirmation",
        return_value={"id": "confirmation-id"},
    )
    @patch("provider_codes._activate_tv2", return_value=(200, False))
    @patch("provider_codes._find_latest_message")
    def test_process_tv2play_sanitizes_post_confirmation_cleanup_failure(
        self,
        find_message,
        activate,
        poll_confirmation,
        forward_message,
        load_chat,
        telegram,
        delete,
    ):
        find_message.return_value = {
            "id": "request-id",
            "receivedDateTime": "2026-09-12T13:00:00Z",
            "body": {
                "content": (
                    '<a href="https://login.tv2.dk/activate">'
                    "Bekræft midlertidig adgang</a>"
                )
            },
        }

        with self.assertRaisesRegex(
            RuntimeError,
            "email cleanup failed",
        ) as raised:
            provider_codes._process_tv2play("token", "configured search")

        self.assertNotIn("sensitive", str(raised.exception))

    @patch("provider_codes.delete_message")
    @patch("provider_codes.send_telegram_forward")
    @patch("provider_codes.load_telegram_chat_id", return_value="configured-chat")
    @patch(
        "provider_codes._forward_message",
        side_effect=[None, RuntimeError("sensitive forwarding detail")],
    )
    @patch(
        "provider_codes._poll_for_tv2_confirmation",
        return_value={"id": "confirmation-id"},
    )
    @patch("provider_codes._activate_tv2", return_value=(200, False))
    @patch("provider_codes._find_latest_message")
    def test_process_tv2play_retains_both_messages_when_success_forward_fails(
        self,
        find_message,
        activate,
        poll_confirmation,
        forward_message,
        load_chat,
        telegram,
        delete,
    ):
        find_message.return_value = {
            "id": "request-id",
            "receivedDateTime": "2026-09-12T13:00:00Z",
            "body": {
                "content": (
                    '<a href="https://login.tv2.dk/activate">'
                    "Bekræft midlertidig adgang</a>"
                )
            },
        }

        with self.assertRaisesRegex(
            RuntimeError,
            "email forwarding failed",
        ) as raised:
            provider_codes._process_tv2play("token", "configured search")

        self.assertNotIn("sensitive", str(raised.exception))
        self.assertEqual(forward_message.call_count, 2)
        delete.assert_not_called()

    @patch("provider_codes.delete_message")
    @patch(
        "provider_codes.send_telegram_forward",
        side_effect=RuntimeError("sensitive Telegram detail"),
    )
    @patch("provider_codes.load_telegram_chat_id", return_value="configured-chat")
    @patch("provider_codes._forward_message")
    @patch(
        "provider_codes._poll_for_tv2_confirmation",
        return_value={"id": "confirmation-id"},
    )
    @patch("provider_codes._activate_tv2", return_value=(200, False))
    @patch("provider_codes._find_latest_message")
    def test_process_tv2play_retains_both_messages_when_success_telegram_fails(
        self,
        find_message,
        activate,
        poll_confirmation,
        forward_message,
        load_chat,
        telegram,
        delete,
    ):
        find_message.return_value = {
            "id": "request-id",
            "receivedDateTime": "2026-09-12T13:00:00Z",
            "body": {
                "content": (
                    '<a href="https://login.tv2.dk/activate">'
                    "Bekræft midlertidig adgang</a>"
                )
            },
        }

        with self.assertRaisesRegex(
            RuntimeError,
            "success notification was not acknowledged",
        ) as raised:
            provider_codes._process_tv2play("token", "configured search")

        self.assertNotIn("sensitive", str(raised.exception))
        forward_message.assert_not_called()
        delete.assert_not_called()

    @patch("provider_codes.delete_message")
    @patch("provider_codes.send_telegram_forward")
    @patch("provider_codes.load_telegram_chat_id", return_value="configured-chat")
    @patch("provider_codes._forward_message")
    @patch("provider_codes._poll_for_tv2_confirmation", return_value=None)
    @patch("provider_codes._activate_tv2", return_value=(200, False))
    @patch("provider_codes._find_latest_message")
    def test_process_tv2play_timeout_notifies_and_deletes_only_request(
        self,
        find_message,
        activate,
        poll_confirmation,
        forward_message,
        load_chat,
        telegram,
        delete,
    ):
        find_message.return_value = {
            "id": "request-id",
            "receivedDateTime": "2026-09-12T13:00:00Z",
            "body": {
                "content": (
                    '<a href="https://login.tv2.dk/activate">'
                    "Bekræft midlertidig adgang</a>"
                )
            },
        }
        actions = MagicMock()
        actions.attach_mock(telegram, "telegram")
        actions.attach_mock(forward_message, "forward")
        actions.attach_mock(delete, "delete")

        result = provider_codes._process_tv2play("token", "configured search")

        self.assertEqual(
            result["activation_failure_category"],
            "confirmation timeout",
        )
        self.assertEqual(
            actions.mock_calls,
            [
                unittest.mock.call.telegram(
                    "configured-chat",
                    "TV2PLAY bekræftelse fejlede",
                ),
                unittest.mock.call.forward("token", "request-id"),
                unittest.mock.call.delete("token", "request-id"),
            ],
        )

    @patch("provider_codes.delete_message")
    @patch("provider_codes.send_telegram_forward")
    @patch("provider_codes.load_telegram_chat_id", return_value="configured-chat")
    @patch(
        "provider_codes._forward_message",
        side_effect=RuntimeError("sensitive forwarding detail"),
    )
    @patch("provider_codes._poll_for_tv2_confirmation", return_value=None)
    @patch("provider_codes._activate_tv2", return_value=(200, False))
    @patch("provider_codes._find_latest_message")
    def test_process_tv2play_timeout_retains_request_when_forward_fails(
        self,
        find_message,
        activate,
        poll_confirmation,
        forward_message,
        load_chat,
        telegram,
        delete,
    ):
        find_message.return_value = {
            "id": "request-id",
            "receivedDateTime": "2026-09-12T13:00:00Z",
            "body": {
                "content": (
                    '<a href="https://login.tv2.dk/activate">'
                    "Bekræft midlertidig adgang</a>"
                )
            },
        }

        with self.assertRaisesRegex(
            RuntimeError,
            "email forwarding failed",
        ) as raised:
            provider_codes._process_tv2play("token", "configured search")

        self.assertNotIn("sensitive", str(raised.exception))
        telegram.assert_called_once_with(
            "configured-chat",
            "TV2PLAY bekræftelse fejlede",
        )
        forward_message.assert_called_once_with("token", "request-id")
        delete.assert_not_called()

    @patch("provider_codes.delete_message")
    @patch("provider_codes.send_telegram_forward")
    @patch("provider_codes.load_telegram_chat_id", return_value="configured-chat")
    @patch("provider_codes._forward_message")
    @patch("provider_codes._graph_json")
    @patch("provider_codes._activate_tv2")
    @patch("provider_codes._find_latest_message")
    def test_process_tv2play_notifies_expiry_and_deletes_only_matched_message(
        self,
        find_message,
        activate,
        graph_json,
        forward_message,
        load_chat,
        telegram,
        delete,
    ):
        find_message.return_value = {
            "id": "opaque-id",
            "body": {
                "content": (
                    '<a href="https://login.tv2.dk/activate">'
                    "Bekræft midlertidig adgang</a>"
                )
            },
        }
        activate.side_effect = provider_codes._TV2ActivationError(
            "TV2 Play activation failed: HTTP 410 (client error); reason: expired.",
            http_status=410,
            reason="expired",
        )

        result = provider_codes._process_tv2play("token", "configured search")

        self.assertTrue(result["link_expired"])
        self.assertEqual(result["activation_failure_category"], "expired")
        self.assertTrue(result["failure_telegram_acknowledged"])
        self.assertTrue(result["original_deleted"])
        telegram.assert_called_once_with(
            "configured-chat",
            "TV2PLAY bekræftelse fejlede",
        )
        graph_json.assert_not_called()
        forward_message.assert_called_once_with("token", "opaque-id")
        delete.assert_called_once_with("token", "opaque-id")

    @patch("provider_codes.delete_message")
    @patch("provider_codes.send_telegram_forward")
    @patch("provider_codes._forward_message")
    @patch("provider_codes._activate_tv2")
    @patch("provider_codes._find_latest_message")
    @patch("provider_codes.load_telegram_chat_id", return_value="configured-chat")
    def test_process_tv2play_notifies_generic_response_failure(
        self,
        load_chat,
        find_message,
        activate,
        forward_message,
        telegram,
        delete,
    ):
        find_message.return_value = {
            "id": "opaque-id",
            "body": {
                "content": (
                    '<a href="https://login.tv2.dk/activate">'
                    "Bekræft midlertidig adgang</a>"
                )
            },
        }
        activate.side_effect = provider_codes._TV2ActivationError(
            "TV2 Play activation failed: HTTP 404 (client error).",
            http_status=404,
        )

        result = provider_codes._process_tv2play("token", "configured search")

        self.assertTrue(result["activation_failed"])
        self.assertEqual(result["http_outcome"], "HTTP 404")
        self.assertEqual(result["activation_failure_category"], "client error")
        self.assertTrue(result["failure_telegram_acknowledged"])
        self.assertTrue(result["original_deleted"])
        telegram.assert_called_once_with(
            "configured-chat",
            "TV2PLAY bekræftelse fejlede",
        )
        forward_message.assert_called_once_with("token", "opaque-id")
        delete.assert_called_once_with("token", "opaque-id")

    @patch("provider_codes.delete_message")
    @patch(
        "provider_codes.send_telegram_forward",
        side_effect=SystemExit("notification failed"),
    )
    @patch("provider_codes.load_telegram_chat_id", return_value="configured-chat")
    @patch("provider_codes._forward_message")
    @patch(
        "provider_codes._activate_tv2",
        side_effect=provider_codes._TV2ActivationError(
            "TV2 Play activation failed: timeout.",
            reason="timeout",
        ),
    )
    @patch("provider_codes._find_latest_message")
    def test_process_tv2play_reports_failure_notification_not_acknowledged(
        self,
        find_message,
        activate,
        forward_message,
        load_chat,
        telegram,
        delete,
    ):
        find_message.return_value = {
            "id": "opaque-id",
            "body": {
                "content": (
                    '<a href="https://login.tv2.dk/activate">'
                    "Bekræft midlertidig adgang</a>"
                )
            },
        }

        with self.assertRaisesRegex(
            provider_codes._TV2FailureNotificationError,
            "notification was not acknowledged",
        ):
            provider_codes._process_tv2play("token", "configured search")

        telegram.assert_called_once_with(
            "configured-chat",
            "TV2PLAY bekræftelse fejlede",
        )
        forward_message.assert_not_called()
        delete.assert_not_called()

    def test_main_returns_failure_exit_code_after_notified_activation_failure(self):
        result = {
            "provider": "tv2play",
            "activation_failed": True,
            "failure_telegram_acknowledged": True,
        }
        with (
            patch.object(sys, "argv", ["provider_codes.py", "--provider", "tv2play"]),
            patch("provider_codes.load_project_env"),
            patch("provider_codes._load_providers", return_value={"tv2play": "search"}),
            patch("provider_codes.get_token", return_value="token"),
            patch("provider_codes._process_tv2play", return_value=result),
            patch("builtins.print"),
        ):
            exit_code = provider_codes.main()

        self.assertEqual(exit_code, 4)


class _FakeNetflixBrowser:
    def __init__(self, actions, *, fail_at=None, expired=False, account_expired=False):
        self.actions = actions
        self.fail_at = fail_at
        self.expired = expired
        self.account_expired = account_expired

    def _record(self, name, value=None):
        self.actions.append((name, value))
        if self.fail_at == name:
            raise RuntimeError("sensitive browser detail")

    def open_request(self, url):
        self._record("open", url)

    def submit_account_email(self, account_email):
        self._record("account", account_email)
        if self.account_expired:
            raise provider_codes._NetflixExpiredLinkError("expired")

    def submit_code(self, code):
        self._record("code", code)

    def require_explicit_success(self):
        self._record("success")
        if self.expired:
            raise provider_codes._NetflixExpiredLinkError("expired")


class NetflixProviderCodesTests(unittest.TestCase):
    SEARCH = "Din midlertidige adgangskode til Netflix"
    CODE_SEARCH = "Netflix: Din loginkode"
    LINK_TEXT = "Hent kode"
    PATTERN = r"Indtast denne kode for at logge på\s*([0-9]{6})\b"
    BOUNDARY = provider_codes._parse_graph_datetime("2026-09-12T13:00:00Z")

    def setUp(self):
        self.request_message = {
            "id": "request-id",
            "receivedDateTime": "2026-09-12T12:59:00Z",
            "body": {
                "content": (
                    '<a href="https://www.netflix.com/account/access">'
                    f"{self.LINK_TEXT}</a>"
                )
            },
        }
        self.code_message = {
            "id": "code-id",
            "receivedDateTime": "2026-09-12T13:00:30Z",
            "subject": self.CODE_SEARCH,
            "from": {"emailAddress": {"address": "info@account.netflix.com"}},
            "body": {
                "content": (
                    "<p>Indtast denne kode for at logge på "
                    "<strong>123456</strong></p>"
                )
            },
        }

    def test_netflix_configuration_supplies_link_text_and_code_pattern(self):
        search, link_text, code_search, pattern = (
            provider_codes._load_netflix_config()
        )

        self.assertEqual(search, self.SEARCH)
        self.assertEqual(link_text, self.LINK_TEXT)
        self.assertEqual(code_search, self.CODE_SEARCH)
        self.assertEqual(pattern, self.PATTERN)

    def test_netflix_exact_link_selection_rejects_unrelated_and_duplicate_links(self):
        exact = (
            '<a href="https://www.netflix.com/help">Hjælp-center</a>'
            f'<a href="https://www.netflix.com/code">{self.LINK_TEXT}</a>'
            '<a href="https://www.netflix.com/password">ændre din adgangskode</a>'
        )
        self.assertEqual(
            provider_codes._extract_exact_link(exact, self.LINK_TEXT),
            "https://www.netflix.com/code",
        )
        with self.assertRaises(ValueError):
            provider_codes._extract_exact_link(
                exact
                + f'<a href="https://www.netflix.com/two">{self.LINK_TEXT}</a>',
                self.LINK_TEXT,
            )

    def test_netflix_url_resolution_accepts_safe_wrapper_and_rejects_lookalikes(self):
        destination = "https://www.netflix.com/account/access?token=opaque"
        safe_link = (
            "https://emea01.safelinks.protection.outlook.com/"
            f"?url={urllib.parse.quote(destination, safe='')}&data=opaque"
        )
        self.assertEqual(
            provider_codes._resolve_netflix_url(safe_link),
            destination,
        )

        invalid_urls = (
            "http://www.netflix.com/account/access",
            "https://user@www.netflix.com/account/access",
            "https://www.netflix.com:8443/account/access",
            "https://netflix.com.example.org/account/access",
            (
                "https://emea01.safelinks.protection.outlook.com.example.org/"
                f"?url={urllib.parse.quote(destination, safe='')}"
            ),
        )
        for url in invalid_urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                provider_codes._resolve_netflix_url(url)

    def test_netflix_browser_route_blocks_non_netflix_redirect(self):
        adapter = provider_codes.PlaywrightNetflixBrowser.__new__(
            provider_codes.PlaywrightNetflixBrowser
        )
        adapter._navigation_rejection = None
        adapter._page = MagicMock()
        route = MagicMock()
        route.request.is_navigation_request.return_value = True
        route.request.frame = adapter._page.main_frame
        route.request.url = "https://netflix.com.example.org/stolen"

        adapter._validate_route(route)

        route.abort.assert_called_once()
        route.continue_.assert_not_called()
        self.assertEqual(adapter._navigation_rejection, "non-Netflix navigation")

    def test_netflix_browser_allows_non_netflix_subframe_navigation(self):
        adapter = provider_codes.PlaywrightNetflixBrowser.__new__(
            provider_codes.PlaywrightNetflixBrowser
        )
        adapter._navigation_rejection = None
        adapter._page = MagicMock()
        route = MagicMock()
        route.request.is_navigation_request.return_value = True
        route.request.frame = MagicMock()
        route.request.url = "https://www.google.com/recaptcha/challenge"

        adapter._validate_route(route)

        route.continue_.assert_called_once()
        route.abort.assert_not_called()
        self.assertIsNone(adapter._navigation_rejection)

    def test_netflix_browser_requires_explicit_success_without_visible_error(self):
        adapter = provider_codes.PlaywrightNetflixBrowser.__new__(
            provider_codes.PlaywrightNetflixBrowser
        )
        adapter._raise_navigation_rejection = MagicMock()
        adapter._page = MagicMock()
        adapter._page.get_by_text.return_value.count.return_value = 0
        hidden_error = MagicMock()
        hidden_error.first.count.return_value = 0
        visible_success = MagicMock()
        visible_success.first.count.return_value = 1
        visible_success.first.is_visible.return_value = True
        adapter._page.locator.side_effect = [hidden_error, visible_success]

        adapter.require_explicit_success()

        adapter._raise_navigation_rejection.assert_called_once()

        visible_error = MagicMock()
        visible_error.first.count.return_value = 1
        visible_error.first.is_visible.return_value = True
        adapter._page.locator.side_effect = None
        adapter._page.locator.return_value = visible_error
        with self.assertRaisesRegex(RuntimeError, "displayed an error"):
            adapter.require_explicit_success()

    def test_netflix_browser_submits_email_then_continue_and_requires_code_heading(self):
        adapter = provider_codes.PlaywrightNetflixBrowser.__new__(
            provider_codes.PlaywrightNetflixBrowser
        )
        adapter._page = MagicMock()
        adapter._raise_navigation_rejection = MagicMock()

        email_continue = MagicMock()
        email_continue.count.return_value = 1
        email_continue.nth.return_value.is_visible.return_value = True
        adapter._page.get_by_role.return_value = email_continue

        sign_in_text = MagicMock()
        sign_in_text.count.return_value = 1
        sign_in_text.nth.return_value.is_visible.return_value = True
        adapter._page.get_by_text.return_value = sign_in_text

        email_input = MagicMock()
        email_input.first.count.return_value = 1
        email_input.first.is_visible.return_value = True
        page_body = MagicMock()
        page_body.inner_text.return_value = (
            "Enter the code we sent\n to your email"
        )
        adapter._page.locator.side_effect = [email_input, page_body]

        adapter.submit_account_email(provider_codes.NETFLIX_ACCOUNT_EMAIL)

        adapter._page.get_by_text.assert_called_once_with(
            provider_codes.NETFLIX_SIGN_IN_HEADING,
            exact=True,
        )
        adapter._page.locator.assert_has_calls(
            [
                unittest.mock.call("input[type='email']"),
                unittest.mock.call("body"),
            ]
        )
        adapter._page.get_by_role.assert_called_once_with(
            "button",
            name=provider_codes.NETFLIX_CONTINUE_TEXT,
            exact=True,
        )
        email_input.first.fill.assert_called_once_with(
            provider_codes.NETFLIX_ACCOUNT_EMAIL
        )
        email_continue.nth.return_value.click.assert_called_once()
        adapter._page.wait_for_load_state.assert_called_once()

    def test_netflix_browser_classifies_exact_expired_text(self):
        adapter = provider_codes.PlaywrightNetflixBrowser.__new__(
            provider_codes.PlaywrightNetflixBrowser
        )
        adapter._page = MagicMock()
        adapter._raise_navigation_rejection = MagicMock()
        expired = MagicMock()
        expired.count.return_value = 1
        expired.nth.return_value.is_visible.return_value = True
        adapter._page.get_by_text.return_value = expired

        with self.assertRaises(provider_codes._NetflixExpiredLinkError):
            adapter.require_explicit_success()

        adapter._page.get_by_text.assert_called_once_with(
            provider_codes.NETFLIX_EXPIRED_TEXT,
            exact=True,
        )

    def test_netflix_code_page_accepts_unique_visible_code_input_fallback(self):
        adapter = provider_codes.PlaywrightNetflixBrowser.__new__(
            provider_codes.PlaywrightNetflixBrowser
        )
        adapter._page = MagicMock()
        page_body = MagicMock()
        page_body.inner_text.return_value = "Check your email"
        code_input = MagicMock()
        code_input.count.return_value = 1
        code_input.nth.return_value.is_visible.return_value = True
        adapter._page.locator.side_effect = [page_body, code_input]

        adapter._require_code_entry_page()

        adapter._page.locator.assert_has_calls(
            [
                unittest.mock.call("body"),
                unittest.mock.call(", ".join(adapter._CODE_SELECTORS)),
            ]
        )

    @patch("provider_codes._graph_json")
    def test_netflix_code_lookup_rejects_stale_and_ambiguous_codes(self, graph_json):
        graph_json.return_value = {
            "value": [
                {
                    "id": "stale",
                    "receivedDateTime": "2026-09-12T12:59:59Z",
                    "subject": f"{self.SEARCH}: 111111",
                    "from": {
                        "emailAddress": {"address": "info@account.netflix.com"}
                    },
                    "body": {"content": ""},
                }
            ]
        }
        self.assertIsNone(
            provider_codes._find_netflix_code(
                "token",
                code_search_string=self.CODE_SEARCH,
                code_pattern=self.PATTERN,
                not_before=self.BOUNDARY,
                excluded_message_ids={"request-id"},
            )
        )

        graph_json.return_value = {
            "value": [
                {
                    "id": "ambiguous",
                    "receivedDateTime": "2026-09-12T13:00:01Z",
                    "subject": self.CODE_SEARCH,
                    "from": {
                        "emailAddress": {"address": "info@account.netflix.com"}
                    },
                    "body": {
                        "content": (
                            "Indtast denne kode for at logge på 111111 "
                            "Indtast denne kode for at logge på 222222"
                        )
                    },
                }
            ]
        }
        with self.assertRaisesRegex(RuntimeError, "multiple distinct codes"):
            provider_codes._find_netflix_code(
                "token",
                code_search_string=self.CODE_SEARCH,
                code_pattern=self.PATTERN,
                not_before=self.BOUNDARY,
                excluded_message_ids={"request-id"},
            )

    @patch("provider_codes._graph_json")
    def test_netflix_code_lookup_lists_recent_mail_and_matches_locally(
        self, graph_json
    ):
        fresh_listing_shape = {
            "id": "fresh-code-id",
            "receivedDateTime": "2026-09-12T13:00:01Z",
            "subject": self.CODE_SEARCH,
            "from": {"emailAddress": {"address": "info@account.netflix.com"}},
            "bodyPreview": "Indtast denne kode for at logge på.",
            "body": {
                "content": (
                    "<p>Indtast denne kode for at logge på "
                    "<strong>123456</strong></p>"
                )
            },
        }
        graph_json.return_value = {"value": [fresh_listing_shape]}

        result = provider_codes._find_netflix_code(
            "token",
            code_search_string=self.CODE_SEARCH,
            code_pattern=self.PATTERN,
            not_before=self.BOUNDARY,
            excluded_message_ids={"request-id"},
        )

        self.assertEqual(result, ("123456", fresh_listing_shape))
        params = graph_json.call_args.args[2]
        self.assertNotIn("$search", params)
        self.assertEqual(params["$orderby"], "receivedDateTime desc")

    @patch("provider_codes._graph_json")
    def test_netflix_code_lookup_ignores_observed_retained_request_shape(
        self, graph_json
    ):
        graph_json.return_value = {
            "value": [
                {
                    **self.request_message,
                    "subject": self.SEARCH,
                    "from": {
                        "emailAddress": {"address": "info@account.netflix.com"}
                    },
                    "bodyPreview": "Hent kode",
                }
            ]
        }

        self.assertIsNone(
            provider_codes._find_netflix_code(
                "token",
                code_search_string=self.CODE_SEARCH,
                code_pattern=self.PATTERN,
                not_before=self.BOUNDARY,
                excluded_message_ids={"request-id"},
            )
        )

    @patch("provider_codes._graph_json")
    def test_netflix_code_lookup_rejects_unrelated_text_and_sender(self, graph_json):
        graph_json.return_value = {
            "value": [
                {
                    "id": "wrong-sender",
                    "receivedDateTime": "2026-09-12T13:00:01Z",
                    "subject": self.CODE_SEARCH,
                    "from": {"emailAddress": {"address": "sender@example.org"}},
                    "body": {
                        "content": "Indtast denne kode for at logge på 123456"
                    },
                },
                {
                    "id": "wrong-provider",
                    "receivedDateTime": "2026-09-12T13:00:02Z",
                    "subject": "Unrelated service 654321",
                    "from": {
                        "emailAddress": {"address": "info@account.netflix.com"}
                    },
                    "body": {"content": ""},
                },
            ]
        }

        self.assertIsNone(
            provider_codes._find_netflix_code(
                "token",
                code_search_string=self.CODE_SEARCH,
                code_pattern=self.PATTERN,
                not_before=self.BOUNDARY,
                excluded_message_ids={"request-id"},
            )
        )

        graph_json.return_value = {
            "value": [
                self.code_message,
                {
                    "id": "second-code-id",
                    "receivedDateTime": "2026-09-12T13:00:31Z",
                    "subject": self.CODE_SEARCH,
                    "from": {
                        "emailAddress": {"address": "info@account.netflix.com"}
                    },
                    "body": {
                        "content": "Indtast denne kode for at logge på 333333"
                    },
                },
            ]
        }
        with self.assertRaisesRegex(RuntimeError, "Multiple fresh Netflix"):
            provider_codes._find_netflix_code(
                "token",
                code_search_string=self.CODE_SEARCH,
                code_pattern=self.PATTERN,
                not_before=self.BOUNDARY,
                excluded_message_ids={"request-id"},
            )

    @patch("provider_codes._graph_json")
    def test_netflix_code_lookup_rejects_unrelated_six_digit_value(self, graph_json):
        graph_json.return_value = {
            "value": [
                {
                    "id": "unrelated-digits",
                    "receivedDateTime": "2026-09-12T13:00:01Z",
                    "subject": self.CODE_SEARCH,
                    "from": {
                        "emailAddress": {"address": "info@account.netflix.com"}
                    },
                    "body": {"content": "<p>Reference 123456</p>"},
                }
            ]
        }

        self.assertIsNone(
            provider_codes._find_netflix_code(
                "token",
                code_search_string=self.CODE_SEARCH,
                code_pattern=self.PATTERN,
                not_before=self.BOUNDARY,
                excluded_message_ids={"request-id"},
            )
        )

    @patch("provider_codes._find_netflix_code")
    def test_netflix_code_poll_finds_delayed_fresh_email_without_real_wait(self, find):
        find.side_effect = [None, None, ("123456", self.code_message)]
        clock = [0.0]
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)
            clock[0] += seconds

        result = provider_codes._poll_for_netflix_code(
            "token",
            code_search_string=self.CODE_SEARCH,
            code_pattern=self.PATTERN,
            not_before=self.BOUNDARY,
            excluded_message_ids={"request-id"},
            sleep_fn=fake_sleep,
            monotonic_fn=lambda: clock[0],
        )

        self.assertEqual(result, ("123456", self.code_message))
        self.assertEqual(sleeps, [30, 30])
        self.assertEqual(provider_codes.NETFLIX_CODE_TIMEOUT_SECONDS, 120)

    @patch("provider_codes.delete_message")
    @patch("provider_codes._forward_message")
    @patch("provider_codes.send_telegram_forward")
    @patch("provider_codes.load_telegram_chat_id", return_value="configured-chat")
    @patch("provider_codes._poll_for_netflix_code")
    @patch("provider_codes._find_latest_message")
    def test_netflix_enters_email_submits_code_and_orders_delivery_cleanup(
        self,
        find_request,
        poll_code,
        load_chat,
        telegram,
        forward,
        delete,
    ):
        find_request.return_value = self.request_message
        poll_code.return_value = ("123456", self.code_message)
        actions = []
        browser = _FakeNetflixBrowser(actions)
        telegram.side_effect = lambda chat, text: actions.append(("telegram", text))
        forward.side_effect = lambda token, message_id: actions.append(
            ("forward", message_id)
        )
        delete.side_effect = lambda token, message_id: actions.append(
            ("delete", message_id)
        )

        def establish_boundary():
            actions.append(("boundary", None))
            return self.BOUNDARY

        result = provider_codes._process_netflix(
            "token",
            self.SEARCH,
            self.LINK_TEXT,
            self.CODE_SEARCH,
            self.PATTERN,
            browser,
            now_fn=establish_boundary,
        )

        self.assertTrue(result["browser_completed"])
        self.assertEqual(
            actions,
            [
                ("open", "https://www.netflix.com/account/access"),
                ("account", provider_codes.NETFLIX_ACCOUNT_EMAIL),
                ("boundary", None),
                ("code", "123456"),
                ("success", None),
                ("telegram", "123456"),
                ("forward", "request-id"),
                ("forward", "code-id"),
                ("delete", "request-id"),
                ("delete", "code-id"),
            ],
        )
        poll_code.assert_called_once_with(
            "token",
            code_search_string=self.CODE_SEARCH,
            code_pattern=self.PATTERN,
            not_before=self.BOUNDARY,
            excluded_message_ids={"request-id"},
            sleep_fn=None,
            monotonic_fn=None,
        )

    def _run_failure(
        self,
        *,
        browser_fail=None,
        code_timeout=False,
        telegram_error=None,
        forward_error=None,
        delete_error=None,
    ):
        actions = []
        browser = _FakeNetflixBrowser(actions, fail_at=browser_fail)
        with (
            patch(
                "provider_codes._find_latest_message",
                return_value=self.request_message,
            ),
            patch(
                "provider_codes._poll_for_netflix_code",
                return_value=None
                if code_timeout
                else ("123456", self.code_message),
            ),
            patch(
                "provider_codes.load_telegram_chat_id",
                return_value="configured-chat",
            ),
            patch(
                "provider_codes.send_telegram_forward",
                side_effect=telegram_error,
            ) as telegram,
            patch(
                "provider_codes._forward_message",
                side_effect=forward_error,
            ) as forward,
            patch(
                "provider_codes.delete_message",
                side_effect=delete_error,
            ) as delete,
        ):
            with self.assertRaises(RuntimeError):
                provider_codes._process_netflix(
                    "token",
                    self.SEARCH,
                    self.LINK_TEXT,
                    self.CODE_SEARCH,
                    self.PATTERN,
                    browser,
                    now_fn=lambda: self.BOUNDARY,
                )
        return telegram, forward, delete

    def test_netflix_browser_failure_retains_all_messages(self):
        telegram, forward, delete = self._run_failure(browser_fail="success")
        telegram.assert_not_called()
        forward.assert_not_called()
        delete.assert_not_called()

    def test_netflix_code_timeout_retains_all_messages(self):
        telegram, forward, delete = self._run_failure(code_timeout=True)
        telegram.assert_not_called()
        forward.assert_not_called()
        delete.assert_not_called()

    def test_netflix_telegram_failure_retains_all_messages(self):
        telegram, forward, delete = self._run_failure(
            telegram_error=RuntimeError("sensitive Telegram response")
        )
        telegram.assert_called_once()
        forward.assert_not_called()
        delete.assert_not_called()

    def test_netflix_forward_failure_retains_all_messages(self):
        telegram, forward, delete = self._run_failure(
            forward_error=RuntimeError("sensitive forwarding response")
        )
        telegram.assert_called_once()
        forward.assert_called_once()
        delete.assert_not_called()

    def test_netflix_cleanup_failure_leaves_remaining_source_undeleted(self):
        telegram, forward, delete = self._run_failure(
            delete_error=[None, RuntimeError("sensitive delete response")]
        )
        telegram.assert_called_once()
        self.assertEqual(forward.call_count, 2)
        self.assertEqual(delete.call_count, 2)

    @patch("provider_codes.delete_message")
    @patch("provider_codes._forward_message")
    @patch("provider_codes.send_telegram_forward")
    @patch("provider_codes.load_telegram_chat_id", return_value="configured-chat")
    @patch(
        "provider_codes._poll_for_netflix_code",
        return_value=("123456", {
            "id": "code-id",
            "receivedDateTime": "2026-09-12T13:00:30Z",
        }),
    )
    @patch("provider_codes._find_latest_message")
    def test_netflix_expired_link_notifies_forwards_then_deletes(
        self,
        find_request,
        poll_code,
        load_chat,
        telegram,
        forward,
        delete,
    ):
        del poll_code, load_chat
        find_request.return_value = self.request_message
        actions = []
        browser = _FakeNetflixBrowser(actions, expired=True)
        telegram.side_effect = lambda chat, text: actions.append(("telegram", text))
        forward.side_effect = lambda token, message_id: actions.append(
            ("forward", message_id)
        )
        delete.side_effect = lambda token, message_id: actions.append(
            ("delete", message_id)
        )

        result = provider_codes._process_netflix(
            "token",
            self.SEARCH,
            self.LINK_TEXT,
            self.CODE_SEARCH,
            self.PATTERN,
            browser,
            now_fn=lambda: self.BOUNDARY,
        )

        self.assertTrue(result["activation_failed"])
        self.assertTrue(result["link_expired"])
        self.assertEqual(
            actions[-5:],
            [
                ("telegram", "NETFLIX link udløbet"),
                ("forward", "request-id"),
                ("forward", "code-id"),
                ("delete", "request-id"),
                ("delete", "code-id"),
            ],
        )

    def test_netflix_expired_notification_failure_retains_both_messages(self):
        browser = _FakeNetflixBrowser([], expired=True)
        with (
            patch(
                "provider_codes._find_latest_message",
                return_value=self.request_message,
            ),
            patch(
                "provider_codes._poll_for_netflix_code",
                return_value=("123456", self.code_message),
            ),
            patch(
                "provider_codes.load_telegram_chat_id",
                return_value="configured-chat",
            ),
            patch(
                "provider_codes.send_telegram_forward",
                side_effect=RuntimeError("sensitive Telegram response"),
            ),
            patch("provider_codes._forward_message") as forward,
            patch("provider_codes.delete_message") as delete,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "expiry notification was not acknowledged",
            ):
                provider_codes._process_netflix(
                    "token",
                    self.SEARCH,
                    self.LINK_TEXT,
                    self.CODE_SEARCH,
                    self.PATTERN,
                    browser,
                    now_fn=lambda: self.BOUNDARY,
                )

        forward.assert_not_called()
        delete.assert_not_called()

    @patch("provider_codes.delete_message")
    @patch("provider_codes._forward_message")
    @patch("provider_codes.send_telegram_forward")
    @patch("provider_codes.load_telegram_chat_id", return_value="configured-chat")
    @patch("provider_codes._poll_for_netflix_code")
    @patch("provider_codes._find_latest_message")
    def test_netflix_old_request_fallback_notifies_forwards_and_deletes_request(
        self,
        find_request,
        poll_code,
        load_chat,
        telegram,
        forward,
        delete,
    ):
        del load_chat
        find_request.return_value = self.request_message
        browser = _FakeNetflixBrowser([], account_expired=True)

        result = provider_codes._process_netflix(
            "token",
            self.SEARCH,
            self.LINK_TEXT,
            self.CODE_SEARCH,
            self.PATTERN,
            browser,
            now_fn=lambda: self.BOUNDARY,
        )

        self.assertTrue(result["link_expired"])
        telegram.assert_called_once_with(
            "configured-chat",
            "NETFLIX link udløbet",
        )
        forward.assert_called_once_with("token", "request-id")
        delete.assert_called_once_with("token", "request-id")
        poll_code.assert_not_called()

    def test_netflix_expired_forward_failure_retains_both_messages(self):
        browser = _FakeNetflixBrowser([], expired=True)
        with (
            patch(
                "provider_codes._find_latest_message",
                return_value=self.request_message,
            ),
            patch(
                "provider_codes._poll_for_netflix_code",
                return_value=("123456", self.code_message),
            ),
            patch(
                "provider_codes.load_telegram_chat_id",
                return_value="configured-chat",
            ),
            patch("provider_codes.send_telegram_forward") as telegram,
            patch(
                "provider_codes._forward_message",
                side_effect=RuntimeError("sensitive forwarding response"),
            ) as forward,
            patch("provider_codes.delete_message") as delete,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "expired-email forwarding failed",
            ):
                provider_codes._process_netflix(
                    "token",
                    self.SEARCH,
                    self.LINK_TEXT,
                    self.CODE_SEARCH,
                    self.PATTERN,
                    browser,
                    now_fn=lambda: self.BOUNDARY,
                )

        telegram.assert_called_once_with(
            "configured-chat",
            "NETFLIX link udløbet",
        )
        forward.assert_called_once_with("token", "request-id")
        delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
