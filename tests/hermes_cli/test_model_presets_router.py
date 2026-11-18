"""Provider presets endpoint (ADR-001): authorized pair, non-secret block, idempotent apply."""

import pytest
from fastapi import HTTPException


def _catalogue():
    from hermes_cli.web_routers import model_presets as mp

    return {row["id"]: row for row in mp.list_model_presets()["presets"]}


def test_catalogue_carries_the_adr_001_authorized_pair():
    rows = _catalogue()
    assert rows["deepseek"]["authorized_models"] == ["deepseek-v4-pro", "deepseek-flash"]
    assert rows["zai"]["authorized_models"] == ["glm-5.3", "glm-5.3-flash"]
    assert rows["deepseek"]["key_env"] == "DEEPSEEK_API_KEY"
    assert rows["zai"]["key_env"] == "GLM_API_KEY"
    # Fresh temp home: no .env, so the key must not read as present.
    assert rows["deepseek"]["key_present"] is False
    assert rows["zai"]["applied"] is False


def test_apply_writes_only_the_non_secret_provider_block():
    from hermes_cli.config import load_config, save_config
    from hermes_cli.web_routers import model_presets as mp

    save_config({"model": {"default": "local-model", "provider": "custom",
                           "base_url": "http://127.0.0.1:11434/v1"}})
    result = mp.apply_model_preset("zai")
    assert result["models"] == ["glm-5.3", "glm-5.3-flash"]

    block = load_config()["providers"]["zai"]
    assert block == {"key_env": "GLM_API_KEY", "models": ["glm-5.3", "glm-5.3-flash"]}
    assert "api_key" not in block  # a credential in config.yaml would fail the sovereignty audit


def test_apply_is_idempotent_and_preserves_user_extras():
    from hermes_cli.config import load_config, save_config
    from hermes_cli.web_routers import model_presets as mp

    save_config({"providers": {"zai": {"extra_body": {"x": 1}},
                               "local": {"api": "http://127.0.0.1:1/v1"}}})
    assert mp.apply_model_preset("zai")["changed"] is True
    assert mp.apply_model_preset("zai")["changed"] is False

    providers = load_config()["providers"]
    assert providers["zai"]["extra_body"] == {"x": 1}          # user extra kept
    assert providers["zai"]["models"] == ["glm-5.3", "glm-5.3-flash"]
    assert providers["local"]["api"] == "http://127.0.0.1:1/v1"  # unrelated provider kept


def test_applied_flag_tracks_the_allowlist():
    from hermes_cli.web_routers import model_presets as mp

    assert _catalogue()["deepseek"]["applied"] is False
    mp.apply_model_preset("deepseek")
    assert _catalogue()["deepseek"]["applied"] is True


def test_unknown_preset_is_404():
    from hermes_cli.web_routers import model_presets as mp

    with pytest.raises(HTTPException) as excinfo:
        mp.apply_model_preset("openai")
    assert excinfo.value.status_code == 404
