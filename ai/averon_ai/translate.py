"""Translation client for llama.cpp `llama-server` (OpenAI-compatible chat completions)."""

from __future__ import annotations

import re

from .errors import RunnerError
from .http import HttpFailure, post_json
from .prompts import Prompt

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_QUOTES = "\"'“”‘’«»「」"
_LABEL = re.compile(r"^(translation|অনুবাদ|الترجمة)\s*[:：]\s*", re.IGNORECASE)


def clean_translation(raw: str) -> str:
    text = _THINK.sub("", raw)
    text = text.split("</think>")[-1]  # unterminated think block
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    line = _LABEL.sub("", lines[0]).strip()
    return line.strip(_QUOTES).strip()


def max_tokens_for(text: str) -> int:
    return max(64, min(512, 64 + 2 * len(text)))


def build_request(prompt: Prompt, text: str, model: str, dialect: str | None) -> dict:
    return {
        "model": model,
        "messages": prompt.messages(text, dialect),
        "temperature": 0.2,
        "top_p": 0.9,
        "max_tokens": max_tokens_for(text),
        "stream": False,
        # Qwen3-style models: disable "thinking" (design D6). Ignored by templates without it.
        "chat_template_kwargs": {"enable_thinking": False},
    }


def translate(base_url: str, prompt: Prompt, text: str, model: str, dialect: str | None, timeout: float) -> str:
    payload = build_request(prompt, text, model, dialect)
    try:
        data = post_json(f"{base_url}/v1/chat/completions", payload, timeout)
    except HttpFailure as e:
        raise RunnerError(f"translation_{e.kind}", e.detail) from None
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RunnerError("translation_failed", "unexpected_response") from None
    if not isinstance(content, str):
        raise RunnerError("translation_failed", "unexpected_response")
    out = clean_translation(content)
    if not out:
        raise RunnerError("translation_failed", "empty_output")
    return out
