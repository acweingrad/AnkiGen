import re

from ..config import DEFAULT_DECK

SYSTEM_PROMPT = """You are a medical education specialist creating Anki flashcards for medical students. Follow every rule below exactly.

ACCURACY REQUIREMENTS:
- Every fact must reflect current standard-of-care knowledge (Harrison's, Robbins, Goodman & Gilman, First Aid for USMLE, Gray's Anatomy, UpToDate).
- If you are uncertain about any fact, omit that card entirely. Do not guess or extrapolate.
- Do not fabricate drug names, mechanisms, doses, or anatomical relationships.
- Drug doses: include only if unambiguous and universally standard (e.g. aspirin 81 mg for antiplatelet). Omit doses that vary by indication or patient weight.
- Mnemonics: mark all mnemonics explicitly with "[Mnemonic]" — never present a mnemonic as a clinical fact.

TESTABILITY — WHAT TO CARD:
Only generate cards for facts a USMLE question writer would put on an exam. High-yield categories:
- Mechanism of action (drug, pathogen virulence factor, pathophysiology step)
- First-line treatment or surgery-vs-medical management decision
- Formal diagnostic criteria (Duke, Jones, Rome IV, DSM-5, Ranson) — card each criterion atomically
- Classic triad/tetrad, pathognomonic sign, buzzword presentation
- Gold-standard or confirmatory diagnostic test
- Pharmacology: class → prototype → MOA → key indication → major ADR → major contraindication
- Anatomy: structure → nerve/vessel supply → clinical correlate of injury
- Pathophysiology chain: trigger → mechanism → end-organ consequence → clinical sign
- "Most common" facts only when unambiguous and First Aid or Pathoma level

Skip: historical context, epidemiological statistics not in First Aid or Pathoma, anecdotes, interesting-but-rare facts, trivial definitions. When in doubt, omit that card entirely.

LECTURE PDF / SLIDE PASTE RULES:
- When the source looks like lecture slides, PDF text extraction, or lecture notes, generate cards only from necessary learning content.
- Prioritize: learning objectives, explicitly explained relationships, named clinical correlations, and "responsible for knowing" material.
- Do not make cards from: disclosures, copyright/admin text, faculty contact info, textbook citations, URLs, slide numbers, figure attributions, isolated image labels, or repeated annotation clutter.
- If the source explicitly says students are not responsible for learning something, do not make cards about that material.
- If the source is dense, noisy, or repetitive, return fewer cards than the requested maximum rather than padding with weak cards.
- For pasted lecture material, mimic AnKing-style notes: one concise cloze fact in the main text field, with optional image/context support in a short extra field.
- Do not create broad summary cards, multi-step lecture recaps, or multi-fact list cards.

REFERENCE DECK STYLE — USE THIS AS THE DEFAULT:
- Match the reference deck's dominant style: cloze-first, short, high-yield, recognition-oriented cards.
- Default to cloze unless a fact is clearly better tested as basic or basic_reversed. In mixed mode, most cards should still be cloze.
- Most cards should be a single sentence or compact sentence fragment, not a paragraph. Keep the visible prompt tight and the answer span short.
- Prefer one atomic relationship per card: disease → defect, image/histology finding → diagnosis, gene → phenotype, organism → association, mechanism → consequence.
- Prefer compressed causal phrasing when it improves memorability (for example, "X causes Y → Z").
- For image-grounded content, write stems that explicitly reference the visual source when appropriate: "The image below...", "The histology below...", "This X-ray...".
- Use back_extra sparingly: a brief qualifier, image label, or one-line clinical pearl. Do not turn back_extra into a mini-lecture.
- Prefer a single cloze deletion. Use multiple cN deletions only when the pieces are tightly linked and awkward to split into separate cards.

CARD TYPE SELECTION:
Choose the type that best fits each fact:
1. cloze — default and preferred card type. Best for concise pathology-style relationships, image identification, sequences, and "A causes B → C" facts.
2. basic_reversed — use when the fact should be tested in BOTH directions (drug ↔ class, disease ↔ pathogen, enzyme ↔ deficiency syndrome). Creates two cards from one note.
3. basic — use for isolated asymmetric Q&A only when cloze would feel forced.

CARD STRUCTURE RULES — BASIC and BASIC_REVERSED (card_type = "basic" or "basic_reversed"):
- Wozniak minimum information: one card = one testable fact. Split if you can make two simpler, still-testable cards.
- Fronts must be specific questions. Bad: "Tell me about beta blockers." Good: "What is the mechanism of action of metoprolol?"
- Backs must be concise (3 sentences or a short list maximum). Avoid prose paragraphs.
- Clinical cards: Presentation → Diagnosis → First-line treatment.
- Pathophysiology cards: mechanism → consequence → clinical manifestation.
- Pharmacology cards: drug class → mechanism → key clinical use → major side effects.
- Anatomy cards: anchor to clinical relevance (nerve injured, movement lost).
- For basic_reversed: both front and back must stand alone as intelligible questions when the card is flipped.

CARD STRUCTURE RULES — CLOZE (card_type = "cloze"):
- Use {{c1::answer}} syntax. Each cN number creates a separate card shown to the student.
- The sentence must be a complete, self-sufficient fact with the blank removed — the reader must know exactly what kind of answer to supply. Bad: "The drug is {{c1::metoprolol}}." Good: "The first-line beta-1 selective blocker for HFrEF is {{c1::metoprolol}}."
- Cloze answers should usually be short noun phrases or short descriptors, not long clauses.
- Use {{c1::answer::hint}} when a short hint reduces ambiguity without giving away the answer.
- One cloze deletion per testable fact. If the request allows multi-cloze notes, use multiple cN numbers in one sentence only when the facts are inseparable. Otherwise keep each note to one distinct cloze number.
- Do not nest cloze deletions.
- If the fact depends on an image, make the stem say so explicitly and set source_image_index to the matching image.
- Use back_extra (optional) for supplementary detail after the answer: mechanism, [Mnemonic], clinical correlate, or a short image label/source cue.
- Keep back_extra brief. Treat it like the AnKing "Extra" field, not a paragraph or lecture transcript.

TAGGING RULES — include all applicable layers:
- Domain (required, one): pharmacology, anatomy, pathophysiology, clinical, microbiology, biochemistry, physiology, immunology
- System (required, one): cardiovascular, respiratory, renal, GI, neuro, MSK, endocrine, heme, immunology, reproductive, dermatology, psychiatry, other
- Step (if clearly scoped): USMLE_Step1, USMLE_Step2
- Source (if clearly covered): Pathoma, Sketchy, FirstAid, BnB, Physeo, Pepper

DECK ROUTING:
- Use the deck name provided by the user.
- If no deck is given, use the hierarchy Medical::<Step>::<System>::<Domain> (e.g. Medical::Step1::Cardiovascular::Pharmacology). Fall back to "Medical::AI Generated" only when step is genuinely ambiguous.

OUTPUT:
- Call the create_flashcards tool. Do not output any text outside the tool call.
- If the input is too vague, ambiguous, or outside medical scope, call the tool with a single card: front="Input unclear", back="Please refine your topic or paste specific text.", tags=["error"], deck="Medical::AI Generated".
"""

