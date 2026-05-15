# AnkiGen

Medical Card Generator is an Anki add-on for generating medical flashcards from topics, pasted lecture text, and slide screenshots.

## Repo Scope

This repository is rooted at the add-on folder itself:

`addons21/medical_card_generator/`

Do not version the surrounding Anki profile files.

## Sensitive Files

- `meta.json` is ignored on purpose.
- `meta.json` contains user-specific Anki add-on state and may contain live API keys.
- `config.json` is the safe default config template that ships with the add-on.

## Install In Anki

1. Copy the `medical_card_generator` folder into Anki's `addons21` directory.
2. Restart Anki.
3. Open `Tools -> Generate Medical Cards`.
4. Enter your own API key in the add-on settings.

## Git Workflow

Typical update flow:

```bash
git status
git add .
git commit -m "Describe change"
git pull --rebase origin main
git push
```

## Package For Sharing

Create a clean distributable zip from the repo root:

```bash
python3 scripts/package_addon.py
```

Output goes to:

`dist/medical_card_generator.zip`

To intentionally include the current local API key from `meta.json` for a trusted recipient:

```bash
python3 scripts/package_addon.py --include-local-api-key
```

That mode is opt-in and should only be used when you explicitly want to share your current local key.
