"""Read-only Ollama discovery for the ``hermes providers`` CLI.

``/api/tags`` lists local models; ``/api/show`` adds the context window and
capabilities. Discovery is best-effort: an unreachable server raises, but a
single model's failed enrichment only leaves its optional fields empty.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:11434"


def normalize_base_url(value: str | None) -> str:
    """Accept ``host:port``, a ``/v1`` OpenAI base, or an ``/api`` root."""
    raw = (value or "").strip() or DEFAULT_BASE_URL
    if "://" not in raw:
        raw = "http://" + raw
    raw = raw.rstrip("/")
    for suffix in ("/v1", "/api"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
    return raw.rstrip("/")


def _json(url: str, *, payload: dict | None = None, timeout: float = 3.0) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(
        url, data=data, headers=headers, method="POST" if data is not None else "GET"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    parsed = json.loads(body.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"unexpected Ollama response from {url}")
    return parsed


@dataclass
class OllamaModel:
    name: str
    size: int = 0
    modified_at: str = ""
    parameter_size: str = ""
    quantization: str = ""
    family: str = ""
    context_length: int = 0
    tools: bool = False
    vision: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "size": self.size,
            "modified_at": self.modified_at,
            "parameter_size": self.parameter_size,
            "quantization": self.quantization,
            "family": self.family,
            "context_length": self.context_length,
            "tools": self.tools,
            "vision": self.vision,
        }


def _context_length(show: dict) -> int:
    """Effective served window: ``num_ctx`` wins over the architecture maximum.

    A model's ``model_info.*.context_length`` is what the architecture *can*
    handle; Ollama serves the much smaller ``num_ctx`` (8,192 by default)
    unless a Modelfile/request raises it. Reporting the maximum would tell a
    user their 8K model is 262K and silently break compression.
    """
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
    # Older Ollama builds omit ``capabilities``; the template is the only hint.
    template = str(show.get("template") or "").lower()
    return {"tools"} if "tools" in template else set()


def scan(
    base_url: str | None = None, *, enrich: bool = True, timeout: float = 3.0
) -> tuple[str, list[OllamaModel]]:
    """Return ``(normalized_base_url, models)`` for a running Ollama server."""
    base = normalize_base_url(base_url)
    tags = _json(f"{base}/api/tags", timeout=timeout)
    models: list[OllamaModel] = []
    for item in tags.get("models") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("model") or "").strip()
        if not name:
            continue
        details = item.get("details") if isinstance(item.get("details"), dict) else {}
        model = OllamaModel(
            name=name,
            size=int(item.get("size") or 0),
            modified_at=str(item.get("modified_at") or ""),
            parameter_size=str(details.get("parameter_size") or ""),
            quantization=str(details.get("quantization_level") or ""),
            family=str(details.get("family") or ""),
        )
        if enrich:
            try:
                show = _json(f"{base}/api/show", payload={"model": name}, timeout=timeout)
                model.context_length = _context_length(show)
                caps = _capabilities(show)
                model.tools = "tools" in caps
                model.vision = "vision" in caps
            except (OSError, ValueError, urllib.error.URLError):
                pass
        models.append(model)
    models.sort(key=lambda model: model.name)
    return base, models


def format_size(size: int) -> str:
    if size >= 1024 ** 3:
        return f"{size / (1024 ** 3):.1f}GB"
    return f"{size / (1024 ** 2):.0f}MB"
