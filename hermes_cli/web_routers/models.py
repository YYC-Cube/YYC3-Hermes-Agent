"""Model assignment dashboard routes: model info/options/recommended default, auxiliary + MoA slots, /api/model/set.

Extracted from ``hermes_cli.web_server``; helpers/state that tests monkeypatch on
``web_server`` stay there and are resolved late at call time (cycle-safe).
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from hermes_cli.web_deps import LateState, late
from hermes_cli.web_server_config import (
    _AUX_TASK_SLOTS, _UNSET, _apply_model_assignment_sync, _dashboard_code_skew_guard,
    _prepare_main_assignment,
)
from agent.model_metadata import is_local_endpoint
from starlette.concurrency import run_in_threadpool
from hermes_cli.web_models import ModelAssignment, MoaConfigPayload, MoaModelSlot
from hermes_cli.web_routers._common import _CONFIG_MUTATION_LOCK, config_write_scope, http_failure

_log = logging.getLogger("hermes_cli.web_server")
router = APIRouter()

# Late-bound so a test's monkeypatch on the owning module wins at call time.
_config_profile_scope = late("_config_profile_scope", "hermes_cli.web_server_profiles")
_profile_scope = late("_profile_scope", "hermes_cli.web_server_profiles")
load_config = late("load_config", "hermes_cli.config")
save_config = late("save_config", "hermes_cli.config")


_EMPTY_MODEL_INFO: dict = {
    "model": "", "provider": "", "auto_context_length": 0, "config_context_length": 0,
    "effective_context_length": 0, "capabilities": {},
}
_CAPABILITY_FIELDS = ("supports_tools", "supports_vision", "supports_reasoning", "context_window",
                      "max_output_tokens", "model_family")


def _main_model_fields(model_cfg) -> tuple[str, str]:
    """(model, provider) from config's ``model`` section, which may be a plain string."""
    if isinstance(model_cfg, dict):
        return model_cfg.get("default", model_cfg.get("name", "")), model_cfg.get("provider", "")
    return (str(model_cfg) if model_cfg else ""), ""


def _load_config_scoped(profile: Optional[str]) -> dict:
    with _profile_scope(profile):
        return load_config()


@router.get("/api/model/info")
def get_model_info(profile: Optional[str] = None):
    """Resolved metadata for the configured model: auto-detected vs configured
    context length (so the UI can show "Auto-detected: 200K" beside the
    override) plus models.dev capabilities when available."""
    try:
        model_cfg = _load_config_scoped(profile).get("model", "")
        model_name, provider = _main_model_fields(model_cfg)
        base_url = model_cfg.get("base_url", "") if isinstance(model_cfg, dict) else ""
        config_ctx = model_cfg.get("context_length") if isinstance(model_cfg, dict) else None

        if not model_name:
            return dict(_EMPTY_MODEL_INFO, provider=provider)

        try:
            from agent.model_metadata import get_model_context_length
            # config_context_length=None: ignore the override — we want the auto value
            auto_ctx = get_model_context_length(model=model_name, base_url=base_url, provider=provider,
                                                config_context_length=None)
        except Exception:
            auto_ctx = 0

        config_ctx_int = config_ctx if isinstance(config_ctx, int) and config_ctx > 0 else 0

        caps = {}
        try:
            from agent.models_dev import get_model_capabilities
            mc = get_model_capabilities(provider=provider, model=model_name)
            if mc is not None:
                caps = {name: getattr(mc, name) for name in _CAPABILITY_FIELDS}
        except Exception:
            pass

        return {
            "model": model_name, "provider": provider, "auto_context_length": auto_ctx,
            "config_context_length": config_ctx_int,
            "effective_context_length": config_ctx_int or auto_ctx,  # what the agent actually uses
            "capabilities": caps,
        }
    except HTTPException:
        # Unknown/invalid profile must surface as 404, not degrade into a
        # 200 with empty model info (which would render as "no model set").
        raise
    except Exception:
        _log.exception("GET /api/model/info failed")
        return dict(_EMPTY_MODEL_INFO)


