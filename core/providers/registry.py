from .anthropic import AnthropicProvider

_PROVIDERS = {}


def register_provider(provider) -> None:
    _PROVIDERS[provider.key] = provider


def get_provider(provider_key: str):
    return _PROVIDERS.get(provider_key)


def require_provider(provider_key: str):
    provider = get_provider(provider_key)
    if provider is None:
        raise RuntimeError(f"Unsupported provider '{provider_key}'.")
    return provider


def list_providers() -> list:
    return list(_PROVIDERS.values())


register_provider(AnthropicProvider())
