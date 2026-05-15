import hashlib

from aqt import mw

from .card_types.registry import get_card_type_handler, get_default_card_type_handler


def _image_html(images: list[bytes]) -> str:
    """Build HTML that is only appended to card backs."""
    if not images:
        return ""
    fnames = _save_images_to_media(images)
    return "".join(
        f'<br><img src="{fname}" style="max-width:100%;">'
        for fname in fnames
    )


def _save_images_to_media(images: list[bytes]) -> list[str]:
    """Save PNG bytes to Anki's media folder; return the actual filenames used."""
    fnames = []
    for png_bytes in images:
        digest = hashlib.sha1(png_bytes).hexdigest()[:16]
        desired = f"ai_slide_{digest}.png"
        actual = mw.col.media.write_data(desired, png_bytes)
        fnames.append(actual)
    return fnames


def add_cards_to_collection(cards: list) -> tuple:
    """
    Writes validated cards to the Anki collection.
    Handles basic, basic_reversed, and cloze cards.
    Must be called on the main thread only.
    Returns (n_added, errors).
    """
    notetype_cache: dict = {}

    def _get_notetype(card_type: str):
        handler = get_card_type_handler(card_type) or get_default_card_type_handler()
        chosen_name = None
        chosen_notetype = None

        for candidate_name in handler.notetype_candidates:
            if candidate_name not in notetype_cache:
                notetype_cache[candidate_name] = mw.col.models.by_name(candidate_name)
            candidate = notetype_cache[candidate_name]
            if candidate is not None:
                chosen_name = candidate_name
                chosen_notetype = candidate
                break

        if chosen_name is None:
            chosen_name = handler.anki_notetype_name

        return handler, chosen_name, chosen_notetype

    added = 0
    errors = []

    for card in cards:
        try:
            card_type = card.get("card_type", "basic")
            deck_id = mw.col.decks.id(card["deck"], create=True)
            img_html = _image_html(card.get("images", []))
            handler, anki_name, notetype = _get_notetype(card_type)

            if notetype is None:
                label = card.get("text", card.get("front", ""))[:50]
                errors.append(
                    f"Notetype '{anki_name}' not found — '{label}' skipped. "
                    "Restore via Tools > Manage Note Types."
                )
                continue

            note = mw.col.new_note(notetype)
            handler.populate_note(note, card, img_html)

            note.tags = mw.col.tags.canonify(card.get("tags", []))
            mw.col.add_note(note, deck_id)
            added += 1
        except Exception as exc:
            label = card.get("text", card.get("front", ""))[:50]
            errors.append(f"Failed to add '{label}': {exc}")

    if added > 0:
        mw.col.save()

    return added, errors
