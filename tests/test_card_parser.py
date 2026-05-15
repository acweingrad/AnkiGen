import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.card_parser import validate_and_clean_cards


def _basic(**kwargs):
    base = {
        "card_type": "basic",
        "front": "What is the mechanism of metoprolol?",
        "back": "Beta-1 selective adrenergic receptor blocker.",
        "tags": ["pharmacology", "cardiovascular"],
        "deck": "Medical::AI Generated",
    }
    base.update(kwargs)
    return base


def _basic_reversed(**kwargs):
    base = {
        "card_type": "basic_reversed",
        "front": "Metoprolol",
        "back": "Beta-1 selective adrenergic blocker",
        "tags": ["pharmacology", "cardiovascular"],
        "deck": "Medical::AI Generated",
    }
    base.update(kwargs)
    return base


def _cloze(**kwargs):
    base = {
        "card_type": "cloze",
        "text": "Metoprolol is a {{c1::beta-1 selective}} adrenergic blocker.",
        "back_extra": "Used for heart failure and hypertension.",
        "tags": ["pharmacology", "cardiovascular"],
        "deck": "Medical::AI Generated",
    }
    base.update(kwargs)
    return base


# ── Basic card tests ──────────────────────────────────────────────────────────

def test_valid_basic_card_passes_through():
    cards, warnings = validate_and_clean_cards([_basic()])
    assert len(cards) == 1
    assert cards[0]["card_type"] == "basic"
    assert not warnings


def test_missing_front_skips_card():
    cards, warnings = validate_and_clean_cards([_basic(front="")])
    assert len(cards) == 0
    assert any("front" in w for w in warnings)


def test_whitespace_only_front_skips_card():
    cards, warnings = validate_and_clean_cards([_basic(front="   ")])
    assert len(cards) == 0


def test_missing_back_skips_card():
    cards, warnings = validate_and_clean_cards([_basic(back="")])
    assert len(cards) == 0
    assert any("back" in w for w in warnings)


def test_basic_fields_are_stripped():
    cards, _ = validate_and_clean_cards([_basic(front="  Q  ", back="  A  ")])
    assert cards[0]["front"] == "Q"
    assert cards[0]["back"] == "A"


def test_multiple_cards_partial_valid():
    raw = [_basic(), _basic(front=""), _basic(back="")]
    cards, warnings = validate_and_clean_cards(raw)
    assert len(cards) == 1
    assert len(warnings) == 2


# ── Cloze card tests ──────────────────────────────────────────────────────────

def test_valid_cloze_card_passes_through():
    cards, warnings = validate_and_clean_cards([_cloze()])
    assert len(cards) == 1
    assert cards[0]["card_type"] == "cloze"
    assert not warnings


def test_cloze_missing_text_skipped():
    cards, warnings = validate_and_clean_cards([_cloze(text="")])
    assert len(cards) == 0
    assert any("text" in w for w in warnings)


def test_cloze_text_without_deletion_skipped():
    cards, warnings = validate_and_clean_cards([_cloze(text="No deletion here.")])
    assert len(cards) == 0
    assert any("deletion" in w for w in warnings)


def test_cloze_back_extra_optional():
    cards, _ = validate_and_clean_cards([_cloze(back_extra="")])
    assert len(cards) == 1
    assert cards[0]["back_extra"] == ""


def test_cloze_back_extra_none_becomes_empty_string():
    cards, _ = validate_and_clean_cards([_cloze(back_extra=None)])
    assert cards[0]["back_extra"] == ""


def test_cloze_text_stripped():
    cards, _ = validate_and_clean_cards([_cloze(text="  {{c1::answer}} text  ")])
    assert not cards[0]["text"].startswith(" ")


def test_cloze_multiple_deletions_valid():
    cards, _ = validate_and_clean_cards([_cloze(
        text="{{c1::Metoprolol}} is a {{c2::beta-1}} blocker."
    )])
    assert len(cards) == 1