@router.get("/api/model/options")
async def get_model_options(
    profile: Optional[str] = None,
    refresh: bool = False,
    include_unconfigured: bool = False,
    explicit_only: bool = False,
):
    """Authenticated providers + curated model lists — REST twin of the ``model.options``
    JSON-RPC on tui_gateway, same response shape so ``ModelPickerDialog`` shares the types.
    ``profile`` scopes the picker context so the Models page reads the SAME profile
    /api/model/set writes. ``refresh`` busts the per-provider model-id disk cache
    (picker's explicit "Refresh Models"); normal opens stay on the 1h cache."""
    with http_failure("GET /api/model/options failed", 500, detail="Failed to list model options"):
        skew_msg = _dashboard_code_skew_guard()
        if skew_msg:
            _log.warning("GET /api/model/options refused: %s", skew_msg)
            raise HTTPException(status_code=503, detail=f"Restart required: {skew_msg}")

        from hermes_cli.inventory import build_model_options_payload, load_picker_context

        def _build_payload_scoped() -> dict:
            # Full sync picker build off the event loop under the requested profile.
            # _config_profile_scope (contextvar only, no skill-module lock): the build can
            # block 15s on a models.dev cache miss, and _profile_scope's RLock held across
            # that starves concurrent /api/config and freezes the server.
            with _config_profile_scope(profile):
                return build_model_options_payload(
                    load_picker_context(), explicit_only=bool(explicit_only),
                    include_unconfigured=bool(include_unconfigured), refresh=bool(refresh))

        return await run_in_threadpool(_build_payload_scoped)


def _nous_recommended_default() -> dict:
    from hermes_cli.models import recommended_nous_default_model
    return recommended_nous_default_model()


@router.get("/api/model/recommended-default")
def get_recommended_default_model(provider: str = ""):
    """Recommended default model for a freshly-authenticated provider, mirroring
    ``hermes model``'s curation so GUI onboarding lands on a sensible default.
    Nous honors the user's free/paid tier. Any other provider gets the preferred
    silent default when its curated list carries it, else the first curated model —
    aggregator lists lead with the priciest Anthropic flagship, which must never be
    the model a user lands on without explicitly picking it.
    Response: {"provider", "model", "free_tier": bool | None} — free_tier only for
    Nous; ``model`` may be empty (caller degrades gracefully)."""
    slug = (provider or "").strip().lower()

    if slug == "nous":
        try:
            return _nous_recommended_default()
        except Exception:
            _log.exception("GET /api/model/recommended-default (nous) failed")
            return {"provider": "nous", "model": "", "free_tier": None}

    try:
        from hermes_cli.inventory import build_models_payload, load_picker_context
        from hermes_cli.models import pick_silent_default_model

        payload = build_models_payload(load_picker_context())
        for row in payload.get("providers", []):
            if str(row.get("slug", "")).lower() == slug:
                models = [str(m) for m in (row.get("models") or [])]
                return {"provider": slug, "model": pick_silent_default_model(models, provider=slug), "free_tier": None}
        return {"provider": slug, "model": "", "free_tier": None}
    except Exception:
        _log.exception("GET /api/model/recommended-default failed")
        return {"provider": slug, "model": "", "free_tier": None}


@router.get("/api/model/auxiliary")
def get_auxiliary_models(profile: Optional[str] = None):
    """Current auxiliary task assignments: ``{"tasks": [{task, provider, model,
    base_url}, ...], "main": {provider, model}}``. ``profile`` scopes the read —
    without it the Models page would show the dashboard profile's pins while
    /api/model/set wrote the selected profile's."""
    with http_failure("GET /api/model/auxiliary failed", 500, detail="Failed to read auxiliary config"):
        cfg = _load_config_scoped(profile)
        aux_cfg = cfg.get("auxiliary", {})
        if not isinstance(aux_cfg, dict):
            aux_cfg = {}

        tasks = []
        for slot in _AUX_TASK_SLOTS:
            slot_cfg = aux_cfg.get(slot, {}) if isinstance(aux_cfg.get(slot), dict) else {}
            base_url = str(slot_cfg.get("base_url", "") or "")
            tasks.append({
                "task": slot, "provider": str(slot_cfg.get("provider", "auto") or "auto"),
                "model": str(slot_cfg.get("model", "") or ""), "base_url": base_url,
                "reasoning_effort": str(slot_cfg.get("reasoning_effort") or "") or None,
                # Lets the UI tell a free local/LAN pin from a forgotten paid-provider pin.
                "local_endpoint": is_local_endpoint(base_url),
            })

        model, provider = _main_model_fields(cfg.get("model", {}))
        return {"tasks": tasks, "main": {"provider": str(provider or ""), "model": str(model or "")}}


