import re
from difflib import SequenceMatcher
from typing import Optional

from ..card_parser import validate_and_clean_cards
from ..config import DEFAULT_DECK, normalize_config
from ..prompts.card_generation import build_disclaimer_card
from ..providers.registry import require_provider


class CardGenerationService:
    _MAX_CARDS_PER_PROVIDER_CALL = 10
    _MAX_CARDS_PER_SOURCE_GENERATION = 100
    _MAX_EMPTY_PROVIDER_ATTEMPTS = 3
    _MAX_IMAGES_PER_PROVIDER_CALL = 4

    def __init__(self, config: dict):
        self.config = normalize_config(config)

    def generate_cards(self, prompt_data: dict) -> tuple[list, list]:
        provider = require_provider(self.config["provider"])
        requested_count = prompt_data.get("n_cards")
        target_count = self._target_count_for_prompt(prompt_data, requested_count)

        if self._should_batch_images(prompt_data):
            valid_cards, warnings, provider_calls, saw_raw_cards = self._generate_from_image_batches(
                provider,
                prompt_data,
                requested_count,
                target_count,
            )
        else:
            valid_cards, warnings, provider_calls, saw_raw_cards = self._generate_from_single_source(
                provider,
                prompt_data,
                requested_count,
                target_count,
                [],
            )

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

        valid_cards, limit_warnings = self._limit_cards(valid_cards, requested_count, prompt_data)
        warnings.extend(limit_warnings)
        self._attach_source_images(valid_cards, prompt_data.get("images", []))

        if self.config.get("auto_add_disclaimer_card", True):
            disclaimer_deck = prompt_data.get("deck") or self.config.get("default_deck") or DEFAULT_DECK
            valid_cards.append(build_disclaimer_card(disclaimer_deck))

        return valid_cards, warnings

    def _generate_from_single_source(
        self,
        provider,
        prompt_data: dict,
        requested_count,
        target_count,
        initial_cards: list,
        *,
        image_index_offset: int = 0,
        max_provider_calls_override: Optional[int] = None,
    ) -> tuple[list, list, int, bool]:
        valid_cards = []
        valid_cards.extend(initial_cards)
        warnings = []
        saw_raw_cards = False
        provider_calls = 0
        empty_attempts = 0
        no_progress_attempts = 0
        max_provider_calls = max_provider_calls_override or self._max_provider_calls(target_count)

        while self._should_request_more(
            provider_calls,
            empty_attempts,
            no_progress_attempts,
            valid_cards,
            target_count,
            max_provider_calls,
        ):
            attempt_prompt_data = self._build_attempt_prompt_data(
                prompt_data,
                requested_count,
                target_count,
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
            self._offset_source_image_indexes(attempt_cards, image_index_offset)
            warnings.extend(attempt_warnings)
            new_cards, duplicate_warnings = self._append_distinct_cards(valid_cards, attempt_cards)
            valid_cards.extend(new_cards)
            warnings.extend(duplicate_warnings)

            if new_cards:
                no_progress_attempts = 0
            else:
                no_progress_attempts += 1

        return valid_cards, warnings, provider_calls, saw_raw_cards

    def _generate_from_image_batches(
        self,
        provider,
        prompt_data: dict,
        requested_count,
        target_count,
    ) -> tuple[list, list, int, bool]:
        images = prompt_data.get("images", [])
        valid_cards = []
        warnings = []
        total_provider_calls = 0
        saw_raw_cards = False
        batches = list(self._image_batches(images))

        for batch_number, (start_index, batch_images) in enumerate(batches, start=1):
            if (
                self._is_positive_int(target_count)
                and len(valid_cards) >= target_count
                and not self._should_exhaust_source(prompt_data)
            ):
                break

            batch_prompt_data = dict(prompt_data)
            batch_prompt_data["images"] = batch_images
            batch_prompt_data["source_batch_instructions"] = self._build_source_batch_instructions(
                start_index,
                len(batch_images),
                batch_number,
                len(batches),
            )
            batch_target_count = self._target_count_for_image_batch(
                prompt_data,
                target_count,
                len(valid_cards),
            )
            before_count = len(valid_cards)
            batch_cards, batch_warnings, batch_calls, batch_saw_raw = self._generate_from_single_source(
                provider,
                batch_prompt_data,
                requested_count,
                batch_target_count,
                valid_cards,
                image_index_offset=start_index,
                max_provider_calls_override=1,
            )
            valid_cards = batch_cards
            warnings.extend(batch_warnings)
            total_provider_calls += batch_calls
            saw_raw_cards = saw_raw_cards or batch_saw_raw

            if len(valid_cards) == before_count and not self._should_exhaust_source(prompt_data):
                break

        return valid_cards, warnings, total_provider_calls, saw_raw_cards

    @classmethod
    def _should_batch_images(cls, prompt_data: dict) -> bool:
        images = prompt_data.get("images", [])
        return (
            prompt_data.get("mode") == "paste"
            and isinstance(images, list)
            and len(images) > cls._MAX_IMAGES_PER_PROVIDER_CALL
        )

    @classmethod
    def _image_batches(cls, images: list) -> list[tuple[int, list]]:
        return [
            (start, images[start : start + cls._MAX_IMAGES_PER_PROVIDER_CALL])
            for start in range(0, len(images), cls._MAX_IMAGES_PER_PROVIDER_CALL)
        ]

    @classmethod
    def _target_count_for_image_batch(cls, prompt_data: dict, target_count, accepted_count: int) -> int:
        if not cls._is_positive_int(target_count):
            return target_count
        if cls._should_exhaust_source(prompt_data):
            return min(target_count, accepted_count + cls._MAX_CARDS_PER_PROVIDER_CALL)
        return target_count

    @staticmethod
    def _build_source_batch_instructions(
        start_index: int,
        image_count: int,
        batch_number: int,
        batch_total: int,
    ) -> str:
        end_index = start_index + image_count - 1
        if start_index == end_index:
            slide_text = f"original slide image {start_index}"
        else:
            slide_text = f"original slide images {start_index} through {end_index}"
        return (
            f"This is slide batch {batch_number} of {batch_total}. "
            f"The images in this API call are {slide_text}; do not create cards from slides outside this batch. "
            "Avoid repeating facts already accepted from earlier batches."
        )

    @staticmethod
    def _offset_source_image_indexes(cards: list, offset: int) -> None:
        if not offset:
            return
        for card in cards:
            source_image_index = card.get("source_image_index")
            if isinstance(source_image_index, int):
                card["source_image_index"] = source_image_index + offset

    @classmethod
    def _build_attempt_prompt_data(
        cls,
        prompt_data: dict,
        requested_count,
        target_count,
        valid_cards: list,
        attempt: int,
    ) -> dict:
        if not cls._is_positive_int(target_count):
            return prompt_data

        remaining_total = max(target_count - len(valid_cards), 1)
        batch_count = min(remaining_total, cls._MAX_CARDS_PER_PROVIDER_CALL)
        retry_prompt_data = dict(prompt_data)
        retry_prompt_data["n_cards"] = batch_count
        source_batch_instructions = str(prompt_data.get("source_batch_instructions") or "").strip()
        if attempt > 0:
            retry_instructions = cls._build_retry_instructions(
                requested_count,
                target_count,
                remaining_total,
                batch_count,
                valid_cards,
                exhaust_source=cls._should_exhaust_source(prompt_data),
            )
            retry_prompt_data["retry_instructions"] = cls._combine_instructions(
                source_batch_instructions,
                retry_instructions,
            )
        elif source_batch_instructions:
            retry_prompt_data["retry_instructions"] = cls._combine_instructions(
                source_batch_instructions,
                cls._build_duplicate_instruction(valid_cards),
            )
        return retry_prompt_data

    @staticmethod
    def _combine_instructions(*instructions: str) -> str:
        return "\n\n".join(str(instruction).strip() for instruction in instructions if str(instruction).strip())

    @staticmethod
    def _build_retry_instructions(
        requested_count: int,
        target_count: int,
        remaining_total: int,
        batch_count: int,
        valid_cards: list,
        *,
        exhaust_source: bool = False,
    ) -> str:
        duplicate_instruction = CardGenerationService._build_duplicate_instruction(valid_cards)
        if exhaust_source:
            return (
                f"Continue extracting distinct cards from the same pasted source. "
                f"The original visible request was {requested_count} card(s), but source mode should keep going "
                f"in separate API calls until no supported, non-duplicate high-yield facts remain. "
                f"There are {remaining_total} slot(s) left before the safety cap of {target_count}. "
                f"Return exactly {batch_count} additional distinct, fully populated card(s) in this batch. "
                "If no more supported non-duplicate facts remain in the provided source, call create_flashcards "
                "with an empty cards array. Every card must satisfy the requested card type, cloze mode, tags, "
                "deck, and grounding rules."
                f"{duplicate_instruction}"
            )
        return (
            f"The previous response produced fewer usable cards than requested. "
            f"The user requested {requested_count} total cards and {remaining_total} more usable card(s) are still needed. "
            f"Return exactly {batch_count} remaining distinct, fully populated card(s) in this batch. "
            "Every card must satisfy the requested card type, cloze mode, tags, deck, and grounding rules."
            f"{duplicate_instruction}"
        )

    @staticmethod
    def _build_duplicate_instruction(valid_cards: list) -> str:
        accepted = []
        for card in valid_cards:
            if card.get("card_type") == "cloze":
                accepted.append(card.get("text", ""))
            else:
                accepted.append(f"{card.get('front', '')} -> {card.get('back', '')}")
        accepted_text = "\n".join(f"- {text}" for text in accepted if text)
        return (
            "\n\nAlready accepted cards; do not duplicate these facts:\n" + accepted_text
            if accepted_text
            else ""
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
        return requested_count + cls._MAX_EMPTY_PROVIDER_ATTEMPTS - 1

    @classmethod
    def _target_count_for_prompt(cls, prompt_data: dict, requested_count) -> int:
        if cls._should_exhaust_source(prompt_data):
            return cls._MAX_CARDS_PER_SOURCE_GENERATION
        return requested_count

    @staticmethod
    def _should_exhaust_source(prompt_data: dict) -> bool:
        requested_count = prompt_data.get("n_cards")
        return (
            prompt_data.get("mode") == "paste"
            and isinstance(requested_count, int)
            and requested_count >= CardGenerationService._MAX_CARDS_PER_PROVIDER_CALL
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
        existing_fact_keys = {cls._card_fact_key(card) for card in existing_cards}
        distinct_cards = []
        warnings = []

        for card in new_cards:
            key = cls._card_identity(card)
            fact_key = cls._card_fact_key(card)
            if key in existing_keys or cls._is_duplicate_fact(fact_key, existing_fact_keys):
                warnings.append("Duplicate generated card skipped")
                continue
            existing_keys.add(key)
            existing_fact_keys.add(fact_key)
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

    @classmethod
    def _card_fact_key(cls, card: dict) -> str:
        if card.get("card_type") == "cloze":
            text = card.get("text", "")
        else:
            text = f"{card.get('front', '')} {card.get('back', '')}"
        return cls._normalize_fact_text(text)

    @staticmethod
    def _normalize_fact_text(text: str) -> str:
        text = re.sub(r"\{\{c\d+::(.*?)(?:::[^{}]*)?\}\}", r"\1", text or "")
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"[^a-z0-9]+", " ", text.lower())
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _is_duplicate_fact(fact_key: str, existing_fact_keys: set[str]) -> bool:
        if not fact_key:
            return False
        if fact_key in existing_fact_keys:
            return True
        return any(
            len(fact_key) >= 40
            and len(existing_key) >= 40
            and SequenceMatcher(None, fact_key, existing_key).ratio() >= 0.96
            for existing_key in existing_fact_keys
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
    def _limit_cards(cards: list, requested_count, prompt_data: Optional[dict] = None) -> tuple[list, list]:
        if CardGenerationService._should_exhaust_source(prompt_data or {}):
            return cards, []
        if not isinstance(requested_count, int) or requested_count < 1:
            return cards, []
        if len(cards) <= requested_count:
            return cards, []

        warnings = [f"Returned {len(cards)} cards; capped at requested {requested_count}"]
        return cards[:requested_count], warnings
