"""``hermes providers`` — custom provider CRUD + local Ollama discovery."""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
from typing import Any

from .ollama import DEFAULT_BASE_URL, format_size, scan

_MIN_AGENT_CONTEXT = 64_000


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return slug or "provider"


def build_parser(parser: argparse.ArgumentParser) -> None:
    subs = parser.add_subparsers(dest="providers_action")

    subs.add_parser("list", aliases=["ls"], help="List configured custom providers")

    scan_parser = subs.add_parser(
        "scan", help="Discover models on a local Ollama endpoint"
    )
    scan_parser.add_argument(
        "--base-url", default=None,
        help=f"Ollama base URL (default: configured local endpoint or {DEFAULT_BASE_URL})")
    scan_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    scan_parser.add_argument(
        "--no-enrich", action="store_true",
        help="Skip /api/show (faster; omits context length and capabilities)")

    add_parser = subs.add_parser("add", help="Add a custom OpenAI-compatible provider")
    add_parser.add_argument("--name", required=True, help="Display name")
    add_parser.add_argument("--base-url", required=True, help="OpenAI-compatible base URL")
    add_parser.add_argument("--slug", default=None, help="Config key (default: slug of --name)")
    add_parser.add_argument("--api-key", default=None, help="API key (optional)")
    add_parser.add_argument(
        "--model", action="append", default=None, help="Model id (repeatable)")
    add_parser.add_argument("--context-length", type=int, default=None)
    add_parser.add_argument(
        "--scan", action="store_true", help="Fill models/context from a local Ollama endpoint")
    add_parser.add_argument(
        "--use", action="store_true", help="Set the first model as the main model")

    edit_parser = subs.add_parser("edit", help="Edit a configured custom provider")
    edit_parser.add_argument("slug", help="Provider config key")
    edit_parser.add_argument("--name", default=None, help="Display name")
    edit_parser.add_argument("--base-url", default=None, help="OpenAI-compatible base URL")
    edit_parser.add_argument("--api-key", default=None, help="API key")
    edit_parser.add_argument(
        "--model", action="append", default=None, help="Replace the model list (repeatable)")
    edit_parser.add_argument("--context-length", type=int, default=None)
    edit_parser.add_argument("--scan", action="store_true", help="Refresh models from Ollama")
    edit_parser.add_argument(
        "--clear-models", action="store_true", help="Remove every model from this provider")
    edit_parser.add_argument("--use", action="store_true", help="Set the first model as main")

    remove_parser = subs.add_parser("remove", aliases=["rm"], help="Remove a custom provider")
    remove_parser.add_argument("slug", help="Provider config key")
    remove_parser.add_argument(
        "--force", action="store_true", help="Remove even when it is the current provider")

    use_parser = subs.add_parser("use", help="Set a provider's model as the main model")
    use_parser.add_argument("slug", help="Provider config key")
    use_parser.add_argument("--model", default=None, help="Model id (default: provider default)")

    parser.set_defaults(func=providers_command)


def providers_command(args: argparse.Namespace) -> int:
    action = getattr(args, "providers_action", None)
    if not action:
        print("Usage: hermes providers {list|scan|add|edit|remove|use}")
        return 2
    handler = _ACTIONS.get(action)
    if handler is None:
        print(f"Unknown providers action: {action}")
        return 2
    return handler(args)


# ── config helpers ───────────────────────────────────────────────────────


def _load_config() -> dict:
    from hermes_cli.config import load_config

    return load_config()


def _save_config(config: dict) -> None:
    from hermes_cli.config import save_config

    save_config(config, merge_existing=True)


def _provider_map(config: dict) -> dict:
    providers = config.get("providers")
    if not isinstance(providers, dict):
        providers = {}
        config["providers"] = providers
    return providers


def _entry_base_url(entry: dict) -> str:
    return str(entry.get("api") or entry.get("base_url") or "").strip()


def _entry_models(entry: dict) -> list[str]:
    models = entry.get("models")
    return [str(model) for model in models] if isinstance(models, list) else []