DOMAIN_HINTS = {
    "pharmacology": (
        "Focus on mechanism of action, receptor targets, clinical indications, "
        "contraindications, and major adverse effects. Use drug class suffixes "
        "where applicable (e.g. -olol for beta blockers, -pril for ACE inhibitors)."
    ),
    "anatomy": (
        "Focus on structural relationships, nerve/vessel supply, and clinical "
        "correlates (injury patterns, surgical landmarks, dermatomes)."
    ),
    "pathophysiology": (
        "Focus on the causal chain from molecular/cellular dysfunction to "
        "organ-level disease to clinical presentation."
    ),
    "clinical": (
        "Focus on diagnosis (key findings, gold-standard test) and first-line "
        "management per major guidelines (ACC/AHA, IDSA, ACOG, etc.)."
    ),
}


def build_disclaimer_card(deck: str = DEFAULT_DECK) -> dict:
    return {
        "front": "IMPORTANT: Verify AI-generated cards",
        "back": (
            "These cards were generated by an AI model. "
            "Always verify medical facts against authoritative sources "
            "(First Aid, Harrison's, UpToDate) before relying on them clinically. "
            "AI can make errors — especially for doses, rare diseases, and recent guideline changes."
        ),
        "tags": ["disclaimer", "AI_generated"],
        "deck": deck or DEFAULT_DECK,
    }


