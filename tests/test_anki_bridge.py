import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import anki_bridge


def _mock_note():
    return SimpleNamespace(fields=["", ""], tags=[])


def _mock_collection():
    col = MagicMock()
    col.models.by_name.side_effect = lambda name: {"name": name}
    col.decks.id.return_value = 123
    col.tags.canonify.side_effect = lambda tags: list(tags)
    col.media.write_data.side_effect = lambda desired, _data: desired
    col.new_note.side_effect = lambda _notetype: _mock_note()
    return col


def _mock_note_with_n_fields(n: int):
    return SimpleNamespace(fields=[""] * n, tags=[])


@patch.object(anki_bridge, "mw", new_callable=MagicMock)
def test_cloze_images_are_added_only_to_back_extra(mock_mw):
    col = _mock_collection()
    added_notes = []

    def _capture(note, _deck_id):
        added_notes.append(note)
        return 1

    col.add_note.side_effect = _capture
    mock_mw.col = col

    cards = [{
        "card_type": "cloze",
        "text": "Metoprolol is {{c1::beta-1 selective}}.",
        "back_extra": "Used in HFrEF.",
        "tags": ["pharmacology"],
        "deck": "Medical::AI Generated",
        "images": [b"png-bytes"],
    }]

    added, errors = anki_bridge.add_cards_to_collection(cards)

    assert added == 1
    assert errors == []
    assert added_notes[0].fields[0] == cards[0]["text"]
    assert cards[0]["back_extra"] in added_notes[0].fields[1]
    assert "<img " in added_notes[0].fields[1]


@patch.object(anki_bridge, "mw", new_callable=MagicMock)
def test_cloze_prefers_anking_notetype_when_available(mock_mw):
    col = _mock_collection()
    added_notes = []

    def _by_name(name):
        if name == "AnKingOverhaul (AnKing Step Deck / AnKingMed)":
            return {"name": name}
        if name == "Cloze":
            return {"name": name}
        return {"name": name}

    def _new_note(notetype):
        if notetype["name"] == "AnKingOverhaul (AnKing Step Deck / AnKingMed)":
            return _mock_note_with_n_fields(18)
        return _mock_note()

    def _capture(note, _deck_id):
        added_notes.append(note)
        return 1

    col.models.by_name.side_effect = _by_name
    col.new_note.side_effect = _new_note
    col.add_note.side_effect = _capture
    mock_mw.col = col

    cards = [{
        "card_type": "cloze",
        "text": "Metoprolol is {{c1::beta-1 selective}}.",
        "back_extra": "Used in HFrEF.",
        "tags": ["pharmacology"],
        "deck": "Medical::AI Generated",
    }]

    added, errors = anki_bridge.add_cards_to_collection(cards)

    assert added == 1
    assert errors == []
    assert len(added_notes[0].fields) == 18
    assert added_notes[0].fields[0] == cards[0]["text"]
    assert added_notes[0].fields[1] == cards[0]["back_extra"]


@patch.object(anki_bridge, "mw", new_callable=MagicMock)
def test_cloze_falls_back_to_standard_cloze_when_anking_missing(mock_mw):
    col = _mock_collection()
    looked_up = []

    def _by_name(name):
        looked_up.append(name)
        if name == "AnKingOverhaul (AnKing Step Deck / AnKingMed)":
            return None
        return {"name": name}

    col.models.by_name.side_effect = _by_name
    mock_mw.col = col

    cards = [{
        "card_type": "cloze",
        "text": "Metoprolol is {{c1::beta-1 selective}}.",
        "back_extra": "",
        "tags": ["pharmacology"],
        "deck": "Medical::AI Generated",
    }]

    added, errors = anki_bridge.add_cards_to_collection(cards)

    assert added == 1
    assert errors == []
    assert looked_up[:2] == [
        "AnKingOverhaul (AnKing Step Deck / AnKingMed)",
        "Cloze",
    ]


@patch.object(anki_bridge, "mw", new_callable=MagicMock)
def test_basic_images_remain_on_back_field(mock_mw):
    col = _mock_collection()
    added_notes = []

    def _capture(note, _deck_id):
        added_notes.append(note)
        return 1

    col.add_note.side_effect = _capture
    mock_mw.col = col

    cards = [{
        "card_type": "basic",
        "front": "What is metoprolol?",
        "back": "A beta-1 selective blocker.",
        "tags": ["pharmacology"],
        "deck": "Medical::AI Generated",
        "images": [b"png-bytes"],
    }]

    added, errors = anki_bridge.add_cards_to_collection(cards)

    assert added == 1
    assert errors == []
    assert added_notes[0].fields[0] == cards[0]["front"]
    assert cards[0]["back"] in added_notes[0].fields[1]
    assert "<img " in added_notes[0].fields[1]


@patch.object(anki_bridge, "mw", new_callable=MagicMock)
def test_basic_reversed_uses_reversed_notetype(mock_mw):
    col = _mock_collection()
    notetype_lookups = []

    original_by_name = col.models.by_name.side_effect

    def _track_by_name(name):
        notetype_lookups.append(name)
        return original_by_name(name)

    col.models.by_name.side_effect = _track_by_name
    added_notes = []

    def _capture(note, _deck_id):
        added_notes.append(note)
        return 1

    col.add_note.side_effect = _capture
    mock_mw.col = col

    cards = [{
        "card_type": "basic_reversed",
        "front": "Metoprolol",
        "back": "Beta-1 selective adrenergic blocker",
        "tags": ["pharmacology", "cardiovascular"],
        "deck": "Medical::AI Generated",
    }]

    added, errors = anki_bridge.add_cards_to_collection(cards)

    assert added == 1
    assert errors == []
    assert "Basic (and reversed card)" in notetype_lookups
    assert added_notes[0].fields[0] == cards[0]["front"]
    assert added_notes[0].fields[1] == cards[0]["back"]


@patch.object(anki_bridge, "mw", new_callable=MagicMock)
def test_missing_notetype_skips_card_not_batch(mock_mw):
    col = _mock_collection()

    def _by_name_with_missing(name):
        if name == "Basic (and reversed card)":
            return None
        return {"name": name}

    col.models.by_name.side_effect = _by_name_with_missing
    added_notes = []

    def _capture(note, _deck_id):
        added_notes.append(note)
        return 1

    col.add_note.side_effect = _capture
    mock_mw.col = col

    cards = [
        {
            "card_type": "basic",
            "front": "What is metoprolol?",
            "back": "A beta-1 selective blocker.",
            "tags": ["pharmacology"],
            "deck": "Medical::AI Generated",
        },
        {
            "card_type": "basic_reversed",
            "front": "Metoprolol",
            "back": "Beta-1 selective adrenergic blocker",
            "tags": ["pharmacology"],
            "deck": "Medical::AI Generated",
        },
    ]

    added, errors = anki_bridge.add_cards_to_collection(cards)

    assert added == 1
    assert len(errors) == 1
    assert "Basic (and reversed card)" in errors[0]
