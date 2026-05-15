# Next Phase Plan

## 1. Native Third-Party Card Types

Goal: support note types beyond built-in `Basic`, `Basic (and reversed card)`, and `Cloze` without scattering special cases.

Planned work:

- Define a small registration contract for third-party card types:
  - unique slug
  - target Anki notetype name
  - required generation fields
  - note population callback
- Add a discovery mechanism from config or a local plugin module list.
- Expand the UI so users can choose between built-in-only mode and installed third-party templates.
- Add validation tests for missing notetypes, mismatched fields, and unsupported template versions.

Recommended first targets:

- Image Occlusion
- Custom lecture note types already present in the user collection
- Specialty templates with extra fields such as `Extra`, `Source`, `Sketch`, or `Mnemonic`

## 2. Multi-Provider / Lower-Cost Model Support

Goal: stop assuming Anthropic is the only runtime option and enable cost-aware routing.

Planned work:

- Add provider adapters for at least one cheaper text-first option and one multimodal option.
- Split provider capabilities explicitly:
  - text-only generation
  - multimodal generation
  - tool / structured-output support
- Introduce provider-specific config validation and API-key storage per provider.
- Add a simple routing policy:
  - use cheaper text model for topic generation
  - use multimodal model only when screenshots are pasted
  - allow manual override in settings for debugging

Suggested rollout:

1. Add OpenAI-compatible structured-output provider.
2. Add a low-cost fallback model for topic-only mode.
3. Add per-provider telemetry fields: latency, token usage, estimated cost.

## 3. Hardening Before Feature Expansion

- Add tests around provider selection and unknown-provider failures.
- Add tests for card-type registration collisions and third-party handler loading.
- Add a manual QA checklist for:
  - built-in note types
  - missing note types
  - pasted text
  - pasted screenshots
  - provider switching