DISCLAIMER_CARD = build_disclaimer_card()

_PDF_NOISE_PATTERNS = (
    re.compile(r"^(cmsru )?disclosure\b", re.IGNORECASE),
    re.compile(r"\bno relevant commercial relationships\b", re.IGNORECASE),
    re.compile(r"\bno commercial support\b", re.IGNORECASE),
    re.compile(r"\bcopyright\b|\ball rights reserved\b|\bused with permission\b|\btitle 17\b", re.IGNORECASE),
    re.compile(r"\binstructional materials contained\b|\bplease do not reproduce\b|\bphotocopies or other reproductions\b", re.IGNORECASE),
    re.compile(r"^(https?://|www\.)", re.IGNORECASE),
    re.compile(r"\busername:\b|\bpassword:\b|\blogin information\b|\bviewer installer\b", re.IGNORECASE),
    re.compile(r"\bemail:\b|\boffice phone\b|\boffice:\b|\broom number\b", re.IGNORECASE),
    re.compile(r"\belectronic reference textbooks\b|\breference reading:\b", re.IGNORECASE),
    re.compile(r"^prepared by\b", re.IGNORECASE),
)

_REFERENCE_LINE_PATTERNS = (
    re.compile(r"^(atlas of anatomy|gray'?s anatomy|grays anatomy|junqueira|netter|robbins|wheater|histology:)", re.IGNORECASE),
    re.compile(r"\b\d+(st|nd|rd|th)\s+ed\.?\b", re.IGNORECASE),
    re.compile(r"\bedition\b", re.IGNORECASE),
    re.compile(r"\bvolume\s+\d+\b|\bissue\s+\d+\b", re.IGNORECASE),
)


def _card_type_instruction(card_type: str) -> str:
    if card_type == "basic":
        return 'Generate BASIC cards only (card_type="basic", with front and back fields).'
    if card_type == "cloze":
        return 'Generate CLOZE cards only (card_type="cloze", with text and optional back_extra fields).'
    return (
        "Generate a cloze-heavy mix of BASIC, CLOZE, and BASIC_REVERSED cards as the content warrants. "
        "Default to cloze for sentence-level relationships and pathology-style recognition facts; "
        "use basic_reversed for bidirectional facts (drug ↔ class, disease ↔ pathogen, "
        "enzyme ↔ deficiency); use basic for isolated Q&A only when cloze would feel forced."
    )


def _cloze_mode_instruction(card_type: str, cloze_mode: str) -> str:
    if card_type == "basic":
        return ""
    if cloze_mode == "single":
        return (
            "Cloze mode: SINGLE only. Every cloze note must use exactly one distinct cloze number. "
            "Do not combine multiple cN deletions in the same note."
        )
    return (
        "Cloze mode: MULTI allowed. Prefer a single cloze note when it keeps the fact atomic, "
        "but use multiple distinct cN deletions in one note when the blanks are tightly linked."
    )


def _anking_cloze_guidance(cloze_mode: str) -> str:
    if cloze_mode == "single":
        return "- Use exactly one cloze number per note.\n"
    return "- Prefer a single cloze number, but use multiple when the blanks are inseparable.\n"


def build_messages(prompt_data: dict) -> list:
    if prompt_data["mode"] == "topic":
        user_content = _build_topic_message(prompt_data)
    else:
        user_content = _build_paste_message(prompt_data)
    return [{"role": "user", "content": user_content}]


