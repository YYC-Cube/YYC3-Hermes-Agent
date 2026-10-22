"""Tests for the providers-tools plugin's Ollama discovery helpers.

Pure parsing only: no network, no real Ollama server.
"""

from __future__ import annotations

from plugins.providers_tools import ollama
from plugins.providers_tools.cli import _slugify


def test_normalize_base_url_accepts_openai_and_api_forms():
    assert ollama.normalize_base_url("http://127.0.0.1:11434/v1/") == "http://127.0.0.1:11434"
    assert ollama.normalize_base_url("localhost:11434") == "http://localhost:11434"
    assert ollama.normalize_base_url("http://example.test/api") == "http://example.test"


def test_context_length_prefers_served_num_ctx_over_architecture_max():
    assert ollama._context_length({
        "parameters": "num_ctx 65536",
        "model_info": {"qwen3.context_length": 262144},
    }) == 65536
    assert ollama._context_length({"parameters": {"num_ctx": "32768"}}) == 32768
    assert ollama._context_length({"model_info": {"qwen3.context_length": 131072}}) == 131072
    assert ollama._context_length({}) == 0


def test_capabilities_prefers_explicit_list_then_template():
    assert ollama._capabilities({"capabilities": ["completion", "tools"]}) == {"completion", "tools"}
    assert "tools" in ollama._capabilities({"template": "{{ .Tools }} ..."})
    assert ollama._capabilities({}) == set()


def test_scan_enriches_tags_without_network(monkeypatch):
    def fake_json(url, *, payload=None, timeout=3.0):
        if url.endswith("/api/tags"):
            return {"models": [
                {"name": "qwen3-coder-30b-64k", "size": 25 * 1024 ** 3,
                 "details": {"parameter_size": "30.5B", "quantization_level": "Q4_K_M"}},
            ]}
        assert payload == {"model": "qwen3-coder-30b-64k"}
        return {"model_info": {"qwen3moe.context_length": 65536},
                "capabilities": ["completion", "tools"]}

    monkeypatch.setattr(ollama, "_json", fake_json)
    base, models = ollama.scan("http://localhost:11434/v1")

    assert base == "http://localhost:11434"
    assert [model.name for model in models] == ["qwen3-coder-30b-64k"]
    assert models[0].context_length == 65536
    assert models[0].tools is True
    assert models[0].parameter_size == "30.5B"


def test_slugify_keeps_config_keys_safe():
    assert _slugify("My Ollama!") == "my-ollama"
    assert _slugify("  ") == "provider"
