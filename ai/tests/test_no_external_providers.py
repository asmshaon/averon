"""Static guard: the runner package contains no paid/external provider endpoints or SDKs."""

import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "averon_ai"
FORBIDDEN = re.compile(
    r"openai\.com|googleapis\.com|azure|cognitiveservices|anthropic|deepgram|assemblyai|elevenlabs|"
    r"import\s+(openai|google|azure|boto3|requests|httpx)",
    re.IGNORECASE,
)


def test_no_external_provider_references():
    hits = [f"{p.name}: {m.group(0)}" for p in PKG.rglob("*.py") for m in FORBIDDEN.finditer(p.read_text())]
    assert hits == []


def test_default_service_urls_are_private_names():
    from averon_ai.config import Settings
    import os
    for k in ("AVERON_STT_URL", "AVERON_LLM_URL"):
        os.environ.pop(k, None)
    s = Settings.from_env()
    assert s.stt_url == "http://whisper:8080" and s.llm_url == "http://llama:8080"