def _default_ollama_base(config: dict) -> str:
    model = config.get("model") if isinstance(config.get("model"), dict) else {}
    base = str(model.get("base_url") or "")
    if base and (":11434" in base or "ollama" in base.lower()):
        return base
    return DEFAULT_BASE_URL


def _is_local_ollama(base_url: str) -> bool:
    low = (base_url or "").lower()
    return ":11434" in low or "localhost" in low or "127.0.0.1" in low


def _pick_default(discovered: list) -> Any:
    """Prefer a tool-capable model with the largest served context, then name."""
    candidates = [model for model in discovered if getattr(model, "name", "")]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda model: (0 if model.tools else 1, -model.context_length, model.name),
    )[0]


# ── actions ──────────────────────────────────────────────────────────────


def _cmd_list(_args: argparse.Namespace) -> int:
    config = _load_config()
    providers = _provider_map(config)
    if not providers:
        print("No custom providers configured.")
        print("Add one: hermes providers add --name 'My Ollama' --base-url http://127.0.0.1:11434/v1 --scan --use")
        return 0
    print(f"Custom providers ({len(providers)}):")
    for slug in sorted(providers):
        entry = providers[slug]
        if not isinstance(entry, dict):
            continue
        models = _entry_models(entry)
        print(f"\n  {slug}  {entry.get('name') or ''}")
        print(f"    api:      {_entry_base_url(entry) or '(unset)'}")
        print(f"    models:   {', '.join(models) if models else '(none)'}")
        context = entry.get("context_length")
        if context:
            print(f"    context:  {context}")
        key = "set" if entry.get("api_key") else "not set"
        print(f"    api key:  {key}")
        if entry.get("default_model"):
            print(f"    default:  {entry.get('default_model')}")
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    config = _load_config()
    base_url = args.base_url or _default_ollama_base(config)
    try:
        base, models = scan(base_url, enrich=not args.no_enrich)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print(f"Ollama not reachable at {base_url}: {exc}")
        return 1
    if args.json:
        print(json.dumps({"base_url": base, "models": [model.as_dict() for model in models]},
                         indent=2, sort_keys=True))
        return 0
    print(f"Ollama @ {base} — {len(models)} model(s)")
    if not models:
        print("No models installed. Pull one with: ollama pull qwen3-coder:30b")
        return 0
    print(f"{'NAME':<34} {'CTX':>7} {'TOOLS':<6} {'SIZE':>8} {'PARAMS':<9} QUANT")
    for model in models:
        name = model.name if len(model.name) <= 34 else model.name[:31] + "..."
        context = str(model.context_length) if model.context_length else "?"
        tools = "yes" if model.tools else "no"
        print(f"{name:<34} {context:>7} {tools:<6} {format_size(model.size):>8} "
              f"{model.parameter_size:<9} {model.quantization}")
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    config = _load_config()
    providers = _provider_map(config)
    slug = _slugify(args.slug or args.name)
    if slug in providers:
        print(f"Provider '{slug}' already exists; use `hermes providers edit {slug}`.")
        return 1
    base_url = str(args.base_url).strip()
    models = list(args.model or [])
    context = args.context_length
    default_model = models[0] if models else None
    if args.scan:
        try:
            _, discovered = scan(base_url)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            print(f"Ollama not reachable at {base_url}: {exc}")
            return 1
        models = [model.name for model in discovered]
        picked = _pick_default(discovered)
        if picked is not None:
            default_model = picked.name
            if context is None and picked.context_length:
                context = picked.context_length
    entry: dict[str, Any] = {
        "name": args.name,
        "api": base_url,
        "api_key": args.api_key or ("no-key" if _is_local_ollama(base_url) else ""),
        "models": models,
        "models_discovered": bool(args.scan),
    }
    if context:
        entry["context_length"] = context
    if default_model:
        entry["default_model"] = default_model
    providers[slug] = entry
    _apply_use(config, slug, entry, default_model if args.use else None)
    _save_config(config)
    print(f"Saved provider '{slug}' ({entry['name']}).")
    if default_model:
        print(f"Use it: hermes providers use {slug} --model {default_model}")
    return 0


