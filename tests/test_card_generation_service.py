import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.services.card_generation import CardGenerationService


class _StubProvider:
    key = "stub"

    def __init__(self, cards):
        self.cards = cards

    def generate_cards(self, prompt_data: dict, config: dict) -> list:
        return list(self.cards)


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
