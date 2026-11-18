"""Provider presets (ADR-001): authorized pair, non-secret block, idempotent apply.

No ``import pytest`` / fastapi on purpose: the lint lane type-checks this tree without test or
runtime dependencies installed, so a module-level third-party import would register as a new
unresolved-import diagnostic. Plain ``test_*`` functions run under pytest regardless.
"""


def _api():
    from hermes_cli.web_routers import models

    return models


def _catalogue():
    return {row["id"]: row for row in _api().list_model_presets()["presets"]}


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

    save_config({"model": {"default": "local-model", "provider": "custom",
                           "base_url": "http://127.0.0.1:11434/v1"}})
    result = _api().apply_model_preset("zai")
    assert result["models"] == ["glm-5.3", "glm-5.3-flash"]

    block = load_config()["providers"]["zai"]
    assert block == {"key_env": "GLM_API_KEY", "models": ["glm-5.3", "glm-5.3-flash"]}
    assert "api_key" not in block  # a credential in config.yaml would fail the sovereignty audit


def test_apply_is_idempotent_and_preserves_user_extras():
    from hermes_cli.config import load_config, save_config

    save_config({"providers": {"zai": {"extra_body": {"x": 1}},
                               "local": {"api": "http://127.0.0.1:1/v1"}}})
    assert _api().apply_model_preset("zai")["changed"] is True
    assert _api().apply_model_preset("zai")["changed"] is False

    providers = load_config()["providers"]
    assert providers["zai"]["extra_body"] == {"x": 1}             # user extra kept
    assert providers["zai"]["models"] == ["glm-5.3", "glm-5.3-flash"]
    assert providers["local"]["api"] == "http://127.0.0.1:1/v1"   # unrelated provider kept


def test_applied_flag_tracks_the_allowlist():
    assert _catalogue()["deepseek"]["applied"] is False
    _api().apply_model_preset("deepseek")
    assert _catalogue()["deepseek"]["applied"] is True


def test_unknown_preset_is_404():
    try:
        _api().apply_model_preset("openai")
    except Exception as exc:  # HTTPException, without importing fastapi in the lint lane
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("an unknown preset must raise")