def _cmd_edit(args: argparse.Namespace) -> int:
    config = _load_config()
    providers = _provider_map(config)
    entry = providers.get(args.slug)
    if not isinstance(entry, dict):
        print(f"Unknown provider: {args.slug}")
        return 1
    if args.name is not None:
        entry["name"] = args.name
    if args.base_url is not None:
        entry["api"] = args.base_url
    if args.api_key is not None:
        entry["api_key"] = args.api_key
    if args.context_length is not None:
        entry["context_length"] = args.context_length
    if args.clear_models:
        entry["models"] = []
    if args.model is not None:
        entry["models"] = list(args.model)
    if args.scan:
        try:
            _, discovered = scan(_entry_base_url(entry))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            print(f"Ollama not reachable at {_entry_base_url(entry)}: {exc}")
            return 1
        entry["models"] = [model.name for model in discovered]
        entry["models_discovered"] = True
        picked = _pick_default(discovered)
        if picked is not None:
            entry["default_model"] = picked.name
            if args.context_length is None and picked.context_length:
                entry["context_length"] = picked.context_length
    models = _entry_models(entry)
    if models and not entry.get("default_model"):
        entry["default_model"] = models[0]
    default_model = str(entry.get("default_model") or (models[0] if models else ""))
    _apply_use(config, args.slug, entry, default_model if args.use else None)
    _save_config(config)
    print(f"Updated provider '{args.slug}'.")
    return 0


def _cmd_remove(args: argparse.Namespace) -> int:
    config = _load_config()
    providers = _provider_map(config)
    if args.slug not in providers:
        print(f"Unknown provider: {args.slug}")
        return 1
    model_cfg = config.get("model") if isinstance(config.get("model"), dict) else {}
    if str(model_cfg.get("provider") or "") == args.slug and not args.force:
        print(f"'{args.slug}' is the current provider; switch first or pass --force.")
        return 1
    del providers[args.slug]
    if str(model_cfg.get("provider") or "") == args.slug:
        for key in ("provider", "default", "base_url", "api_key", "ollama_num_ctx"):
            model_cfg.pop(key, None)
        print("Cleared the main model route; choose a new model with `hermes model`.")
    _save_config(config)
    print(f"Removed provider '{args.slug}'.")
    return 0


def _cmd_use(args: argparse.Namespace) -> int:
    config = _load_config()
    providers = _provider_map(config)
    entry = providers.get(args.slug)
    if not isinstance(entry, dict):
        print(f"Unknown provider: {args.slug}")
        return 1
    models = _entry_models(entry)
    model = args.model or str(entry.get("default_model") or "") or (models[0] if models else "")
    if not model:
        print(f"Provider '{args.slug}' has no models; add one with "
              f"`hermes providers edit {args.slug} --model <id>`.")
        return 1
    _apply_use(config, args.slug, entry, model)
    _save_config(config)
    context = entry.get("context_length")
    suffix = f" (context {context})" if context else ""
    print(f"Main model -> {args.slug} / {model}{suffix}")
    if context and int(context) < _MIN_AGENT_CONTEXT:
        print(f"Warning: {context} < {_MIN_AGENT_CONTEXT} required for agentic compression; "
              "raise the model's num_ctx or set a larger context_length.")
    print("Takes effect in new sessions; restart long-running sessions to pick it up.")
    return 0


def _apply_use(config: dict, slug: str, entry: dict, model: str | None) -> None:
    if not model:
        return
    model_cfg = config.get("model")
    if not isinstance(model_cfg, dict):
        model_cfg = {}
        config["model"] = model_cfg
    base_url = _entry_base_url(entry)
    model_cfg.update({
        "provider": slug,
        "default": model,
        "base_url": base_url,
        "api_key": str(entry.get("api_key") or ""),
    })
    context = entry.get("context_length")
    if context and _is_local_ollama(base_url):
        model_cfg["ollama_num_ctx"] = context


_ACTIONS = {
    "list": _cmd_list, "ls": _cmd_list,
    "scan": _cmd_scan,
    "add": _cmd_add,
    "edit": _cmd_edit,
    "remove": _cmd_remove, "rm": _cmd_remove,
    "use": _cmd_use,
}
