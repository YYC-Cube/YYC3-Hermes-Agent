"""ADR-001 data-sovereignty audit: local-first, cloud egress limited to the authorized 4 models.

Behaviour contract: a config is compliant iff every model/STT/aux route is either loopback or
one of the two authorized providers (deepseek, zai) using one of its two authorized models.
The audit is a pure function over (config, env-name-list) — no disk, no network.

No ``import pytest`` on purpose: the lint lane type-checks this tree without test dependencies
installed, so a module-level pytest import would register as a new unresolved-import diagnostic.
Plain ``test_*`` functions run under pytest and keep this file type-check clean.
"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "data_sovereignty_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("data_sovereignty_check", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LOCAL = {
    "model": {"default": "qwen3-coder-30b-64k", "provider": "custom",
              "base_url": "http://127.0.0.1:11434/v1"},
    "stt": {"enabled": True, "provider": "local"},
}
AUTHORIZED = {
    "model": dict(LOCAL["model"]),
    "providers": {
        "deepseek": {"key_env": "DEEPSEEK_API_KEY", "models": ["deepseek-v4-pro", "deepseek-flash"]},
        "zai": {"key_env": "GLM_API_KEY", "models": ["glm-5.3", "glm-5.3-flash"]},
    },
    "stt": {"enabled": True, "provider": "local"},
}

CASES = [
    ("local only", LOCAL, (), True),
    ("authorized cloud", AUTHORIZED, ("DEEPSEEK_API_KEY", "GLM_API_KEY"), True),
    ("non-allowlisted provider",
     {"model": {"default": "gpt-6", "provider": "openai"}, "stt": {"provider": "local"}}, (), False),
    ("non-allowlisted endpoint",
     {**LOCAL, "providers": {"relay": {"api": "https://relay.example.com/v1", "models": ["glm-5.3"]}}}, (), False),
    ("model outside allowlist",
     {**LOCAL, "providers": {"deepseek": {"models": ["deepseek-v4-pro", "deepseek-r1"]}}}, (), False),
    ("cloud STT", {**LOCAL, "stt": {"enabled": True, "provider": "openai"}}, (), False),
    ("inline credential",
     {**LOCAL, "providers": {"zai": {"api_key": "<inline-placeholder>", "models": ["glm-5.2"]}}}, (), False),
    ("foreign credential", LOCAL, ("OPENAI_API_KEY",), False),
    ("aux route to forbidden provider",
     {**LOCAL, "auxiliary": {"compression": {"provider": "anthropic", "model": "claude-opus-5"}}}, (), False),
    ("delegation to forbidden provider",
     {**LOCAL, "delegation": {"provider": "gemini", "model": "gemini-9-pro"}}, (), False),
]


def test_audit_contract():
    """Each row states whether the config may egress; the audit must agree."""
    audit = _load().audit
    for label, config, env, compliant in CASES:
        violations, _warnings = audit(config, env)
        assert (not violations) is compliant, f"{label}: {violations}"


def test_authorized_model_aliases_resolve_to_the_same_policy():
    """``glm``/``zhipu``/``z-ai`` all resolve to zai, so an alias cannot bypass the allowlist."""
    audit = _load().audit
    for alias in ("glm", "zhipu", "z-ai", "z.ai"):
        violations, _ = audit({**LOCAL, "model": {"provider": alias, "default": "glm-5.3"}}, ())
        assert not violations, f"{alias}: {violations}"
        violations, _ = audit({**LOCAL, "model": {"provider": alias, "default": "glm-9-offlist"}}, ())
        assert violations, f"{alias} must not authorize an off-list model"


def test_self_test_fixtures_pass(capsys):
    """The shipped --self-test fixtures must stay green (they mirror this contract)."""
    assert _load()._self_test() == 0
    assert "8/8 passed" in capsys.readouterr().out