def _prepare_pasted_text(text: str) -> str:
    text = (text or "").replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned_lines = []
    previous_line = None

    for raw_line in text.split("\n"):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue

        line = re.sub(r"^\d+(?=[A-Z])", "", line).strip()
        if not line or re.fullmatch(r"\d+", line):
            continue

        if any(pattern.search(line) for pattern in _PDF_NOISE_PATTERNS):
            continue

        if any(pattern.search(line) for pattern in _REFERENCE_LINE_PATTERNS):
            continue

        if line == previous_line:
            continue

        cleaned_lines.append(line)
        previous_line = line

    return "\n".join(cleaned_lines)


def _build_topic_message(data: dict) -> str:
    hint = ""
    if data.get("domain_hints") and data.get("domain") and data["domain"] in DOMAIN_HINTS:
        hint = f"\n\nDomain guidance: {DOMAIN_HINTS[data['domain']]}"
    type_instruction = _card_type_instruction(data.get("card_type", "mixed"))
    cloze_instruction = _cloze_mode_instruction(
        data.get("card_type", "mixed"),
        data.get("cloze_mode", "multi"),
    )
    return (
        f"{type_instruction}\n\n"
        + (f"{cloze_instruction}\n\n" if cloze_instruction else "")
        + f"Generate {data['n_cards']} high-quality Anki flashcards on the medical topic: "
        + f'"{data["topic"]}".{hint}\n\n'
        + f"Target deck: {data['deck']}"
    )


def _build_paste_message(data: dict):
    import base64

    text = _prepare_pasted_text(data.get("text", ""))
    truncated = ""
    if len(text) > 12000:
        text = text[:12000]
        truncated = "\n\n[Note: Input was truncated to 12,000 characters.]"

    type_instruction = _card_type_instruction(data.get("card_type", "mixed"))
    cloze_instruction = _cloze_mode_instruction(
        data.get("card_type", "mixed"),
        data.get("cloze_mode", "multi"),
    )
    cloze_guidance = _anking_cloze_guidance(data.get("cloze_mode", "multi"))
    images = data.get("images", [])
    if not images:
        return (
            f"{type_instruction}\n\n"
            + (f"{cloze_instruction}\n\n" if cloze_instruction else "")
            + f"Generate up to {data['n_cards']} Anki flashcards from the following medical text. "
            "Extract only the necessary high-yield facts. It is correct to return fewer cards if the source "
            "does not support more strong cards. Ignore admin/citation/PDF extraction noise and do not invent "
            "facts not present in the text.\n\n"
            "Target the AnKingOverhaul cloze style:\n"
            "- Put one concise cloze fact in the main text.\n"
            "- Use back_extra only for a short pearl or image cue.\n"
            f"{cloze_guidance}"
            "- Do not create basic cards for this pasted material unless cloze is clearly impossible.\n\n"
            f"Target deck: {data['deck']}\n\n"
            f"--- BEGIN TEXT ---\n{text}\n--- END TEXT ---{truncated}"
        )

    text_block = (
        f"{type_instruction}\n\n"
        + (f"{cloze_instruction}\n\n" if cloze_instruction else "")
        + f"Generate up to {data['n_cards']} Anki flashcards from the following medical slide image(s)"
        + (" and text" if text.strip() else "")
        + ". Extract only the necessary high-yield facts. It is correct to return fewer cards if the source "
          "does not support more strong cards. Ignore admin/citation/PDF extraction noise and do not invent "
          "facts not present in the provided content.\n\n"
        "Target the AnKingOverhaul cloze style:\n"
        "- Put one concise cloze fact in the main text.\n"
        "- Use back_extra only for a short pearl or image cue.\n"
        f"{cloze_guidance}"
        "- Do not create basic cards for this pasted material unless cloze is clearly impossible.\n\n"
        f"There are {len(images)} image(s) provided (index 0 through {len(images) - 1}). "
        "For each card, set source_image_index to the 0-based index of the image the card's content "
        "primarily comes from. Omit source_image_index if the card is not clearly tied to one image.\n\n"
        f"Target deck: {data['deck']}"
        + (f"\n\n--- BEGIN TEXT ---\n{text}\n--- END TEXT ---{truncated}" if text.strip() else "")
    )

    content = []
    for png_bytes in images:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.standard_b64encode(png_bytes).decode("ascii"),
                },
            }
        )
    content.append({"type": "text", "text": text_block})
    return content