def test_cloze_more_than_two_distinct_deletions_skipped():
    cards, warnings = validate_and_clean_cards([_cloze(
        text="{{c1::A}} causes {{c2::B}} which leads to {{c3::C}}."
    )])
    assert len(cards) == 0
    assert any("too many distinct deletions" in w for w in warnings)


def test_single_cloze_mode_rejects_multiple_distinct_deletions():
    cards, warnings = validate_and_clean_cards(
        [_cloze(text="{{c1::Metoprolol}} is a {{c2::beta-1}} blocker.")],
        max_unique_clozes=1,
    )
    assert len(cards) == 0
    assert any("too many distinct deletions" in w for w in warnings)


def test_multi_cloze_mode_allows_more_than_two_distinct_deletions():
    cards, warnings = validate_and_clean_cards(
        [_cloze(text="{{c1::A}} causes {{c2::B}} which leads to {{c3::C}}.")],
        max_unique_clozes=None,
    )
    assert len(cards) == 1
    assert warnings == []


# ── Shared field tests ────────────────────────────────────────────────────────

def test_tags_coerced_from_string_to_list():
    cards, _ = validate_and_clean_cards([_basic(tags="pharmacology")])
    assert isinstance(cards[0]["tags"], list)
    assert "pharmacology" in cards[0]["tags"]


def test_tags_none_becomes_empty_list():
    cards, _ = validate_and_clean_cards([_basic(tags=None)])
    assert cards[0]["tags"] == []


def test_default_deck_assigned_when_missing():
    cards, _ = validate_and_clean_cards([_basic(deck="")])
    assert cards[0]["deck"] == "Medical::AI Generated"


def test_default_deck_assigned_when_whitespace():
    cards, _ = validate_and_clean_cards([_basic(deck="   ")])
    assert cards[0]["deck"] == "Medical::AI Generated"


def test_unknown_card_type_treated_as_basic():
    card = _basic(card_type="unknown")
    cards, warnings = validate_and_clean_cards([card])
    assert cards[0]["card_type"] == "basic"
    assert any("unknown" in w for w in warnings)


def test_non_dict_card_skipped():
    cards, warnings = validate_and_clean_cards(["not a dict"])
    assert len(cards) == 0
    assert warnings


def test_empty_list_returns_empty():
    cards, warnings = validate_and_clean_cards([])
    assert cards == []
    assert warnings == []


def test_mixed_basic_and_cloze():
    raw = [_basic(), _cloze(), _basic(front="")]
    cards, warnings = validate_and_clean_cards(raw)
    assert len(cards) == 2
    assert cards[0]["card_type"] == "basic"
    assert cards[1]["card_type"] == "cloze"
    assert len(warnings) == 1


# ── Basic reversed card tests ─────────────────────────────────────────────────

def test_valid_basic_reversed_card_passes_through():
    cards, warnings = validate_and_clean_cards([_basic_reversed()])
    assert len(cards) == 1
    assert cards[0]["card_type"] == "basic_reversed"
    assert not warnings


def test_basic_reversed_preserves_card_type():
    cards, _ = validate_and_clean_cards([_basic_reversed()])
    assert cards[0]["card_type"] == "basic_reversed"
    assert cards[0]["front"] == "Metoprolol"
    assert cards[0]["back"] == "Beta-1 selective adrenergic blocker"


def test_basic_reversed_missing_front_skipped():
    cards, warnings = validate_and_clean_cards([_basic_reversed(front="")])
    assert len(cards) == 0
    assert any("front" in w for w in warnings)


def test_basic_reversed_missing_back_skipped():
    cards, warnings = validate_and_clean_cards([_basic_reversed(back="")])
    assert len(cards) == 0
    assert any("back" in w for w in warnings)


def test_mixed_all_three_types():
    raw = [_basic(), _cloze(), _basic_reversed()]
    cards, warnings = validate_and_clean_cards(raw)
    assert len(cards) == 3
    assert cards[0]["card_type"] == "basic"
    assert cards[1]["card_type"] == "cloze"
    assert cards[2]["card_type"] == "basic_reversed"
    assert not warnings
