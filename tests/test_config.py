import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.config import (
    DEFAULT_MODEL_BY_PROVIDER,
    get_provider_api_key,
    has_provider_credentials,
    normalize_config,
    set_provider_api_key,
)


def test_normalize_config_migrates_legacy_anthropic_key():
    config = normalize_config({"api_key": "secret"})
    assert config["provider"] == "anthropic"
    assert config["provider_api_keys"]["anthropic"] == "secret"


def test_normalize_config_sets_default_model_for_provider():
    config = normalize_config({})
    assert config["model"] == DEFAULT_MODEL_BY_PROVIDER["anthropic"]


def test_normalize_config_replaces_deprecated_model():
    config = normalize_config({"model": "claude-sonnet-4-6"})
    assert config["model"] == DEFAULT_MODEL_BY_PROVIDER["anthropic"]


def test_normalize_config_replaces_dated_sonnet_4_model():
    config = normalize_config({"model": "claude-sonnet-4-20250514"})
    assert config["model"] == DEFAULT_MODEL_BY_PROVIDER["anthropic"]


def test_set_provider_api_key_updates_nested_mapping():
    config = set_provider_api_key({}, "anthropic", "secret")
    assert get_provider_api_key(config, "anthropic") == "secret"


def test_has_provider_credentials_uses_normalized_keys():
    assert has_provider_credentials({"provider_api_keys": {"anthropic": "secret"}}) is True
    assert has_provider_credentials({"provider_api_keys": {"anthropic": ""}}) is False