@router.get("/api/model/moa")
def get_moa_models(profile: Optional[str] = None):
    """Return the configured Mixture-of-Agents provider/model slots."""
    with http_failure("GET /api/model/moa failed", 500, detail="Failed to read MoA config"):
        from hermes_cli.moa_config import normalize_moa_config

        with _profile_scope(profile):
            cfg = load_config()
            return normalize_moa_config(cfg.get("moa") if isinstance(cfg, dict) else {})


_MOA_PRESET_FIELDS = (
    "reference_temperature", "aggregator_temperature", "reference_timeout",
    "degraded_reference_policy", "fanout", "enabled",
)


def _slot_dict(slot: MoaModelSlot) -> dict:
    # Drop unset optionals so saved slots stay minimal ({provider, model}).
    return {k: v for k, v in slot.dict().items() if v is not None}


def _preset_dict(preset) -> dict:
    """Raw preset dict from a MoaPresetPayload or the flat MoaConfigPayload fields."""
    return {
        "reference_models": [_slot_dict(slot) for slot in preset.reference_models],
        "aggregator": _slot_dict(preset.aggregator),
        **{name: getattr(preset, name) for name in _MOA_PRESET_FIELDS},
    }


@router.put("/api/model/moa")
def set_moa_models(body: MoaConfigPayload, profile: Optional[str] = None):
    """Persist the Mixture-of-Agents provider/model slots."""
    with http_failure("PUT /api/model/moa failed", 500, detail="Failed to save MoA config"):
        from hermes_cli.moa_config import normalize_moa_config, validate_moa_payload

        # load→mutate→save runs on a worker thread (sync-def endpoint); the
        # desktop's debounced PUT /api/config autosave races it, so the whole
        # span holds _CONFIG_MUTATION_LOCK or one of the two saves is dropped.
        with config_write_scope(body.profile or profile):
            cfg = load_config()
            if body.presets:
                raw = {
                    "default_preset": body.default_preset,
                    "active_preset": body.active_preset,
                    "presets": {name: _preset_dict(preset) for name, preset in body.presets.items()},
                }
            else:
                raw = _preset_dict(body)  # legacy flat payload from older clients

            # Reject-don't-repair: normalize_moa_config() silently swaps any preset with
            # incomplete slots for the hardcoded defaults — correct tolerance at READ time,
            # silent data loss at WRITE time (desktop autosave of a half-filled slot replaced
            # the user's whole preset). Refuse loudly so no client can corrupt config here.
            # See #64156.
            problems = validate_moa_payload(raw)
            if problems:
                raise HTTPException(status_code=422, detail="Invalid MoA config: " + "; ".join(problems))
            normalized = normalize_moa_config(raw)
            # Merge, don't overwrite: hand-edited keys not in MoaConfigPayload (save_traces, trace_dir) survive.
            # See issue #58819. Write ONLY the moa section (merge_existing deep-merges it over the
            # on-disk raw file): saving the whole default-expanded ``cfg`` snapshot re-persisted
            # every other section too, so a Desktop MoA autosave could wipe a chain another
            # surface wrote meanwhile (#89184, ``fallback_providers: []``).
            moa_section = dict(cfg.get("moa") or {})
            moa_section.update(normalized)
            save_config({"moa": moa_section}, merge_existing=True)
            return {"ok": True, **normalized}


@router.post("/api/model/set")
async def set_model_assignment(body: ModelAssignment, profile: Optional[str] = None):
    """Assign a model to the main slot or an auxiliary task slot. Writes
    ``~/.hermes/config.yaml`` — applies to **new** sessions only; a running chat
    PTY hot-swaps via the ``/model`` slash command instead."""
    scope, task = (body.scope or "").strip().lower(), (body.task or "").strip().lower()
    provider, model = (body.provider or "").strip(), (body.model or "").strip()
    base_url, api_key = (body.base_url or "").strip(), (body.api_key or "").strip()

    if scope not in {"main", "auxiliary"}:
        raise HTTPException(status_code=400, detail="scope must be 'main' or 'auxiliary'")

    with http_failure("POST /api/model/set failed", 500, detail="Failed to save model assignment"):
        # Expensive-model warning runs BEFORE the profile scope is entered: _profile_scope
        # must never be held across an await (the RLock is reentrant per-thread, so a second
        # coroutine interleaving on the event-loop thread could cross-restore module globals).
        if model and not body.confirm_expensive_model:
            try:
                from hermes_cli.model_selection_guards import combined_selection_warning

                # Pricing lookup can hit models.dev / a /models endpoint on a cache miss — off the loop.
                warning = await asyncio.to_thread(combined_selection_warning, model, provider=provider, base_url=base_url)
            except Exception:
                warning = None
            if warning is not None:
                return {"ok": False, "scope": scope, "provider": provider, "model": model,
                        "confirm_required": True, "confirm_message": warning.message}

        reasoning_effort = body.reasoning_effort if "reasoning_effort" in body.model_fields_set else _UNSET

        def _apply_assignment():
            # Same RMW span as PUT /api/config: applyMainModel fires this while the
            # settings-page autosave is in flight — hold the mutation lock. switch_model's
            # catalog fetches / endpoint probes are network I/O, so they run BEFORE the lock;
            # only load→apply→save holds it.
            with _profile_scope(body.profile or profile):
                prepared = (_prepare_main_assignment(load_config(), provider, model, base_url, api_key)
                            if scope == "main" else None)
                with _CONFIG_MUTATION_LOCK:
                    return _apply_model_assignment_sync(
                        scope, provider, model, task, base_url, api_key,
                        reasoning_effort=reasoning_effort, prepared=prepared)

        return await asyncio.to_thread(_apply_assignment)


