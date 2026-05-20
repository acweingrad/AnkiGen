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


def test_service_returns_partial_cards_when_retries_still_under_requested_count(monkeypatch):
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

    assert [card["front"] for card in cards] == ["Q1"]
    assert "Generated 1 usable cards out of requested 3 after 4 API calls" in warnings
    assert len(provider.calls) == 4


def test_service_batches_large_requested_count(monkeypatch):
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
                {
                    "card_type": "basic",
                    "front": f"Q{batch}_{i}",
                    "back": "A",
                    "tags": [],
                    "deck": "Medical::AI Generated",
                }
                for i in range(10)
            ]
            for batch in range(7)
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
            "n_cards": 70,
            "domain_hints": True,
        }
    )

    assert len(cards) == 70
    assert warnings == []
    assert [call["n_cards"] for call in provider.calls] == [10, 10, 10, 10, 10, 10, 10]
    assert "requested 70 total cards" in provider.calls[1]["retry_instructions"]


def test_service_rebatches_pasted_source_until_requested_count(monkeypatch):
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
            ],
        ]
    )
    monkeypatch.setattr("core.services.card_generation.require_provider", lambda _name: provider)

    cards, warnings = service.generate_cards(
        {
            "mode": "paste",
            "topic": "",
            "text": "long pasted lecture source",
            "images": [],
            "card_type": "cloze",
            "cloze_mode": "multi",
            "domain": None,
            "deck": "Custom::Deck",
            "n_cards": 20,
            "domain_hints": True,
        }
    )

    assert [card["front"] for card in cards] == ["Q1", "Q2"]
    assert len(provider.calls) == 5
    assert [call["n_cards"] for call in provider.calls] == [10, 10, 10, 10, 10]
    assert "do not duplicate" in provider.calls[1]["retry_instructions"]
    assert "Generated 2 usable cards out of requested 20 after 5 API calls" in warnings


def test_service_continues_pasted_source_after_full_default_batch(monkeypatch):
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
                {
                    "card_type": "basic",
                    "front": f"Q1_{i}",
                    "back": "A",
                    "tags": [],
                    "deck": "Medical::AI Generated",
                }
                for i in range(10)
            ],
            [
                {
                    "card_type": "basic",
                    "front": "Q2",
                    "back": "A",
                    "tags": [],
                    "deck": "Medical::AI Generated",
                },
            ],
            [],
            [],
            [],
        ]
    )
    monkeypatch.setattr("core.services.card_generation.require_provider", lambda _name: provider)

    cards, warnings = service.generate_cards(
        {
            "mode": "paste",
            "topic": "",
            "text": "long pasted lecture source",
            "images": [],
            "card_type": "basic",
            "cloze_mode": "multi",
            "domain": None,
            "deck": "Custom::Deck",
            "n_cards": 10,
            "domain_hints": True,
        }
    )

    assert len(cards) == 11
    assert len(provider.calls) == 5
    assert [call["n_cards"] for call in provider.calls] == [10, 10, 10, 10, 10]
    assert "keep going" in provider.calls[1]["retry_instructions"]
    assert "Attempt 5: provider returned 0 cards" in warnings


def test_service_splits_large_slide_sets_into_image_batches(monkeypatch):
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
                {
                    "card_type": "basic",
                    "front": "Slide 1 fact",
                    "back": "A1",
                    "tags": [],
                    "deck": "Medical::AI Generated",
                    "source_image_index": 0,
                },
            ],
            [
                {
                    "card_type": "basic",
                    "front": "Slide 5 fact",
                    "back": "A5",
                    "tags": [],
                    "deck": "Medical::AI Generated",
                    "source_image_index": 0,
                },
            ],
        ]
    )
    monkeypatch.setattr("core.services.card_generation.require_provider", lambda _name: provider)

    cards, warnings = service.generate_cards(
        {
            "mode": "paste",
            "topic": "",
            "text": "",
            "images": [b"slide1", b"slide2", b"slide3", b"slide4", b"slide5"],
            "card_type": "basic",
            "cloze_mode": "multi",
            "domain": None,
            "deck": "Custom::Deck",
            "n_cards": 10,
            "domain_hints": True,
        }
    )

    assert [len(call["images"]) for call in provider.calls[:2]] == [4, 1]
    assert "slide batch 1 of 2" in provider.calls[0]["retry_instructions"]
    assert "slide batch 2 of 2" in provider.calls[1]["retry_instructions"]
    assert [card["front"] for card in cards] == ["Slide 1 fact", "Slide 5 fact"]
    assert cards[0]["images"] == [b"slide1"]
    assert cards[1]["images"] == [b"slide5"]
    assert "Generated 2 usable cards out of requested 10 after 2 API calls" in warnings


def test_service_batches_slides_without_repeating_accepted_facts(monkeypatch):
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
            "mode": "paste",
            "topic": "",
            "text": "",
            "images": [b"1", b"2", b"3", b"4", b"5"],
            "card_type": "basic",
            "cloze_mode": "multi",
            "domain": None,
            "deck": "Custom::Deck",
            "n_cards": 10,
            "domain_hints": True,
        }
    )

    assert [card["front"] for card in cards] == ["Q1", "Q2"]
    assert "Already accepted cards; do not duplicate these facts" in provider.calls[1]["retry_instructions"]
    assert "Q1 -> A1" in provider.calls[1]["retry_instructions"]
    assert "Duplicate generated card skipped" in warnings


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


def test_service_skips_duplicate_cloze_facts_with_different_markup(monkeypatch):
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
                {
                    "card_type": "cloze",
                    "text": "Metoprolol is a {{c1::beta-1 selective::receptor}} blocker.",
                    "back_extra": "",
                    "tags": [],
                    "deck": "Medical::AI Generated",
                },
                {
                    "card_type": "cloze",
                    "text": "Metoprolol is a {{c2::beta-1 selective}} blocker.",
                    "back_extra": "",
                    "tags": [],
                    "deck": "Medical::AI Generated",
                },
                {
                    "card_type": "cloze",
                    "text": "Atenolol is a {{c1::beta-1 selective}} blocker.",
                    "back_extra": "",
                    "tags": [],
                    "deck": "Medical::AI Generated",
                },
            ],
        ]
    )
    monkeypatch.setattr("core.services.card_generation.require_provider", lambda _name: provider)

    cards, warnings = service.generate_cards(
        {
            "mode": "paste",
            "text": "beta blocker notes",
            "images": [],
            "card_type": "cloze",
            "cloze_mode": "multi",
            "domain": None,
            "deck": "Custom::Deck",
            "n_cards": 2,
            "domain_hints": True,
        }
    )

    assert [card["text"] for card in cards] == [
        "Metoprolol is a {{c1::beta-1 selective::receptor}} blocker.",
        "Atenolol is a {{c1::beta-1 selective}} blocker.",
    ]
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
