"""Benchmark helper: speech-to-text only (design D7 "STT sweep"). Not part of the Laravel contract.

python -m averon_ai.probe_stt --audio FILE --source bn-BD   -> one JSON line on stdout
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time

from . import audio, logs, stt
from .config import SUPPORTED_LANGUAGES, Settings
from .errors import RunnerError, exit_code_for


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--source", required=True, choices=SUPPORTED_LANGUAGES)
    a = ap.parse_args(argv)
    logs.configure()
    s = Settings.from_env()
    res: dict = {"status": "failed", "model": s.stt_model_id, "transcription": None,
                 "audio_duration_seconds": None, "timings_ms": {}, "error_code": None}
    try:
        with tempfile.TemporaryDirectory(prefix="averon-") as work:
            t = time.monotonic()
            prepared = audio.prepare(a.audio, work)
            res["timings_ms"]["audio_prep"] = int((time.monotonic() - t) * 1000)
            res["audio_duration_seconds"] = prepared.duration_seconds
            if prepared.is_silent:
                raise RunnerError("transcription_empty", "digital_silence")
            t = time.monotonic()
            text = stt.transcribe(s.stt_url, prepared.wav_path, a.source, s.stt_timeout)
            res["timings_ms"]["stt"] = int((time.monotonic() - t) * 1000)
            if not text:
                raise RunnerError("transcription_empty", "no_speech")
            res["transcription"] = text
            res["status"] = "completed"
    except RunnerError as e:
        res["error_code"] = e.code
    print(json.dumps(res, ensure_ascii=False))
    return exit_code_for(res["error_code"])


if __name__ == "__main__":
    sys.exit(main())
