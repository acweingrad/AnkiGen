from .config import DEFAULT_MODEL_BY_PROVIDER
from .providers.anthropic import AnthropicProvider, CARD_GENERATION_TOOL, CLAUDE_API_URL
from .prompt_builder import SYSTEM_PROMPT

MODEL = DEFAULT_MODEL_BY_PROVIDER["anthropic"]


class ClaudeClient:
    def __init__(self, api_key: str):
        self._provider = AnthropicProvider(api_key)

    def generate_cards(self, messages: list, config: dict) -> list:
        return self._provider.generate_cards_from_messages(messages, config)

    def _extract_cards(self, response: dict) -> list:
        return self._provider._extract_cards(response)
