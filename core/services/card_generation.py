from typing import Optional

from ..card_parser import validate_and_clean_cards
from ..config import DEFAULT_DECK, normalize_config
from ..prompts.card_generation import build_disclaimer_card
from ..providers.registry import require_provider


class CardGenerationService:
    _MAX_PROVIDER_ATTEMPTS = 3

    def __init__(self, config: dict):
        self.config = normalize_config(config)

    def generate_cards(self, prompt_data: dict) -> tuple[list, list]:
        provider = require_provider(self.config["provider"])
        requested_count = prompt_data.get("n_cards")
        valid_cards = []
        warnings = []
        saw_raw_cards = False

        for attempt in range(self._MAX_PROVIDER_ATTEMPTS):
            attempt_prompt_data = self._build_attempt_prompt_data(
                prompt_data,
                requested_count,
                valid_cards,
                attempt,
            )
            raw_cards = provider.generate_cards(attempt_prompt_data, self.config)
            if not raw_cards:
                warnings.append(f"Attempt {attempt + 1}: provider returned 0 cards")
                continue

            saw_raw_cards = True
            attempt_cards, attempt_warnings = validate_and_clean_cards(
                raw_cards,
                max_unique_clozes=self._max_unique_clozes(prompt_data.get("cloze_mode")),
            )
            warnings.extend(attempt_warnings)
            new_cards, duplicate_warnings = self._append_distinct_cards(valid_cards, attempt_cards)
            valid_cards.extend(new_cards)
            warnings.extend(duplicate_warnings)

            if not self._is_positive_int(requested_count) or self._has_requested_count(valid_cards, requested_count):
                break

        if not valid_cards:
            if saw_raw_cards:
                reason = "; ".join(warnings) if warnings else "No cards passed validation."
                raise RuntimeError(f"The model returned cards, but none were usable: {reason}")
            raise RuntimeError(
                "The model returned 0 cards. Try a more specific topic or paste text with "
                "clear testable medical facts."
            )

        if self._is_positive_int(requested_count) and len(valid_cards) < requested_count:
            reason = "; ".join(warnings) if warnings else "No retry details available."
            raise RuntimeError(
                f"The model returned {len(valid_cards)} usable cards, but {requested_count} were requested: {reason}"
            )

        valid_cards, limit_warnings = self._limit_cards(valid_cards, requested_count)
        warnings.extend(limit_warnings)
        self._attach_source_images(valid_cards, prompt_data.get("images", []))

        if self.config.get("auto_add_disclaimer_card", True):
            disclaimer_deck = prompt_data.get("deck") or self.config.get("default_deck") or DEFAULT_DECK
            valid_cards.append(build_disclaimer_card(disclaimer_deck))

        return valid_cards, warnings

    @classmethod
    def _build_attempt_prompt_data(cls, prompt_data: dict, requested_count, valid_cards: list, attempt: int) -> dict:
        if attempt == 0 or not cls._is_positive_int(requested_count):
            return prompt_data

        remaining = max(requested_count - len(valid_cards), 1)
        retry_prompt_data = dict(prompt_data)
        retry_prompt_data["n_cards"] = remaining
        retry_prompt_data["retry_instructions"] = cls._build_retry_instructions(
            requested_count,
            remaining,
            valid_cards,
        )
        return retry_prompt_data

    @staticmethod
    def _build_retry_instructions(requested_count: int, remaining: int, valid_cards: list) -> str:
        accepted = []
        for card in valid_cards:
            if card.get("card_type") == "cloze":
                accepted.append(card.get("text", ""))
            else:
                accepted.append(f"{card.get('front', '')} -> {card.get('back', '')}")
        accepted_text = "\n".join(f"- {text}" for text in accepted if text)
        duplicate_instruction = (
            "\n\nAlready accepted cards; do not duplicate these facts:\n" + accepted_text
            if accepted_text
            else ""
        )
        return (
            f"The previous response produced fewer usable cards than requested. "
            f"The user requested {requested_count} cards and {remaining} more usable card(s) are still needed. "
            "Return only the remaining distinct, fully populated cards. "
            "Every card must satisfy the requested card type, cloze mode, tags, deck, and grounding rules."
            f"{duplicate_instruction}"
        )

    @staticmethod
    def _max_unique_clozes(cloze_mode) -> Optional[int]:
        if cloze_mode == "single":
            return 1
        if cloze_mode == "multi":
            return None
        return 2

    @staticmethod
    def _is_positive_int(value) -> bool:
        return isinstance(value, int) and value > 0

    @classmethod
    def _has_requested_count(cls, cards: list, requested_count) -> bool:
        return cls._is_positive_int(requested_count) and len(cards) >= requested_count

    @classmethod
    def _append_distinct_cards(cls, existing_cards: list, new_cards: list) -> tuple[list, list]:
        existing_keys = {cls._card_identity(card) for card in existing_cards}
        distinct_cards = []
        warnings = []

        for card in new_cards:
            key = cls._card_identity(card)
            if key in existing_keys:
                warnings.append("Duplicate generated card skipped")
                continue
            existing_keys.add(key)
            distinct_cards.append(card)

        return distinct_cards, warnings

    @staticmethod
    def _card_identity(card: dict) -> tuple:
        card_type = card.get("card_type")
        if card_type == "cloze":
            return (card_type, card.get("text", "").strip().lower())
        return (
            card_type,
            card.get("front", "").strip().lower(),
            card.get("back", "").strip().lower(),
        )

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
