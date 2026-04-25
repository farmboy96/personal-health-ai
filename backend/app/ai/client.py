"""
LLM clients. Prefer Anthropic when ANTHROPIC_API_KEY is set (Claude); otherwise OpenAI.

Env:
  ANTHROPIC_API_KEY — if set, chat completions route to Claude unless LLM_PROVIDER=openai.
  ANTHROPIC_MODEL — defaults to claude-sonnet-4-20250514 (override for other Claude models).
  ANTHROPIC_MAX_TOKENS — max output tokens (default 8192).
  OPENAI_API_KEY — used when Anthropic is not selected or unavailable.
  LLM_PROVIDER — optional: anthropic | openai (forces routing when both keys exist).
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
_USAGE = {"input_tokens": 0, "output_tokens": 0, "calls": 0}

# Per-million-token pricing (USD) - update if Anthropic changes pricing
_PRICING = {
    "claude-haiku-4-5": {"in": 1.00, "out": 5.00},
    "claude-sonnet-4-5": {"in": 3.00, "out": 15.00},
    "claude-sonnet-4-6": {"in": 3.00, "out": 15.00},
    "claude-opus-4-6": {"in": 15.00, "out": 75.00},
    "claude-opus-4-7": {"in": 15.00, "out": 75.00},
}


def _record_usage(model: str, usage) -> None:
    _USAGE["input_tokens"] += getattr(usage, "input_tokens", 0) or 0
    _USAGE["output_tokens"] += getattr(usage, "output_tokens", 0) or 0
    _USAGE["calls"] += 1


def get_usage_summary() -> dict:
    price = None
    model = _USAGE.get("model") or ""
    for key, p in _PRICING.items():
        if key in model:
            price = p
            break
    cost = None
    if price:
        cost = (_USAGE["input_tokens"] / 1_000_000) * price["in"] + (
            (_USAGE["output_tokens"] / 1_000_000) * price["out"]
        )
    return {**_USAGE, "estimated_cost_usd": cost}


def _llm_provider() -> str:
    explicit = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if explicit in ("anthropic", "openai"):
        return explicit
    if (os.getenv("ANTHROPIC_API_KEY") or "").strip():
        return "anthropic"
    return "openai"


def _map_openai_model_to_anthropic(model: str) -> str:
    """OpenAI-style names from code → Anthropic model id."""
    if (os.getenv("ANTHROPIC_MODEL") or "").strip():
        return os.getenv("ANTHROPIC_MODEL", "").strip()
    m = (model or "").lower()
    if m.startswith("gpt") or m.startswith("o1") or m.startswith("o3"):
        return _DEFAULT_ANTHROPIC_MODEL
    return model or _DEFAULT_ANTHROPIC_MODEL


def _anthropic_messages_create(*, model: str, messages: list[dict[str, Any]]) -> tuple[str, Any, str]:
    from anthropic import Anthropic

    system_parts: list[str] = []
    conv: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role") or "user"
        content = msg.get("content") or ""
        if role == "system":
            system_parts.append(str(content))
        elif role in ("user", "assistant"):
            conv.append({"role": role, "content": content})
        else:
            conv.append({"role": "user", "content": content})

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    amodel = _map_openai_model_to_anthropic(model)
    max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", "8192"))
    kwargs: dict[str, Any] = {
        "model": amodel,
        "max_tokens": max_tokens,
        "messages": conv,
    }
    if system_parts:
        kwargs["system"] = "\n\n".join(system_parts)

    resp = client.messages.create(**kwargs)
    _USAGE["model"] = resp.model
    _record_usage(resp.model, resp.usage)
    out: list[str] = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            out.append(getattr(block, "text", "") or "")
    return "".join(out).strip(), resp.usage, resp.model


def _openai_style_response(text: str, usage: Any = None, model: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        model=model,
        usage=usage,
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=text)),
        ],
    )


class _ChatCompletions:
    @staticmethod
    def create(
        *,
        model: str,
        messages: list,
        **kwargs: Any,
    ) -> SimpleNamespace:
        provider = _llm_provider()
        has_a = bool((os.getenv("ANTHROPIC_API_KEY") or "").strip())
        use_anthropic = provider == "anthropic" and has_a
        if use_anthropic:
            text, usage, actual_model = _anthropic_messages_create(
                model=model,
                messages=list(messages),
            )
            return _openai_style_response(text, usage=usage, model=actual_model)
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "No LLM credentials: set ANTHROPIC_API_KEY (Claude) or OPENAI_API_KEY."
            )
        client = OpenAI(api_key=key)
        return client.chat.completions.create(model=model, messages=messages, **kwargs)


class _Chat:
    completions = _ChatCompletions()


class RoutingClient:
    """drop-in for OpenAI client.chat.completions.create."""

    chat = _Chat()


def get_openai_client():
    """Returns a client with .chat.completions.create — OpenAI or Anthropic-backed."""
    return RoutingClient()