# ── Cloud provider presets (ADR-001) ─────────────────────────────────────────────────────────────
# Two one-click presets matching the authorized cloud pair: DeepSeek and Z.AI/GLM. Applying one
# writes only the non-secret ``providers.<id>`` block (``key_env`` + authorized ``models``); the
# credential is set on the environment page, so no secret transits this surface, and the endpoint
# stays fixed by the bundled provider profile. Keep the model lists in sync with ADR-001 §2 D2.
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
            {"id": "deepseek-v4-pro", "role": "flagship", "context_window": 1_000_000,
             "capabilities": ["text", "structured_output", "system_messages"]},
            {"id": "deepseek-flash", "role": "fast", "context_window": 1_000_000,
             "capabilities": ["text", "vision", "structured_output", "system_messages"]},
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
            {"id": "glm-5.3", "role": "flagship", "context_window": 1_310_720,
             "capabilities": ["text", "structured_output", "system_messages"]},
            {"id": "glm-5.3-flash", "role": "fast", "context_window": 1_310_720,
             "capabilities": ["text", "vision", "structured_output", "system_messages"]},
        ],
    },
}


def preset_model_ids(preset: Dict[str, Any]) -> List[str]:
    """Authorized model ids of a preset, in display order."""
    return [str(m["id"]) for m in preset.get("models", ())]


def provider_block(preset: Dict[str, Any]) -> Dict[str, Any]:
    """The non-secret ``providers.<id>`` block a preset writes (no api_key, no endpoint)."""
    return {"key_env": preset["key_env"], "models": preset_model_ids(preset)}


def apply_preset(config: Dict[str, Any], preset: Dict[str, Any]) -> Dict[str, Any]:
    """Return *config* with ``providers.<id>`` carrying the preset block (idempotent).

    Other providers, user extras on this entry (timeouts, extra_body) and every unrelated
    section are preserved; an entry that already matches comes back unchanged.
    """
    providers = config.get("providers")
    if not isinstance(providers, dict):
        providers = {}
    block = provider_block(preset)
    existing = providers.get(preset["provider"])
    if isinstance(existing, dict):
        merged = {**existing, **block}
        if merged == existing:
            return config
        providers = {**providers, preset["provider"]: merged}
    else:
        providers = {**providers, preset["provider"]: block}
    return {**config, "providers": providers}


def preset_status(preset: Dict[str, Any], config: Dict[str, Any], env_get) -> Dict[str, Any]:
    """Catalogue row: preset content + applied state + whether its credential is armed."""
    providers = config.get("providers") if isinstance(config.get("providers"), dict) else {}
    entry = providers.get(preset["provider"]) if isinstance(providers, dict) else None
    applied = isinstance(entry, dict) and list(entry.get("models") or []) == preset_model_ids(preset)
    try:
        key_present = bool(env_get(preset["key_env"]))
    except Exception:
        key_present = False
    return {**preset, "applied": applied, "key_present": key_present,
            "authorized_models": preset_model_ids(preset)}


@router.get("/api/model/presets")
def list_model_presets():
    """Preset catalogue for the Models page, with applied/key state for this profile."""
    from hermes_cli.config import get_env_value

    config = load_config()
    return {"presets": [preset_status(p, config, get_env_value) for p in PRESETS.values()]}


@router.post("/api/model/presets/{preset_id}/apply")
def apply_model_preset(preset_id: str):
    """Write the preset's provider block into config.yaml (no secrets, idempotent)."""
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
