import re

from ..config import DEFAULT_DECK
from .base import CardTypeHandler, CardTypeValidationError

_CLOZE_RE = re.compile(r"\{\{c\d+::.+?\}\}")


def _normalize_tags(tags) -> list[str]:
    if not isinstance(tags, list):
        tags = [str(tags)] if tags else []
    return [str(tag).strip() for tag in tags if str(tag).strip()]


def _normalize_deck(deck, default_deck: str) -> str:
    if not isinstance(deck, str) or not deck.strip():
        return default_deck
    return deck.strip()


def _copy_source_image_index(card: dict, entry: dict) -> dict:
    source_image_index = card.get("source_image_index")
    if isinstance(source_image_index, int):
        entry["source_image_index"] = source_image_index
    return entry


class BasicCardType(CardTypeHandler):
    key = "basic"
    anki_notetype_name = "Basic"

    def normalize(self, card: dict, default_deck: str = DEFAULT_DECK) -> dict:
        front = card.get("front", "")
        if not isinstance(front, str) or not front.strip():
            raise CardTypeValidationError("missing or empty front")

        back = card.get("back", "")
        if not isinstance(back, str) or not back.strip():
            raise CardTypeValidationError("missing or empty back")

        entry = {
            "card_type": self.key,
            "front": front.strip(),
            "back": back.strip(),
            "tags": _normalize_tags(card.get("tags", [])),
            "deck": _normalize_deck(card.get("deck", ""), default_deck),
        }
        return _copy_source_image_index(card, entry)

    def populate_note(self, note, card: dict, image_html: str) -> None:
        note.fields[0] = card["front"]
        note.fields[1] = card["back"] + image_html


class BasicReversedCardType(BasicCardType):
    key = "basic_reversed"
    anki_notetype_name = "Basic (and reversed card)"

    def normalize(self, card: dict, default_deck: str = DEFAULT_DECK) -> dict:
        entry = super().normalize(card, default_deck)
        entry["card_type"] = self.key
        return entry


class ClozeCardType(CardTypeHandler):
    key = "cloze"
    anki_notetype_name = "Cloze"
    _MAX_UNIQUE_CLOZES = 2

    @property
    def notetype_candidates(self) -> tuple[str, ...]:
        return (
            "AnKingOverhaul (AnKing Step Deck / AnKingMed)",
            self.anki_notetype_name,
        )

    def normalize(self, card: dict, default_deck: str = DEFAULT_DECK) -> dict:
        text = card.get("text", "")
        if not isinstance(text, str) or not text.strip():
            raise CardTypeValidationError("cloze card missing text")
        if not _CLOZE_RE.search(text):
            raise CardTypeValidationError("cloze card has no {{c1::...}} deletions")
        unique_cloze_numbers = set(re.findall(r"\{\{c(\d+)::", text))
        if len(unique_cloze_numbers) > self._MAX_UNIQUE_CLOZES:
            raise CardTypeValidationError(
                f"cloze card has too many distinct deletions ({len(unique_cloze_numbers)} > {self._MAX_UNIQUE_CLOZES})"
            )

        back_extra = card.get("back_extra", "")
        if not isinstance(back_extra, str):
            back_extra = ""

        entry = {
            "card_type": self.key,
            "text": text.strip(),
            "back_extra": back_extra.strip(),
            "tags": _normalize_tags(card.get("tags", [])),
            "deck": _normalize_deck(card.get("deck", ""), default_deck),
        }
        return _copy_source_image_index(card, entry)

    def populate_note(self, note, card: dict, image_html: str) -> None:
        note.fields[0] = card["text"]
        note.fields[1] = card.get("back_extra", "") + image_html


BUILTIN_CARD_TYPES = [
    BasicCardType(),
    BasicReversedCardType(),
    ClozeCardType(),
]
