"""Provider presets for the dashboard Models page (ADR-001 cloud allowlist).

Two presets ship, matching the authorized cloud pair in ADR-001: DeepSeek (flagship
``deepseek-v4-pro`` + fast ``deepseek-flash``) and Z.AI/GLM (flagship ``glm-5.3`` +
fast ``glm-5.3-flash``). Applying a preset writes only the non-secret provider block
(``key_env`` + authorized ``models``) into ``config.yaml``; the API key itself is set
through the existing environment page, so no credential ever transits this surface.

Endpoints:
  GET  /api/model/presets               preset catalogue + applied/key presence
  POST /api/model/presets/{preset}/apply idempotent merge into providers.<id>
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

router = APIRouter()

# Official provider configuration. Endpoints and capabilities come from the bundled
# provider profiles and the model metadata table — keep them in sync with ADR-001 D2.
PRESETS: Dict[str, Dict[str, Any]] = {
    "deepseek": {
        "id": "deepseek",
        "label": "DeepSeek",
        "description": "DeepSeek 官方 API — 旗舰 v4-pro + 快档 flash（上下文 1M，flash 支持视觉）",
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "transport": "chat_completions",
        "key_env": "DEEPSEEK_API_KEY",
        "models": [
            {
                "id": "deepseek-v4-pro",
                "role": "flagship",
                "context_window": 1_000_000,
                "capabilities": ["text", "structured_output", "system_messages"],
            },
            {
                "id": "deepseek-flash",
                "role": "fast",
                "context_window": 1_000_000,
                "capabilities": ["text", "vision", "structured_output", "system_messages"],
            },
        ],
    },
    "zai": {
        "id": "zai",
        "label": "Z.AI (GLM)",
        "description": "智谱 Z.AI 官方 API — 旗舰 glm-5.3 + 快档 glm-5.3-flash（上下文 1.31M，flash 支持视觉）",
        "provider": "zai",
        "base_url": "https://api.z.ai/api/paas/v4",
        "transport": "chat_completions",
        "key_env": "GLM_API_KEY",
        "models": [
            {
                "id": "glm-5.3",
                "role": "flagship",
                "context_window": 1_310_720,
                "capabilities": ["text", "structured_output", "system_messages"],
            },
            {
                "id": "glm-5.3-flash",
                "role": "fast",
                "context_window": 1_310_720,
                "capabilities": ["text", "vision", "structured_output", "system_messages"],
            },
        ],
    },
}


def preset_model_ids(preset: Dict[str, Any]) -> List[str]:
    """Authorized model ids of a preset, in display order."""
    return [str(m["id"]) for m in preset.get("models", ())]


def provider_block(preset: Dict[str, Any]) -> Dict[str, Any]:
    """The non-secret ``providers.<id>`` block a preset writes.

    Endpoints stay out: the bundled provider profile already carries the official base
    URL, and ADR-001 fixes it. A key would be a credential in ``config.yaml`` — refused
    by the sovereignty audit — so only the env-var name is written.
    """
    return {"key_env": preset["key_env"], "models": preset_model_ids(preset)}


def apply_preset(config: Dict[str, Any], preset: Dict[str, Any]) -> Dict[str, Any]:
    """Return *config* with ``providers.<id>`` set to the preset block (idempotent).

    Other providers, other keys and every unrelated section are preserved; an entry
    that already matches is returned unchanged so a re-click is a no-op.
    """
    providers = config.get("providers")
    if not isinstance(providers, dict):
        providers = {}
    block = provider_block(preset)
    existing = providers.get(preset["provider"])
    if isinstance(existing, dict):
        merged = dict(existing)
        merged.update(block)  # keep user extras (timeouts, extra_body), enforce the allowlist
        if merged == existing:
            return config
        providers = {**providers, preset["provider"]: merged}
    else:
        providers = {**providers, preset["provider"]: block}
    return {**config, "providers": providers}


def preset_status(
    preset: Dict[str, Any], config: Dict[str, Any], env_get
) -> Dict[str, Any]:
    """Catalogue row: preset content + whether it is applied and whether its key is armed."""
    providers = config.get("providers") if isinstance(config.get("providers"), dict) else {}
    entry = providers.get(preset["provider"]) if isinstance(providers, dict) else None
    applied = isinstance(entry, dict) and list(entry.get("models") or []) == preset_model_ids(preset)
    try:
        key_present = bool(env_get(preset["key_env"]))
    except Exception:
        key_present = False
    return {
        **preset,
        "applied": applied,
        "key_present": key_present,
        "authorized_models": preset_model_ids(preset),
    }


@router.get("/api/model/presets")
def list_model_presets():
    """Preset catalogue for the Models page, with applied/key state for this profile."""
    from hermes_cli.config import get_env_value, load_config

    config = load_config()
    return {"presets": [preset_status(p, config, get_env_value) for p in PRESETS.values()]}


@router.post("/api/model/presets/{preset_id}/apply")
def apply_model_preset(preset_id: str):
    """Write the preset's provider block into config.yaml (no secrets, idempotent)."""
    from hermes_cli.config import load_config, save_config

    preset = PRESETS.get(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"unknown preset: {preset_id}")
    config = load_config()
    updated = apply_preset(config, preset)
    changed = updated is not config
    if changed:
        save_config(updated, merge_existing=True)
    return {
        "preset": preset_id,
        "provider": preset["provider"],
        "models": preset_model_ids(preset),
        "key_env": preset["key_env"],
        "changed": changed,
        "next_step": f"在「环境变量」页设置 {preset['key_env']}，然后在 /model 中选择该模型",
    }
