"""Tests for the Ollama enrichment used by the custom-endpoint validator."""

from __future__ import annotations

from hermes_cli import ollama_probe


def test_normalize_and_detect_ollama():
    assert ollama_probe.normalize_ollama_base("http://127.0.0.1:11434/v1/") == "http://127.0.0.1:11434"
    assert ollama_probe.normalize_ollama_base("localhost:11434/api") == "http://localhost:11434"
    assert ollama_probe.is_ollama_base("http://127.0.0.1:11434/v1")
    assert ollama_probe.is_ollama_base("http://gpu-box.local:11434")
    assert not ollama_probe.is_ollama_base("https://api.openai.com/v1")


def test_effective_context_prefers_served_num_ctx():
    assert ollama_probe.effective_context_length({
        "parameters": "num_ctx 65536",
        "model_info": {"qwen3.context_length": 262144},
    }) == 65536
    assert ollama_probe.effective_context_length({"parameters": {"num_ctx": "32768"}}) == 32768
    assert ollama_probe.effective_context_length({"model_info": {"qwen3.context_length": 131072}}) == 131072
    assert ollama_probe.effective_context_length({}) == 0


def test_enrich_entries_adds_capabilities(monkeypatch):
    def fake_json(url, *, payload=None, timeout=2.0):
        assert url.endswith("/api/show")
        assert payload == {"model": "qwen3-coder-30b-64k"}
        return {
            "parameters": "num_ctx 65536",
            "model_info": {"qwen3moe.context_length": 262144},
            "capabilities": ["completion", "tools"],
            "details": {"parameter_size": "30.5B", "quantization_level": "Q4_K_M"},
        }

    monkeypatch.setattr(ollama_probe, "_json", fake_json)
    entries = [{"id": "qwen3-coder-30b-64k"}]
    enriched = ollama_probe.enrich_entries("http://127.0.0.1:11434/v1", entries)

    assert enriched[0]["context_length"] == 65536
    assert enriched[0]["tools"] is True
    assert enriched[0]["vision"] is False
    assert enriched[0]["parameter_size"] == "30.5B"
    assert enriched[0]["quantization"] == "Q4_K_M"


def test_enrich_entries_degrades_on_unreachable_model(monkeypatch):
    def fail(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(ollama_probe, "_json", fail)
    entries = [{"id": "m"}]
    assert ollama_probe.enrich_entries("http://127.0.0.1:11434", entries) == entries
