"""Custom provider + local Ollama management.

Registers only an operator-facing CLI surface (``hermes providers``); no model
tools, so the per-call tool schema stays unchanged.
"""

from __future__ import annotations

from .cli import build_parser, providers_command


def register(ctx) -> None:
    ctx.register_cli_command(
        name="providers",
        help="Manage model providers and discover local Ollama models",
        setup_fn=build_parser,
        handler_fn=providers_command,
        description=(
            "List, add, edit, remove, or activate custom OpenAI-compatible "
            "providers. 'scan' discovers models on a local Ollama endpoint, "
            "including context length and tool-calling support."
        ),
    )
