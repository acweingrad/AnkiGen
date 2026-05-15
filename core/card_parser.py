from typing import Optional

from .card_types.base import CardTypeValidationError
from .card_types.registry import get_card_type_handler, get_default_card_type_handler
from .config import DEFAULT_DECK


def validate_and_clean_cards(raw_cards: list, *, max_unique_clozes: Optional[int] = 2) -> tuple:
    valid = []
    warnings = []

    for i, card in enumerate(raw_cards):
        label = f"Card {i + 1}"

        if not isinstance(card, dict):
            warnings.append(f"{label}: not a dict — skipped")
            continue

        requested_type = card.get("card_type", "basic")
        if not isinstance(requested_type, str):
            requested_type = "basic"

        handler = get_card_type_handler(requested_type)
        if handler is None:
            warnings.append(f"{label}: unknown card_type '{requested_type}', treating as basic")
            handler = get_default_card_type_handler()

        working_card = dict(card)
        working_card["card_type"] = handler.key

        try:
            valid.append(
                handler.normalize(
                    working_card,
                    default_deck=DEFAULT_DECK,
                    max_unique_clozes=max_unique_clozes,
                )
            )
        except CardTypeValidationError as exc:
            warnings.append(f"{label}: {exc} — skipped")

    return valid, warnings
