from typing import Optional

DEFAULT_DECK = "Medical::AI Generated"
DEFAULT_PROVIDER = "anthropic"

DEFAULT_MODEL_BY_PROVIDER = {
    "anthropic": "claude-sonnet-4-20250514",
}

DEPRECATED_MODEL_REPLACEMENTS = {
    "claude-sonnet-4-6": DEFAULT_MODEL_BY_PROVIDER["anthropic"],
}

PROVIDER_LABELS = {
    "anthropic": "Anthropic",
}

PROVIDER_API_KEY_PLACEHOLDERS = {
    "anthropic": "sk-ant-...",
}

CONFIG_DEFAULTS = {
    "api_key": "",
    "provider": DEFAULT_PROVIDER,
    "model": DEFAULT_MODEL_BY_PROVIDER[DEFAULT_PROVIDER],
    "provider_api_keys": {},
    "default_deck": DEFAULT_DECK,
    "cards_per_topic": 10,
    "temperature": 0,
    "max_tokens": 4096,
    "auto_add_disclaimer_card": True,
    "domain_hints": True,
}


def normalize_config(config: Optional[dict]) -> dict:
    normalized = dict(CONFIG_DEFAULTS)
    if config:
        normalized.update(config)

    provider = str(normalized.get("provider") or DEFAULT_PROVIDER).strip() or DEFAULT_PROVIDER
    provider_api_keys = normalized.get("provider_api_keys")
    if not isinstance(provider_api_keys, dict):
        provider_api_keys = {}

    clean_keys = {}
    for key, value in provider_api_keys.items():
        clean_key = str(key).strip()
        if clean_key:
            clean_keys[clean_key] = str(value or "").strip()

    legacy_api_key = str(normalized.get("api_key") or "").strip()
    if legacy_api_key and not clean_keys.get("anthropic"):
        clean_keys["anthropic"] = legacy_api_key

    model = str(normalized.get("model") or "").strip()
    if model in DEPRECATED_MODEL_REPLACEMENTS:
        model = DEPRECATED_MODEL_REPLACEMENTS[model]
    if not model:
        model = DEFAULT_MODEL_BY_PROVIDER.get(provider, "")

    normalized["provider"] = provider
    normalized["model"] = model
    normalized["provider_api_keys"] = clean_keys
    normalized["api_key"] = clean_keys.get("anthropic", legacy_api_key)
    normalized["default_deck"] = str(normalized.get("default_deck") or DEFAULT_DECK).strip() or DEFAULT_DECK
    return normalized


def get_provider_api_key(config: Optional[dict], provider: Optional[str] = None) -> str:
    normalized = normalize_config(config)
    target = provider or normalized["provider"]
    return str(normalized["provider_api_keys"].get(target) or "").strip()


def set_provider_api_key(config: Optional[dict], provider: str, api_key: str) -> dict:
    normalized = normalize_config(config)
    keys = dict(normalized["provider_api_keys"])
    clean_key = str(api_key or "").strip()
    if clean_key:
        keys[provider] = clean_key
    else:
        keys.pop(provider, None)
    normalized["provider_api_keys"] = keys
    if provider == "anthropic":
        normalized["api_key"] = clean_key
    return normalized


def has_provider_credentials(config: Optional[dict], provider: Optional[str] = None) -> bool:
    return bool(get_provider_api_key(config, provider))


def get_provider_label(provider: str) -> str:
    return PROVIDER_LABELS.get(provider, provider.title())


def get_provider_api_key_placeholder(provider: str) -> str:
    return PROVIDER_API_KEY_PLACEHOLDERS.get(provider, "")


def get_provider_choices() -> list[tuple[str, str]]:
    return [(key, get_provider_label(key)) for key in PROVIDER_LABELS]
