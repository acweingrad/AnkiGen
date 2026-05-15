# Architecture

The add-on is now split around extension boundaries instead of provider-specific files:

- `core/services/`: orchestration for card generation workflows.
- `core/providers/`: model-provider adapters such as Anthropic.
- `core/card_types/`: registry-backed card-type handlers that normalize payloads and populate Anki notes.
- `core/prompts/`: shared prompt policy and provider-facing prompt builders.
- `ui/`: Qt dialogs and widgets only.

## Current Flow

1. `ui/main_dialog.py` collects prompt data.
2. `core/services/card_generation.py` resolves the active provider and runs generation.
3. `core/card_parser.py` validates output through the card type registry.
4. `core/anki_bridge.py` writes reviewed cards into Anki by asking the same registry how each card maps to a note type.

## Why This Scales Better

- Adding a new model provider no longer requires editing the dialog or card-validation logic.
- Adding a new card type no longer requires hardcoding rules in both parsing and Anki note creation.
- Backward-compatible shims remain in `core/api_client.py`, `core/prompt_builder.py`, `core/card_parser.py`, and `core/anki_bridge.py` so the current test surface stays stable while internals evolve.

## Next Extension Hooks

- Register providers in `core/providers/registry.py`.
- Register built-in or third-party card types in `core/card_types/registry.py`.
- Keep provider-specific request formatting inside provider adapters rather than the UI layer.
