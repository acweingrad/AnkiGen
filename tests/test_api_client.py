import io
import json
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.api_client import ClaudeClient
from core.providers.anthropic import AnthropicProvider

CONFIG = {"max_tokens": 4096, "temperature": 0}
MESSAGES = [{"role": "user", "content": "Generate cards on beta blockers."}]

SAMPLE_CARDS = [
    {
        "front": "What is the mechanism of metoprolol?",
        "back": "Beta-1 selective adrenergic antagonist.",
        "tags": ["pharmacology", "cardiovascular"],
        "deck": "Medical::AI Generated",
    }
]


def _make_response(cards):
    body = {
        "content": [
            {
                "type": "tool_use",
                "name": "create_flashcards",
                "input": {"cards": cards},
            }
        ]
    }
    raw = json.dumps(body).encode()
    resp = MagicMock()
    resp.read.return_value = raw
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _make_http_error(code: int, message: str):
    err = urllib.error.HTTPError(
        url="https://api.anthropic.com/v1/messages",
        code=code,
        msg=message,
        hdrs={},
        fp=io.BytesIO(json.dumps({"error": message}).encode()),
    )
    return err


def _make_anthropic_http_error(code: int, message: str, headers=None):
    err = urllib.error.HTTPError(
        url="https://api.anthropic.com/v1/messages",
        code=code,
        msg=message,
        hdrs=headers or {},
        fp=io.BytesIO(json.dumps({"error": {"message": message}}).encode()),
    )
    return err


class TestClaudeClient(unittest.TestCase):
    def setUp(self):
        self.client = ClaudeClient("test-key")

    @patch("urllib.request.urlopen")
    def test_successful_response_extracts_cards(self, mock_urlopen):
        mock_urlopen.return_value = _make_response(SAMPLE_CARDS)
        cards = self.client.generate_cards(MESSAGES, CONFIG)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["front"], SAMPLE_CARDS[0]["front"])

    @patch("urllib.request.urlopen")
    def test_http_401_raises_runtime_error(self, mock_urlopen):
        mock_urlopen.side_effect = _make_http_error(401, "invalid_api_key")
        with self.assertRaises(RuntimeError) as ctx:
            self.client.generate_cards(MESSAGES, CONFIG)
        self.assertIn("401", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_http_429_raises_runtime_error(self, mock_urlopen):
        mock_urlopen.side_effect = _make_http_error(429, "rate_limit_exceeded")
        with self.assertRaises(RuntimeError) as ctx:
            self.client.generate_cards(MESSAGES, CONFIG)
        self.assertIn("429", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_http_429_uses_readable_rate_limit_message(self, mock_urlopen):
        mock_urlopen.side_effect = _make_anthropic_http_error(
            429,
            "This request would exceed your organization's rate limit.",
            {"retry-after": "12"},
        )

        with self.assertRaises(RuntimeError) as ctx:
            self.client.generate_cards(MESSAGES, CONFIG)

        message = str(ctx.exception)
        self.assertIn("Anthropic rate limit hit (429)", message)
        self.assertIn("Wait 12 seconds", message)
        self.assertIn("shorten pasted text", message)

    @patch("urllib.request.urlopen")
    def test_network_error_raises_runtime_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        with self.assertRaises(RuntimeError) as ctx:
            self.client.generate_cards(MESSAGES, CONFIG)
        self.assertIn("Network error", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_missing_tool_use_block_raises_runtime_error(self, mock_urlopen):
        body = json.dumps({"content": [{"type": "text", "text": "I cannot help."}]}).encode()
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp
        with self.assertRaises(RuntimeError) as ctx:
            self.client.generate_cards(MESSAGES, CONFIG)
        self.assertIn("tool_use", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_empty_cards_list_returned(self, mock_urlopen):
        mock_urlopen.return_value = _make_response([])
        cards = self.client.generate_cards(MESSAGES, CONFIG)
        self.assertEqual(cards, [])

    @patch("urllib.request.urlopen")
    def test_prompt_generation_retries_empty_cards_response(self, mock_urlopen):
        mock_urlopen.side_effect = [_make_response([]), _make_response(SAMPLE_CARDS)]
        provider = AnthropicProvider("test-key")

        cards = provider.generate_cards(
            {
                "mode": "topic",
                "topic": "beta blockers",
                "card_type": "mixed",
                "cloze_mode": "multi",
                "domain": None,
                "deck": "Medical::AI Generated",
                "n_cards": 10,
                "domain_hints": True,
            },
            CONFIG,
        )

        self.assertEqual(len(cards), 1)
        self.assertEqual(mock_urlopen.call_count, 2)

    def test_extract_cards_uses_later_non_empty_tool_call(self):
        response = {
            "content": [
                {"type": "tool_use", "name": "create_flashcards", "input": {"cards": []}},
                {"type": "tool_use", "name": "create_flashcards", "input": {"cards": SAMPLE_CARDS}},
            ]
        }

        cards = self.client._extract_cards(response)

        self.assertEqual(cards, SAMPLE_CARDS)

    @patch("urllib.request.urlopen")
    def test_multiple_cards_all_returned(self, mock_urlopen):
        two_cards = SAMPLE_CARDS + [
            {"front": "Q2", "back": "A2", "tags": ["anatomy"], "deck": "Medical::AI Generated"}
        ]
        mock_urlopen.return_value = _make_response(two_cards)
        cards = self.client.generate_cards(MESSAGES, CONFIG)
        self.assertEqual(len(cards), 2)


if __name__ == "__main__":
    unittest.main()
