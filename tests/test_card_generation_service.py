import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.services.card_generation import CardGenerationService


class _StubProvider:
    key = "stub"

    def __init__(self, cards):
        self.cards = cards

    def generate_cards(self, prompt_data: dict, config: dict) -> list:
        return list(self.cards)


class _SequenceProvider:
    key = "sequence"

    def __init__(self, batches):
        self.batches = list(batches)
        self.calls = []

    def generate_cards(self, prompt_data: dict, config: dict) -> list:
        self.calls.append(dict(prompt_data))
        if not self.batches:
            return []
        return list(self.batches.pop(0))


def test_service_attaches_images_before_disclaimer(monkeypatch):
    service = CardGenerationService(
        {
            "provider": "stub",
            "provider_api_keys": {},
            "auto_add_disclaimer_card": True,
        }
    )
    stub_provider = _StubProvider(
        [
            {
                "card_type": "basic",
                "front": "Q",
                "back": "A",
                "tags": [],
                "deck": "Medical::AI Generated",
            }
        ]
    )
    monkeypatch.setattr("core.services.card_generation.require_provider", lambda _name: stub_provider)

    cards, warnings = service.generate_cards(
        {
            "mode": "paste",
            "text": "",
            "images": [b"png"],
            "card_type": "mixed",
            "domain": None,
            "deck": "Custom::Deck",
            "n_cards": 1,
            "domain_hints": True,
        }
    )

    assert warnings == []
    assert cards[0]["images"] == [b"png"]
    assert cards[1]["deck"] == "Custom::Deck"
    assert "images" not in cards[1]


def test_service_caps_generated_cards_to_requested_count(monkeypatch):
    service = CardGenerationService(
        {
            "provider": "stub",
            "provider_api_keys": {},
            "auto_add_disclaimer_card": False,
        }
    )
    stub_provider = _StubProvider(
        [
            {"card_type": "basic", "front": "Q1", "back": "A1", "tags": [], "deck": "Medical::AI Generated"},
            {"card_type": "basic", "front": "Q2", "back": "A2", "tags": [], "deck": "Medical::AI Generated"},
            {"card_type": "basic", "front": "Q3", "back": "A3", "tags": [], "deck": "Medical::AI Generated"},
        ]
    )
    monkeypatch.setattr("core.services.card_generation.require_provider", lambda _name: stub_provider)

    cards, warnings = service.generate_cards(
        {
            "mode": "paste",
            "text": "source",
            "images": [],
            "card_type": "mixed",
            "domain": None,
            "deck": "Custom::Deck",
            "n_cards": 2,
            "domain_hints": True,
        }
    )

    assert [card["front"] for card in cards] == ["Q1", "Q2"]
    assert warnings == ["Returned 3 cards; capped at requested 2"]


def test_service_retries_short_generation_until_requested_count(monkeypatch):
    service = CardGenerationService(
        {
            "provider": "sequence",
            "provider_api_keys": {},
            "auto_add_disclaimer_card": False,
        }
    )
    provider = _SequenceProvider(
        [
            [
                {"card_type": "basic", "front": "Q1", "back": "A1", "tags": [], "deck": "Medical::AI Generated"},
            ],
            [
                {"card_type": "basic", "front": "Q2", "back": "A2", "tags": [], "deck": "Medical::AI Generated"},
                {"card_type": "basic", "front": "Q3", "back": "A3", "tags": [], "deck": "Medical::AI Generated"},
            ],
        ]
    )
    monkeypatch.setattr("core.services.card_generation.require_provider", lambda _name: provider)

    cards, warnings = service.generate_cards(
        {
            "mode": "topic",
            "topic": "beta blockers",
            "images": [],
            "card_type": "basic",
            "cloze_mode": "multi",
            "domain": None,
            "deck": "Custom::Deck",
            "n_cards": 3,
            "domain_hints": True,
        }
    )

    assert [card["front"] for card in cards] == ["Q1", "Q2", "Q3"]
    assert warnings == []
    assert len(provider.calls) == 2
    assert provider.calls[1]["n_cards"] == 2
    assert "do not duplicate" in provider.calls[1]["retry_instructions"]
    assert "Q1 -> A1" in provider.calls[1]["retry_instructions"]


