"""Runtime configuration from environment variables (overridable by CLI flags)."""

from __future__ import annotations

import os
from dataclasses import dataclass

SUPPORTED_LANGUAGES = ("bn-BD", "ar-SA")
# Whisper language codes. Always forced, never auto-detected (design D4).
WHISPER_LANGUAGE = {"bn-BD": "bn", "ar-SA": "ar"}
MAX_AUDIO_SECONDS = 30.0


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    stt_url: str
    llm_url: str
    stt_model_id: str
    llm_model_id: str
    stt_timeout: float
    translation_timeout: float
    total_timeout: float

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            stt_url=os.environ.get("AVERON_STT_URL", "http://whisper:8080").rstrip("/"),
            llm_url=os.environ.get("AVERON_LLM_URL", "http://llama:8080").rstrip("/"),
            stt_model_id=os.environ.get("AVERON_STT_MODEL_ID", "unknown-stt"),
            llm_model_id=os.environ.get("AVERON_LLM_MODEL_ID", "unknown-llm"),
            stt_timeout=_float("AVERON_STT_TIMEOUT", 90.0),
            translation_timeout=_float("AVERON_TRANSLATION_TIMEOUT", 60.0),
            total_timeout=_float("AVERON_TOTAL_TIMEOUT", 180.0),
        )
