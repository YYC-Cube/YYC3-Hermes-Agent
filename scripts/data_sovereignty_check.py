#!/usr/bin/env python3
"""Data-sovereignty audit for the YYC3 Hermes fork — enforces ADR-001.

Checks that the *effective configuration* cannot send conversation content to any
cloud endpoint outside the two authorized providers (DeepSeek, Z.AI/GLM) and the
four authorized models (deepseek-v4-pro, deepseek-flash, glm-5.2, glm-4.5-flash).
Local-first is the default; any loopback route is always allowed.

Reads: ``$HERMES_HOME/config.yaml`` (or ``--config``) and the secret *names* in
``$HERMES_HOME/.env`` (never values). Pure static inspection: no network, no
content is printed or transmitted.

Exit codes: 0 = policy satisfied (warnings allowed), 1 = violation(s), 2 = usage.

Usage:
  scripts/data_sovereignty_check.py                 # audit the live profile
  scripts/data_sovereignty_check.py --json          # machine-readable
  scripts/data_sovereignty_check.py --self-test     # built-in fixtures, no disk
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

POLICY_ID = "ADR-001"

# ── Policy (single source: docs/.../11-数据主权与云API白名单ADR.md §2 D2) ──────
CLOUD_ALLOWLIST: dict[str, dict[str, Any]] = {
    "deepseek": {
        "hosts": frozenset({"api.deepseek.com"}),
        "models": frozenset({"deepseek-v4-pro", "deepseek-flash"}),
    },
    "zai": {
        "hosts": frozenset({"api.z.ai"}),
        "models": frozenset({"glm-5.2", "glm-4.5-flash"}),
    },
}
PROVIDER_ALIASES = {
    "glm": "zai", "z-ai": "zai", "z.ai": "zai", "zhipu": "zai", "z-ai-glm": "zai",
    "deep-seek": "deepseek", "deepseek-chat": "deepseek",
}
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "0.0.0.0", "[::1]"})
LOCAL_PROVIDERS = frozenset({"", "custom", "ollama", "local", "llamacpp", "lmstudio"})
# Credentials the policy explicitly allows in .env (D3).
ALLOWED_CLOUD_CREDENTIALS = frozenset({"DEEPSEEK_API_KEY", "GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"})
# Cloud STT providers would ship audio off-box; only "local" is authorized (D4).
CLOUD_STT_PROVIDERS = frozenset({"groq", "openai", "mistral", "elevenlabs", "deepinfra", "azure", "whisper-cloud"})
# Fallback when the provider registry cannot be imported (audit portability).
FALLBACK_PROVIDER_ENV = frozenset({
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY",
    "XAI_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY", "TOGETHER_API_KEY", "FIREWORKS_API_KEY",
    "DEEPINFRA_API_KEY", "NVIDIA_API_KEY", "CEREBRAS_API_KEY", "SAMBANOVA_API_KEY", "COHERE_API_KEY",
    "MOONSHOT_API_KEY", "MINIMAX_API_KEY", "DASHSCOPE_API_KEY", "QWEN_API_KEY", "ARK_API_KEY",
    "VOLCENGINE_API_KEY", "BAIDU_API_KEY", "HUNYUAN_API_KEY", "STEPFUN_API_KEY", "NOVITA_API_KEY",
    "HYPERBOLIC_API_KEY", "PERPLEXITY_API_KEY", "REPLICATE_API_TOKEN", "HUGGINGFACE_API_KEY",
    "HF_TOKEN", "AZURE_OPENAI_API_KEY", "AZURE_FOUNDRY_API_KEY", "VERTEX_API_KEY",
})

# Keys that name a remote endpoint for a route.
_URL_KEYS = ("base_url", "api", "url", "endpoint")
# Task blocks under ``auxiliary:`` that are not routes.
_AUX_SKIP_KEYS = frozenset({
    "transient_retries", "free_only", "openrouter_model", "stream_only_base_urls",
})


def _host(url: Any) -> str:
    """Lower-cased hostname of *url* ("" when absent/unparseable)."""
    if not isinstance(url, str) or not url.strip():
        return ""
    try:
        return (urlsplit(url.strip()).hostname or "").lower()
    except ValueError:
        return ""


def _canon_provider(name: Any) -> str:
    n = str(name or "").strip().lower()
    return PROVIDER_ALIASES.get(n, n)


def _is_local_host(host: str) -> bool:
    return host in LOCAL_HOSTS


def _allowed_for(provider: str) -> dict[str, Any] | None:
    return CLOUD_ALLOWLIST.get(_canon_provider(provider))


def _credential_env_names() -> frozenset[str]:
    """Provider credential env var names, from the registry when importable."""
    try:  # repo checkout on sys.path (preflight runs from the repo root)
        from providers import list_providers  # type: ignore

        names: set[str] = set()
        for profile in list_providers():
            for var in getattr(profile, "env_vars", ()) or ():
                if isinstance(var, str) and var.isupper() and not var.endswith(("_URL", "_BASE_URL")):
                    names.add(var)
        return frozenset(names) | FALLBACK_PROVIDER_ENV
    except Exception:
        return FALLBACK_PROVIDER_ENV


def _check_route(
    label: str,
    *,
    provider: Any = "",
    base_url: Any = "",
    model: Any = "",
    violations: list[str],
    warnings: list[str],
) -> None:
    """One route: loopback is free; anything else must be an allowlisted provider/model."""
    prov = _canon_provider(provider)
    host = _host(base_url)
    mdl = str(model or "").strip()
    if host and _is_local_host(host):
        return  # local-first: always authorized
    allowed = _allowed_for(prov)
    if host:  # explicit remote endpoint
        if allowed is None:
            violations.append(
                f"{label}: remote endpoint {host!r} is not an authorized cloud provider "
                f"(allowed: {', '.join(sorted(CLOUD_ALLOWLIST))})")
            return
        if host not in allowed["hosts"]:
            violations.append(
                f"{label}: provider {prov!r} must use {sorted(allowed['hosts'])}, got {host!r}")
            return
    else:  # no endpoint declared: the provider id decides
        if prov in LOCAL_PROVIDERS:
            return
        if allowed is None:
            violations.append(
                f"{label}: provider {prov!r} is not authorized "
                f"(local or {', '.join(sorted(CLOUD_ALLOWLIST))})")
            return
    if mdl and allowed is not None and mdl.lower() not in allowed["models"]:
        violations.append(
            f"{label}: model {mdl!r} is outside the authorized set for {prov} "
            f"({', '.join(sorted(allowed['models']))})")
    elif not mdl and allowed is not None:
        warnings.append(f"{label}: cloud provider {prov!r} declares no model; the runtime default may be unauthorized")


def _check_provider_entries(
    providers: Any, violations: list[str], warnings: list[str]
) -> None:
    if not isinstance(providers, Mapping):
        return
    for key, entry in providers.items():
        if not isinstance(entry, Mapping):
            continue
        label = f"providers.{key}"
        if entry.get("enabled") is False:
            continue
        if entry.get("api_key"):
            violations.append(f"{label}: inline api_key in config.yaml — credentials belong in .env (D3)")
        base = next((entry.get(k) for k in _URL_KEYS if entry.get(k)), "")
        models = entry.get("models")
        declared: list[str] = []
        if isinstance(models, Mapping):
            declared = [str(k) for k in models if not str(k).startswith("__")]
        elif isinstance(models, list):
            for item in models:
                if isinstance(item, str):
                    declared.append(item)
                elif isinstance(item, Mapping):
                    mid = item.get("id") or item.get("name")
                    if isinstance(mid, str):
                        declared.append(mid)
        if declared:
            for model_id in declared:
                _check_route(f"{label}.models[{model_id}]", provider=key, base_url=base,
                             model=model_id, violations=violations, warnings=warnings)
        else:
            _check_route(label, provider=key, base_url=base, violations=violations, warnings=warnings)


def _check_custom_providers(legacy: Any, violations: list[str], warnings: list[str]) -> None:
    if not isinstance(legacy, list):
        return
    for i, entry in enumerate(legacy):
        if not isinstance(entry, Mapping):
            continue
        name = str(entry.get("name") or f"#{i}")
        base = next((entry.get(k) for k in _URL_KEYS if entry.get(k)), "")
        _check_route(f"custom_providers.{name}", provider=name, base_url=base,
                     model=entry.get("default_model") or entry.get("model") or "",
                     violations=violations, warnings=warnings)


def _check_auxiliary(aux: Any, violations: list[str], warnings: list[str]) -> None:
    if not isinstance(aux, Mapping):
        return
    for task, block in aux.items():
        if task in _AUX_SKIP_KEYS or not isinstance(block, Mapping):
            continue
        _check_route(f"auxiliary.{task}", provider=block.get("provider"),
                     base_url=next((block.get(k) for k in _URL_KEYS if block.get(k)), ""),
                     model=block.get("model"), violations=violations, warnings=warnings)


def _check_fallbacks(config: Mapping[str, Any], violations: list[str], warnings: list[str]) -> None:
    model_cfg = config.get("model") if isinstance(config.get("model"), Mapping) else {}
    candidates = [
        ("model.fallback_providers", model_cfg.get("fallback_providers")),
        ("fallback_providers", config.get("fallback_providers")),
    ]
    for label, value in candidates:
        if not value:
            continue
        entries = value.values() if isinstance(value, Mapping) else (
            value if isinstance(value, (list, tuple)) else [value])
        for item in entries:
            if isinstance(item, str):
                _check_route(label, provider=item, violations=violations, warnings=warnings)
            elif isinstance(item, Mapping):
                _check_route(label, provider=item.get("provider"),
                             base_url=next((item.get(k) for k in _URL_KEYS if item.get(k)), ""),
                             model=item.get("model"), violations=violations, warnings=warnings)


def _check_stt(stt: Any, violations: list[str], warnings: list[str]) -> None:
    if not isinstance(stt, Mapping) or stt.get("enabled") is False:
        return
    provider = str(stt.get("provider") or "").strip().lower()
    if provider and provider != "local":
        if provider in CLOUD_STT_PROVIDERS:
            violations.append(
                f"stt.provider: {provider!r} uploads audio off-box — set 'local' (D4)")
        else:
            warnings.append(f"stt.provider: unrecognized {provider!r}; verify it is local")
    elif not provider:
        warnings.append("stt.provider: unset — autodetect may pick a cloud backend; set 'local' (D4)")


def _check_env(env_names: Iterable[str], violations: list[str], warnings: list[str]) -> None:
    present = {str(n).strip() for n in env_names if str(n).strip()}
    known = _credential_env_names()
    for name in sorted(present & known):
        if name in ALLOWED_CLOUD_CREDENTIALS:
            continue
        violations.append(f".env: {name} is not an authorized cloud credential (D3; allowed: "
                          f"{', '.join(sorted(ALLOWED_CLOUD_CREDENTIALS))})")
    # Authorized keys are fine; note which are armed so the report is honest about egress.
    armed = sorted(present & ALLOWED_CLOUD_CREDENTIALS)
    if armed:
        warnings.append(f".env: cloud credentials armed ({', '.join(armed)}) — those providers may now be selected")


def audit(config: Mapping[str, Any], env_names: Iterable[str] = ()) -> tuple[list[str], list[str]]:
    """Return ``(violations, warnings)`` for an in-memory config + secret *names*."""
    violations: list[str] = []
    warnings: list[str] = []
    model_cfg = config.get("model") if isinstance(config.get("model"), Mapping) else {}
    _check_route(
        "model",
        provider=model_cfg.get("provider"),
        base_url=model_cfg.get("base_url") or model_cfg.get("api"),
        model=model_cfg.get("default") or model_cfg.get("model"),
        violations=violations,
        warnings=warnings,
    )
    _check_provider_entries(config.get("providers"), violations, warnings)
    _check_custom_providers(config.get("custom_providers"), violations, warnings)
    _check_auxiliary(config.get("auxiliary"), violations, warnings)
    delegation = config.get("delegation")
    if isinstance(delegation, Mapping) and (delegation.get("provider") or delegation.get("base_url")):
        _check_route("delegation", provider=delegation.get("provider"),
                     base_url=delegation.get("base_url"), model=delegation.get("model"),
                     violations=violations, warnings=warnings)
    _check_fallbacks(config, violations, warnings)
    _check_stt(config.get("stt"), violations, warnings)
    _check_env(env_names, violations, warnings)
    return violations, warnings


# ── I/O ──────────────────────────────────────────────────────────────────────
def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))


def _load_config(path: Path) -> dict:
    import yaml  # repo dependency (PyYAML), present in the hermes venv
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _env_names(path: Path) -> list[str]:
    """Secret *names* only — values are never read or printed."""
    if not path.exists():
        return []
    names: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name = line.split("=", 1)[0].strip()
        if name.startswith("export "):
            name = name[len("export "):].strip()
        if name and name.replace("_", "").isalnum():
            names.append(name)
    return names


# ── self-test (fixtures; no disk, no network) ────────────────────────────────
def _self_test() -> int:
    local_default = {
        "model": {"default": "qwen3-coder-30b-64k", "provider": "custom",
                  "base_url": "http://127.0.0.1:11434/v1"},
        "stt": {"enabled": True, "provider": "local"},
    }
    authorized_cloud = {
        "model": dict(local_default["model"]),
        "providers": {
            "deepseek": {"key_env": "DEEPSEEK_API_KEY",
                         "models": ["deepseek-v4-pro", "deepseek-flash"]},
            "zai": {"key_env": "GLM_API_KEY", "models": ["glm-5.2", "glm-4.5-flash"]},
        },
        "stt": {"enabled": True, "provider": "local"},
    }
    forbidden_provider = {
        "model": {"default": "gpt-6", "provider": "openai"},
        "stt": {"enabled": True, "provider": "local"},
    }
    forbidden_endpoint = {
        "model": dict(local_default["model"]),
        "providers": {"relay": {"api": "https://relay.example.com/v1", "models": ["glm-5.2"]}},
        "stt": {"enabled": True, "provider": "local"},
    }
    offlist_model = {
        "model": dict(local_default["model"]),
        "providers": {"deepseek": {"models": ["deepseek-v4-pro", "deepseek-r1"]}},
        "stt": {"enabled": True, "provider": "local"},
    }
    cloud_stt = {
        "model": dict(local_default["model"]),
        "stt": {"enabled": True, "provider": "openai"},
    }
    inline_key = {
        "model": dict(local_default["model"]),
        # Fixture only: the audit must reject an inline credential. Never a real value.
        "providers": {"zai": {"api_key": "<inline-credential-placeholder>",
                              "models": ["glm-5.2", "glm-4.5-flash"]}},
        "stt": {"enabled": True, "provider": "local"},
    }
    cases: list[tuple[str, dict, tuple[str, ...], bool]] = [
        ("local-only passes", local_default, (), True),
        ("authorized cloud passes", authorized_cloud, ("DEEPSEEK_API_KEY", "GLM_API_KEY"), True),
        ("non-allowlisted provider fails", forbidden_provider, (), False),
        ("non-allowlisted endpoint fails", forbidden_endpoint, (), False),
        ("model outside allowlist fails", offlist_model, (), False),
        ("cloud STT fails", cloud_stt, (), False),
        ("inline api_key fails", inline_key, (), False),
        ("foreign credential fails", local_default, ("OPENAI_API_KEY",), False),
    ]
    bad = 0
    for name, cfg, env, should_pass in cases:
        violations, _warnings = audit(cfg, env)
        ok = (not violations) == should_pass
        print(f"{'PASS' if ok else 'FAIL'}  {name}"
              + ("" if ok else f"  -> {violations}"))
        bad += 0 if ok else 1
    print(f"\nself-test: {len(cases) - bad}/{len(cases)} passed")
    return 0 if bad == 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, help="config.yaml path (default: $HERMES_HOME/config.yaml)")
    ap.add_argument("--env-file", type=Path, help=".env path (default: $HERMES_HOME/.env)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--self-test", action="store_true", help="run built-in fixtures (no disk/network)")
    ap.add_argument("--quiet", action="store_true", help="violations only")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()

    home = _hermes_home()
    config_path = args.config or (home / "config.yaml")
    env_path = args.env_file or (home / ".env")
    if not config_path.exists():
        print(f"data-sovereignty: config not found: {config_path}", file=sys.stderr)
        return 2
    config = _load_config(config_path)
    violations, warnings = audit(config, _env_names(env_path))

    if args.json:
        print(json.dumps({
            "policy": POLICY_ID,
            "config": str(config_path),
            "allowlist": {p: {"hosts": sorted(v["hosts"]), "models": sorted(v["models"])}
                          for p, v in CLOUD_ALLOWLIST.items()},
            "violations": violations,
            "warnings": warnings,
        }, indent=2, ensure_ascii=False))
    else:
        print(f"data-sovereignty audit ({POLICY_ID}) — {config_path}")
        if not args.quiet:
            for p, v in CLOUD_ALLOWLIST.items():
                print(f"  authorized cloud: {p} -> {', '.join(sorted(v['models']))}")
            for w in warnings:
                print(f"  WARN  {w}")
        for v in violations:
            print(f"  VIOLATION  {v}")
        print("PASS — policy satisfied" if not violations else f"FAIL — {len(violations)} violation(s)")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