def test_service_retries_empty_first_batch_then_returns_requested_count(monkeypatch):
    service = CardGenerationService(
        {
            "provider": "sequence",
            "provider_api_keys": {},
            "auto_add_disclaimer_card": False,
        }
    )
    provider = _SequenceProvider(
        [
            [],
            [
                {"card_type": "basic", "front": "Q1", "back": "A1", "tags": [], "deck": "Medical::AI Generated"},
                {"card_type": "basic", "front": "Q2", "back": "A2", "tags": [], "deck": "Medical::AI Generated"},
            ],
        ]
    )
    monkeypatch.setattr("core.services.card_generation.require_provider", lambda _name: provider)

    cards, warnings = service.generate_cards(
        {
            "mode": "topic",
            "topic": "beta blockers",
            "images": [],
            "card_type": "basic",
            "cloze_mode": "multi",
            "domain": None,
            "deck": "Custom::Deck",
            "n_cards": 2,
            "domain_hints": True,
        }
    )

    assert [card["front"] for card in cards] == ["Q1", "Q2"]
    assert warnings == ["Attempt 1: provider returned 0 cards"]
    assert len(provider.calls) == 2
    assert provider.calls[1]["n_cards"] == 2


def test_service_raises_when_retries_still_under_requested_count(monkeypatch):
    service = CardGenerationService(
        {
            "provider": "sequence",
            "provider_api_keys": {},
            "auto_add_disclaimer_card": False,
        }
    )
    provider = _SequenceProvider(
        [
            [
                {"card_type": "basic", "front": "Q1", "back": "A1", "tags": [], "deck": "Medical::AI Generated"},
            ],
            [],
            [],
        ]
    )
    monkeypatch.setattr("core.services.card_generation.require_provider", lambda _name: provider)

    with pytest.raises(RuntimeError) as exc:
        service.generate_cards(
            {
                "mode": "topic",
                "topic": "beta blockers",
                "images": [],
                "card_type": "basic",
                "cloze_mode": "multi",
                "domain": None,
                "deck": "Custom::Deck",
                "n_cards": 3,
                "domain_hints": True,
            }
        )

    assert "returned 1 usable cards, but 3 were requested" in str(exc.value)
    assert len(provider.calls) == 3


def test_service_does_not_count_duplicate_retry_cards(monkeypatch):
    service = CardGenerationService(
        {
            "provider": "sequence",
            "provider_api_keys": {},
            "auto_add_disclaimer_card": False,
        }
    )
    provider = _SequenceProvider(
        [
            [
                {"card_type": "basic", "front": "Q1", "back": "A1", "tags": [], "deck": "Medical::AI Generated"},
            ],
            [
                {"card_type": "basic", "front": "Q1", "back": "A1", "tags": [], "deck": "Medical::AI Generated"},
                {"card_type": "basic", "front": "Q2", "back": "A2", "tags": [], "deck": "Medical::AI Generated"},
            ],
        ]
    )
    monkeypatch.setattr("core.services.card_generation.require_provider", lambda _name: provider)

    cards, warnings = service.generate_cards(
        {
            "mode": "topic",
            "topic": "beta blockers",
            "images": [],
            "card_type": "basic",
            "cloze_mode": "multi",
            "domain": None,
            "deck": "Custom::Deck",
            "n_cards": 2,
            "domain_hints": True,
        }
    )

    assert [card["front"] for card in cards] == ["Q1", "Q2"]
    assert warnings == ["Duplicate generated card skipped"]


def test_service_enforces_single_cloze_mode(monkeypatch):
    service = CardGenerationService(
        {
            "provider": "stub",
            "provider_api_keys": {},
            "auto_add_disclaimer_card": False,
        }
    )
    stub_provider = _StubProvider(
        [
            {
                "card_type": "cloze",
                "text": "{{c1::Metoprolol}} is a {{c2::beta-1}} blocker.",
                "back_extra": "",
                "tags": [],
                "deck": "Medical::AI Generated",
            }
        ]
    )
    monkeypatch.setattr("core.services.card_generation.require_provider", lambda _name: stub_provider)

    with pytest.raises(RuntimeError) as exc:
        service.generate_cards(
            {
                "mode": "paste",
                "text": "source",
                "images": [],
                "card_type": "cloze",
                "cloze_mode": "single",
                "domain": None,
                "deck": "Custom::Deck",
                "n_cards": 1,
                "domain_hints": True,
            }
        )

    assert "none were usable" in str(exc.value)
    assert "too many distinct deletions" in str(exc.value)


def test_service_raises_when_provider_returns_no_cards(monkeypatch):
    service = CardGenerationService(
        {
            "provider": "stub",
            "provider_api_keys": {},
            "auto_add_disclaimer_card": False,
        }
    )
    stub_provider = _StubProvider([])
    monkeypatch.setattr("core.services.card_generation.require_provider", lambda _name: stub_provider)

    with pytest.raises(RuntimeError) as exc:
        service.generate_cards(
            {
                "mode": "topic",
                "topic": "beta blockers",
                "images": [],
                "card_type": "mixed",
                "cloze_mode": "multi",
                "domain": None,
                "deck": "Custom::Deck",
                "n_cards": 10,
                "domain_hints": True,
            }
        )

    assert "returned 0 cards" in str(exc.value)
