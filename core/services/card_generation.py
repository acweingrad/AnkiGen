from typing import Optional

from ..card_parser import validate_and_clean_cards
from ..config import DEFAULT_DECK, normalize_config
from ..prompts.card_generation import build_disclaimer_card
from ..providers.registry import require_provider


class CardGenerationService:
    _MAX_CARDS_PER_PROVIDER_CALL = 10
    _MAX_EMPTY_PROVIDER_ATTEMPTS = 3

    def __init__(self, config: dict):
        self.config = normalize_config(config)

    def generate_cards(self, prompt_data: dict) -> tuple[list, list]:
        provider = require_provider(self.config["provider"])
        requested_count = prompt_data.get("n_cards")
        valid_cards = []
        warnings = []
        saw_raw_cards = False
        provider_calls = 0
        empty_attempts = 0
        no_progress_attempts = 0
        max_provider_calls = self._max_provider_calls_for_prompt(prompt_data, requested_count)

        while self._should_request_more(
            provider_calls,
            empty_attempts,
            no_progress_attempts,
            valid_cards,
            requested_count,
            max_provider_calls,
        ):
            attempt_prompt_data = self._build_attempt_prompt_data(
                prompt_data,
                requested_count,
                valid_cards,
                provider_calls,
            )
            provider_calls += 1
            raw_cards = provider.generate_cards(attempt_prompt_data, self.config)
            if not raw_cards:
                empty_attempts += 1
                warnings.append(f"Attempt {provider_calls}: provider returned 0 cards")
                continue

            empty_attempts = 0
            saw_raw_cards = True
            attempt_cards, attempt_warnings = validate_and_clean_cards(
                raw_cards,
                max_unique_clozes=self._max_unique_clozes(prompt_data.get("cloze_mode")),
            )
            warnings.extend(attempt_warnings)
            new_cards, duplicate_warnings = self._append_distinct_cards(valid_cards, attempt_cards)
            valid_cards.extend(new_cards)
            warnings.extend(duplicate_warnings)

            if new_cards:
                no_progress_attempts = 0
            else:
                no_progress_attempts += 1

        if not valid_cards:
            if saw_raw_cards:
                reason = "; ".join(warnings) if warnings else "No cards passed validation."
                raise RuntimeError(f"The model returned cards, but none were usable: {reason}")
            raise RuntimeError(
                "The model returned 0 cards. Try a more specific topic or paste text with "
                "clear testable medical facts."
            )

        if self._is_positive_int(requested_count) and len(valid_cards) < requested_count:
            warnings.append(
                f"Generated {len(valid_cards)} usable cards out of requested {requested_count} after {provider_calls} API calls"
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
        if not cls._is_positive_int(requested_count):
            return prompt_data

        remaining_total = max(requested_count - len(valid_cards), 1)
        batch_count = min(remaining_total, cls._MAX_CARDS_PER_PROVIDER_CALL)
        retry_prompt_data = dict(prompt_data)
        retry_prompt_data["n_cards"] = batch_count
        if attempt > 0:
            retry_prompt_data["retry_instructions"] = cls._build_retry_instructions(
                requested_count,
                remaining_total,
                batch_count,
                valid_cards,
            )
        return retry_prompt_data

    @staticmethod
    def _build_retry_instructions(requested_count: int, remaining_total: int, batch_count: int, valid_cards: list) -> str:
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
            f"The user requested {requested_count} total cards and {remaining_total} more usable card(s) are still needed. "
            f"Return exactly {batch_count} remaining distinct, fully populated card(s) in this batch. "
            "Every card must satisfy the requested card type, cloze mode, tags, deck, and grounding rules."
            f"{duplicate_instruction}"
        )

    @classmethod
    def _should_request_more(
        cls,
        provider_calls: int,
        empty_attempts: int,
        no_progress_attempts: int,
        valid_cards: list,
        requested_count,
        max_provider_calls: int,
    ) -> bool:
        if empty_attempts >= cls._MAX_EMPTY_PROVIDER_ATTEMPTS:
            return False
        if no_progress_attempts >= cls._MAX_EMPTY_PROVIDER_ATTEMPTS:
            return False
        if not cls._is_positive_int(requested_count):
            return provider_calls == 0
        if cls._has_requested_count(valid_cards, requested_count):
            return False
        return provider_calls < max_provider_calls

    @classmethod
    def _max_provider_calls(cls, requested_count) -> int:
        if not cls._is_positive_int(requested_count):
            return 1
        full_batches = (requested_count + cls._MAX_CARDS_PER_PROVIDER_CALL - 1) // cls._MAX_CARDS_PER_PROVIDER_CALL
        return full_batches + cls._MAX_EMPTY_PROVIDER_ATTEMPTS - 1

    @classmethod
    def _max_provider_calls_for_prompt(cls, prompt_data: dict, requested_count) -> int:
        if prompt_data.get("mode") == "paste":
            return 1
        return cls._max_provider_calls(requested_count)

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
