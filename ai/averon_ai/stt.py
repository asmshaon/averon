"""Speech-to-text client for whisper.cpp `whisper-server` (POST /inference)."""

from __future__ import annotations

import re

from .config import WHISPER_LANGUAGE
from .errors import RunnerError
from .http import HttpFailure, post_multipart

# Non-speech markers Whisper emits for silence/noise, e.g. [BLANK_AUDIO], (music), [Music].
_MARKERS = re.compile(r"\[[^\]]*\]|\([^)]*\)|♪+")


def clean_transcript(text: str) -> str:
    """Strip non-speech markers. Output with no letters or digits (e.g. "...", "-") counts as empty:
    Whisper emits such fragments for noise without speech."""
    text = re.sub(r"\s+", " ", _MARKERS.sub(" ", text)).strip()
    return text if any(c.isalnum() for c in text) else ""


def transcribe(base_url: str, wav_path: str, language: str, timeout: float) -> str:
    with open(wav_path, "rb") as f:
        content = f.read()
    fields = {
        "language": WHISPER_LANGUAGE[language],
        "response_format": "json",
        "temperature": "0.0",
        "no_timestamps": "true",
    }
    try:
        data = post_multipart(f"{base_url}/inference", fields, "file", "audio.wav", content, "audio/wav", timeout)
    except HttpFailure as e:
        raise RunnerError(f"stt_{e.kind}", e.detail) from None
    if "error" in data or not isinstance(data.get("text"), str):
        raise RunnerError("stt_failed", "error_response")
    # May be empty: the caller records usage for the executed stage, then raises transcription_empty.
    return clean_transcript(data["text"])
