import json
import urllib.error
import urllib.request
from typing import Optional

from ..config import DEFAULT_MODEL_BY_PROVIDER, get_provider_api_key, normalize_config
from ..prompts.card_generation import SYSTEM_PROMPT, build_messages
from .base import ModelProvider

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

CARD_GENERATION_TOOL = {
    "name": "create_flashcards",
    "description": "Create a structured list of medical Anki flashcards.",
    "input_schema": {
        "type": "object",
        "properties": {
            "cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "card_type": {
                            "type": "string",
                            "enum": ["basic", "cloze", "basic_reversed"],
                            "description": (
                                "Card type. Use 'basic' for asymmetric Q&A; "
                                "'basic_reversed' for bidirectional facts (drug ↔ class, disease ↔ pathogen) "
                                "— creates two cards from one note; "
                                "'cloze' for fill-in-the-blank sentence cards."
                            ),
                        },
                        "front": {
                            "type": "string",
                            "description": "Basic and basic_reversed cards: the question on the front.",
                        },
                        "back": {
                            "type": "string",
                            "description": (
                                "Basic and basic_reversed cards: the answer on the back. "
                                "For basic_reversed, this text also becomes the front of the reversed card."
                            ),
                        },
                        "text": {
                            "type": "string",
                            "description": (
                                "Cloze cards only: the full sentence with cloze deletions marked as "
                                "{{c1::answer}}, {{c2::answer}}, etc. Each cloze number creates a "
                                "separate card. Example: 'Metoprolol is a {{c1::beta-1 selective}} "
                                "blocker used for {{c2::heart failure}}.'."
                            ),
                        },
                        "back_extra": {
                            "type": "string",
                            "description": "Cloze cards only (optional): extra context shown on the back after the answer is revealed.",
                        },
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Anki tags (domain, system, USMLE step)."},
                        "deck": {"type": "string", "description": "Target Anki deck name."},
                        "source_image_index": {
                            "type": "integer",
                            "description": (
                                "0-based index of the image (from the user message) that this card's "
                                "content primarily comes from. Omit if the card is not tied to a specific image."
                            ),
                        },
                    },
                    "required": ["card_type", "tags", "deck"],
                },
            }
        },
        "required": ["cards"],
    },
}


class AnthropicProvider(ModelProvider):
    key = "anthropic"
    display_name = "Anthropic"
    default_model = DEFAULT_MODEL_BY_PROVIDER["anthropic"]
    api_key_placeholder = "sk-ant-..."

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = str(api_key or "").strip()

    def generate_cards(self, prompt_data: dict, config: dict) -> list:
        messages = build_messages(prompt_data)
        return self.generate_cards_from_messages(messages, config)

    def generate_cards_from_messages(self, messages: list, config: dict) -> list:
        normalized = normalize_config(config)
        api_key = self.api_key or get_provider_api_key(normalized, self.key)
        if not api_key:
            raise RuntimeError("Anthropic API key is missing.")

        payload = {
            "model": normalized.get("model") or self.default_model,
            "max_tokens": normalized.get("max_tokens", 4096),
            "temperature": normalized.get("temperature", 0),
            "system": SYSTEM_PROMPT,
            "tools": [CARD_GENERATION_TOOL],
            "tool_choice": {"type": "any"},
            "messages": messages,
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            CLAUDE_API_URL,
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"API error {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error: {exc.reason}") from exc

        return self._extract_cards(data)

    def _extract_cards(self, response: dict) -> list:
        for block in response.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == "create_flashcards":
                cards = block.get("input", {}).get("cards", [])
                if not isinstance(cards, list):
                    raise RuntimeError("Unexpected cards format in tool_use response")
                return cards
        raise RuntimeError(
            "No create_flashcards tool_use block found in API response. "
            "The model may have refused to generate cards or returned an unexpected format."
        )
