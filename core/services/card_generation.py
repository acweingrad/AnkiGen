from typing import Optional

from ..card_parser import validate_and_clean_cards
from ..config import DEFAULT_DECK, normalize_config
from ..prompts.card_generation import build_disclaimer_card
from ..providers.registry import require_provider


class CardGenerationService:
    def __init__(self, config: dict):
        self.config = normalize_config(config)

    def generate_cards(self, prompt_data: dict) -> tuple[list, list]:
        provider = require_provider(self.config["provider"])
        raw_cards = provider.generate_cards(prompt_data, self.config)
        valid_cards, warnings = validate_and_clean_cards(
            raw_cards,
            max_unique_clozes=self._max_unique_clozes(prompt_data.get("cloze_mode")),
        )
        valid_cards, limit_warnings = self._limit_cards(valid_cards, prompt_data.get("n_cards"))
        warnings.extend(limit_warnings)
        self._attach_source_images(valid_cards, prompt_data.get("images", []))

        if self.config.get("auto_add_disclaimer_card", True):
            disclaimer_deck = prompt_data.get("deck") or self.config.get("default_deck") or DEFAULT_DECK
            valid_cards.append(build_disclaimer_card(disclaimer_deck))

        return valid_cards, warnings

    @staticmethod
    def _max_unique_clozes(cloze_mode) -> Optional[int]:
        if cloze_mode == "single":
            return 1
        if cloze_mode == "multi":
            return None
        return 2

    @staticmethod
    def _attach_source_images(cards: list, images: list[bytes]) -> None:
        if not images:
            return

        for card in cards:
            source_image_index = card.pop("source_image_index", None)
            if isinstance(source_image_index, int) and 0 <= source_image_index < len(images):
                card["images"] = [images[source_image_index]]
            elif len(images) == 1:
                card["images"] = images

    @staticmethod
    def _limit_cards(cards: list, requested_count) -> tuple[list, list]:
        if not isinstance(requested_count, int) or requested_count < 1:
            return cards, []
        if len(cards) <= requested_count:
            return cards, []

        warnings = [f"Returned {len(cards)} cards; capped at requested {requested_count}"]
        return cards[:requested_count], warnings
