import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.prompt_builder import PASTE_TEXT_CHAR_LIMIT, build_messages, SYSTEM_PROMPT


def _topic_data(**kwargs):
    base = {
        "mode": "topic",
        "topic": "beta blockers",
        "text": "",
        "card_type": "mixed",
        "cloze_mode": "multi",
        "domain": None,
        "deck": "Medical::AI Generated",
        "n_cards": 10,
        "domain_hints": True,
    }
    base.update(kwargs)
    return base


def _paste_data(**kwargs):
    base = {
        "mode": "paste",
        "topic": "",
        "text": "Beta blockers block beta-1 adrenergic receptors.",
        "card_type": "mixed",
        "cloze_mode": "multi",
        "domain": None,
        "deck": "Medical::AI Generated",
        "n_cards": 10,
        "domain_hints": True,
    }
    base.update(kwargs)
    return base


def test_topic_mode_includes_topic_name():
    messages = build_messages(_topic_data(topic="ACE inhibitors"))
    assert "ACE inhibitors" in messages[0]["content"]


def test_topic_mode_includes_n_cards():
    messages = build_messages(_topic_data(n_cards=7))
    assert "7" in messages[0]["content"]


def test_topic_mode_domain_hint_appended_when_enabled():
    messages = build_messages(_topic_data(domain="pharmacology", domain_hints=True))
    assert "mechanism of action" in messages[0]["content"]


def test_topic_mode_domain_hint_absent_when_disabled():
    messages = build_messages(_topic_data(domain="pharmacology", domain_hints=False))
    assert "Domain guidance" not in messages[0]["content"]


def test_topic_mode_no_hint_for_none_domain():
    messages = build_messages(_topic_data(domain=None, domain_hints=True))
    assert "Domain guidance" not in messages[0]["content"]


def test_paste_mode_includes_text():
    messages = build_messages(_paste_data(text="Metoprolol is a beta-1 selective blocker."))
    assert "Metoprolol" in messages[0]["content"]


def test_paste_mode_grounding_instruction_present():
    messages = build_messages(_paste_data())
    assert "do not invent facts not present in the text" in messages[0]["content"].lower()


def test_paste_mode_mentions_requested_card_limit():
    messages = build_messages(_paste_data(n_cards=7))
    assert "Generate exactly 7 Anki flashcards" in messages[0]["content"]


def test_retry_instructions_are_appended_to_topic_prompt():
    messages = build_messages(_topic_data(n_cards=2, retry_instructions="Return two new facts."))
    assert "Retry instructions: Return two new facts." in messages[0]["content"]


def test_paste_mode_filters_common_pdf_noise_but_keeps_scope_signals():
    text = "\n".join(
        [
            "CMSRU Disclosure",
            "There is no commercial support for this program.",
            "Atlas of Anatomy, 3rd ed.",
            "Office phone number: 856-361-2889",
            "https://example.com/reference",
            "Learning Objectives",
            "Achilles tendon rupture causes inability to perform a heel raise.",
            "You are not responsible for learning the names of these muscles.",
        ]
    )
    messages = build_messages(_paste_data(text=text))
    content = messages[0]["content"]
    assert "commercial support" not in content
    assert "Atlas of Anatomy" not in content
    assert "Office phone number" not in content
    assert "https://example.com/reference" not in content
    assert "Learning Objectives" in content
    assert "Achilles tendon rupture" in content
    assert "You are not responsible" in content


def test_paste_mode_truncates_at_paste_text_char_limit():
    long_text = "A" * (PASTE_TEXT_CHAR_LIMIT + 3000)
    messages = build_messages(_paste_data(text=long_text))
    content = messages[0]["content"]
    assert "A" * (PASTE_TEXT_CHAR_LIMIT + 1) not in content
    assert "truncated" in content


def test_paste_mode_no_truncation_under_limit():
    text = "A" * (PASTE_TEXT_CHAR_LIMIT - 1)
    messages = build_messages(_paste_data(text=text))
    assert "truncated" not in messages[0]["content"]


def test_system_prompt_contains_accuracy_requirements():
    assert "omit that card entirely" in SYSTEM_PROMPT
    assert "Do not guess" in SYSTEM_PROMPT


def test_system_prompt_contains_mnemonic_rule():
    assert "[Mnemonic]" in SYSTEM_PROMPT


def test_messages_returns_list_with_user_role():
    messages = build_messages(_topic_data())
    assert isinstance(messages, list)
    assert messages[0]["role"] == "user"


def test_topic_mode_basic_only_instruction():
    messages = build_messages(_topic_data(card_type="basic"))
    assert "BASIC" in messages[0]["content"]
    assert "CLOZE" not in messages[0]["content"]


def test_topic_mode_cloze_only_instruction():
    messages = build_messages(_topic_data(card_type="cloze"))
    assert "CLOZE" in messages[0]["content"]
    assert "BASIC" not in messages[0]["content"]


def test_topic_mode_mixed_instruction():
    messages = build_messages(_topic_data(card_type="mixed"))
    content = messages[0]["content"]
    assert "BASIC" in content and "CLOZE" in content


def test_topic_mode_mixed_instruction_mentions_reversed():
    messages = build_messages(_topic_data(card_type="mixed"))
    assert "basic_reversed" in messages[0]["content"].lower() or "REVERSED" in messages[0]["content"]


def test_paste_mode_card_type_instruction_present():
    messages = build_messages(_paste_data(card_type="cloze"))
    assert "CLOZE" in messages[0]["content"]


def test_paste_mode_mentions_anking_style():
    messages = build_messages(_paste_data(card_type="cloze"))
    content = messages[0]["content"]
    assert "AnKingOverhaul" in content
    assert "back_extra only for a short pearl or image cue" in content


def test_topic_mode_single_cloze_instruction_present():
    messages = build_messages(_topic_data(card_type="cloze", cloze_mode="single"))
    content = messages[0]["content"]
    assert "SINGLE only" in content
    assert "exactly one distinct cloze number" in content


def test_paste_mode_multi_cloze_instruction_present():
    messages = build_messages(_paste_data(card_type="cloze", cloze_mode="multi"))
    content = messages[0]["content"]
    assert "MULTI allowed" in content
    assert "use multiple when the blanks are inseparable" in content


def test_system_prompt_contains_cloze_rules():
    from core.prompt_builder import SYSTEM_PROMPT
    assert "{{c1::" in SYSTEM_PROMPT
    assert "back_extra" in SYSTEM_PROMPT


def test_system_prompt_contains_reference_deck_style_rules():
    assert "REFERENCE DECK STYLE" in SYSTEM_PROMPT
    assert "Default to cloze" in SYSTEM_PROMPT
    assert "source_image_index" in SYSTEM_PROMPT


def test_system_prompt_contains_lecture_pdf_rules():
    assert "LECTURE PDF / SLIDE PASTE RULES" in SYSTEM_PROMPT
    assert "Return fewer cards only when" in SYSTEM_PROMPT
    assert "not responsible for learning" in SYSTEM_PROMPT
