# Medical Flashcard Generator — Configuration

**provider**: Active model provider. Default: `anthropic`. The codebase is now structured so additional providers can be added without rewiring the UI or generation flow.

**model**: Model identifier passed to the active provider. Default: `claude-sonnet-4-6`.

**provider_api_keys**: Mapping of provider slug to API key. Example: `{"anthropic": "sk-ant-..."}`. Stored in plaintext on disk — do not share this file or the add-ons folder.

**api_key**: Legacy Anthropic API key field retained for backward compatibility. New code normalizes it into `provider_api_keys.anthropic`.

**default_deck**: Deck name for generated cards. Use `::` for subdecks (e.g. `Medicine::Pharmacology`). The deck is created automatically if it does not exist.

**cards_per_topic**: Number of cards to request when using Topic mode. Default: 10. Maximum recommended: 100.

**temperature**: API sampling temperature. `0` = deterministic, most accurate output. Do not raise above `0.3` for medical content — higher values increase the chance of hallucination.

**max_tokens**: Maximum tokens in each API response. Large requests are split into 10-card API calls to reduce truncation risk. Increase only if you see truncated output for individual batches.

**auto_add_disclaimer_card**: If `true`, appends a reminder card to every generated batch instructing the user to verify content against authoritative sources.

**domain_hints**: If `true`, includes domain-specific sub-instructions in the prompt (e.g. pharmacology cards get extra guidance on mechanism/side-effect structure). Recommended to leave enabled.

## Extension Points

Provider integrations live under `core/providers/`.

Card type integrations live under `core/card_types/`.

The generation pipeline entrypoint is `core/services/card_generation.py`.
