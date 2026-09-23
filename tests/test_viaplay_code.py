import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import viaplay_code


class ViaplayCodeTests(unittest.TestCase):
    def setUp(self):
        self.message = {
            "id": "matched-message-id",
            "subject": "Viaplay midlertidig engangskode: ABCD",
            "receivedDateTime": "2026-09-12T13:00:00Z",
            "from": {"emailAddress": {"address": "provider@example.invalid"}},
        }

    @patch("viaplay_code.urllib.request.urlopen")
    def test_forward_message_uses_exact_graph_message_and_recipient(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 202
        urlopen.return_value = response

        viaplay_code.forward_message(
            "token",
            "matched/message",
            "recipient@example.invalid",
        )

        request = urlopen.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/matched%2Fmessage/forward"))
        self.assertEqual(
            json.loads(request.data),
            {
                "comment": "",
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": "recipient@example.invalid",
                        }
                    }
                ],
            },
        )

    @patch("viaplay_code.delete_message")
    @patch("viaplay_code.send_telegram_forward")
    @patch("viaplay_code.load_telegram_chat_id", return_value="configured-chat")
    @patch("viaplay_code.forward_message")
    def test_process_viaplay_forwards_and_acknowledges_before_exact_delete(
        self,
        email_forward,
        load_chat,
        telegram,
        delete,
    ):
        actions = MagicMock()
        actions.attach_mock(email_forward, "email")
        actions.attach_mock(telegram, "telegram")
        actions.attach_mock(delete, "delete")

        viaplay_code.process_viaplay_message("token", "ABCD", self.message)

        self.assertEqual(
            actions.mock_calls,
            [
                unittest.mock.call.email(
                    "token",
                    "matched-message-id",
                ),
                unittest.mock.call.telegram(
                    "configured-chat",
                    unittest.mock.ANY,
                ),
                unittest.mock.call.delete("token", "matched-message-id"),
            ],
        )

    @patch("viaplay_code.delete_message")
    @patch("viaplay_code.send_telegram_forward")
    @patch("viaplay_code.load_telegram_chat_id")
    @patch(
        "viaplay_code.forward_message",
        side_effect=SystemExit("sanitized forwarding failure"),
    )
    def test_process_viaplay_retains_message_when_email_forward_fails(
        self,
        email_forward,
        load_chat,
        telegram,
        delete,
    ):
        with self.assertRaises(SystemExit):
            viaplay_code.process_viaplay_message("token", "ABCD", self.message)

        load_chat.assert_not_called()
        telegram.assert_not_called()
        delete.assert_not_called()

    @patch("viaplay_code.delete_message")
    @patch(
        "viaplay_code.send_telegram_forward",
        side_effect=SystemExit("sanitized Telegram failure"),
    )
    @patch("viaplay_code.load_telegram_chat_id", return_value="configured-chat")
    @patch("viaplay_code.forward_message")
    def test_process_viaplay_retains_message_when_telegram_fails(
        self,
        email_forward,
        load_chat,
        telegram,
        delete,
    ):
        with self.assertRaises(SystemExit):
            viaplay_code.process_viaplay_message("token", "ABCD", self.message)

        email_forward.assert_called_once()
        telegram.assert_called_once()
        delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
