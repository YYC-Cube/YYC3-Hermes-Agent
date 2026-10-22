"""Ollama-specific probe used by the custom-endpoint validator.

The generic validator calls ``{base_url}/models``, which Ollama answers with ids
only. ``/api/tags`` + ``/api/show`` add what actually matters for agentic use:
the **served** context window (``num_ctx``, often 8,192 even when the model
architecture supports 262K) and whether the model supports tool calling.

Best-effort by design: an unreachable model or a non-Ollama endpoint returns the
entries unchanged.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse


def normalize_ollama_base(value: str | None) -> str:
    """Return the server root (no ``/v1`` or ``/api`` suffix)."""
    raw = (value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "http://" + raw
    raw = raw.rstrip("/")
    for suffix in ("/v1", "/api"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
    return raw.rstrip("/")


def is_ollama_base(value: str | None) -> bool:
    """True only for an explicit Ollama signature (port 11434 / ollama host)."""
    root = normalize_ollama_base(value)
    if not root:
        return False
    parsed = urlparse(root)
    try:
        if parsed.port == 11434:
            return True
    except ValueError:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    return bool(host) and (host == "ollama.com" or host.endswith(".ollama.com") or "ollama" in host.split("."))


def _json(url: str, *, payload: dict | None = None, timeout: float = 2.0) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(
        url, data=data, headers=headers, method="POST" if data is not None else "GET"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    parsed = json.loads(body.decode("utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def effective_context_length(show: dict) -> int:
    """Served window: ``num_ctx`` wins over the architecture maximum."""
    params = show.get("parameters")
    if isinstance(params, str):
        for line in params.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "num_ctx" and parts[1].isdigit():
                return int(parts[1])
    if isinstance(params, dict):
        value = params.get("num_ctx")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    info = show.get("model_info")
    if isinstance(info, dict):
        for key, value in info.items():
            if key.endswith(".context_length") and isinstance(value, int) and value > 0:
                return value
    direct = show.get("context_length")
    return direct if isinstance(direct, int) else 0


def _capabilities(show: dict) -> set[str]:
    caps = show.get("capabilities")
    if isinstance(caps, list):
        return {str(cap) for cap in caps}
    template = str(show.get("template") or "").lower()
    return {"tools"} if "tools" in template else set()


def enrich_entries(base_url: str, entries: list[dict[str, Any]], *, timeout: float = 2.0) -> list[dict[str, Any]]:
    """Attach Ollama metadata to ``/models`` entries; never raises."""
    root = normalize_ollama_base(base_url)
    if not root:
        return entries
    for entry in entries:
        model_id = str(entry.get("id") or "").strip()
        if not model_id:
            continue
        try:
            show = _json(f"{root}/api/show", payload={"model": model_id}, timeout=timeout)
        except (OSError, ValueError, urllib.error.URLError):
            continue
        caps = _capabilities(show)
        context = effective_context_length(show)
        if context:
            entry["context_length"] = context
        entry["tools"] = "tools" in caps
        entry["vision"] = "vision" in caps
        details = show.get("details")
        if isinstance(details, dict):
            if details.get("parameter_size"):
                entry["parameter_size"] = str(details["parameter_size"])
            if details.get("quantization_level"):
                entry["quantization"] = str(details["quantization_level"])
    return entries
