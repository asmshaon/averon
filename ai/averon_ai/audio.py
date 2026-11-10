"""Audio validation and normalization. Duration and readability come from decoded content only;
the file name and any caller metadata are ignored (spec: ai-runner, "Audio limits enforced from content")."""

from __future__ import annotations

import array
import os
import subprocess
import wave
from dataclasses import dataclass

from .config import MAX_AUDIO_SECONDS
from .errors import RunnerError

SAMPLE_RATE = 16000
MIN_AUDIO_SECONDS = 0.1
# Peak below this (int16) is treated as digital silence: no speech to transcribe.
SILENCE_PEAK = 33
FFMPEG_TIMEOUT = 30.0


@dataclass(frozen=True)
class PreparedAudio:
    wav_path: str
    duration_seconds: float
    is_silent: bool


def prepare(input_path: str, work_dir: str, timeout: float = FFMPEG_TIMEOUT) -> PreparedAudio:
    """Decode any supported input into 16 kHz mono PCM WAV and validate it."""
    if not os.path.isfile(input_path) or not os.access(input_path, os.R_OK):
        raise RunnerError("audio_unreadable", "not_a_readable_file")

    out = os.path.join(work_dir, "input-16k.wav")
    # Decode at most MAX+1 seconds: enough to tell "too long" without decoding huge files.
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", input_path,
        "-t", str(MAX_AUDIO_SECONDS + 1),
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", "-f", "wav",
        out,
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RunnerError("audio_unreadable", "decode_timeout") from None
    except FileNotFoundError:
        raise RunnerError("internal_error", "ffmpeg_missing") from None
    if proc.returncode != 0 or not os.path.isfile(out):
        raise RunnerError("audio_unreadable", f"ffmpeg_exit={proc.returncode}")

    try:
        with wave.open(out, "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            pcm = w.readframes(frames)
    except (wave.Error, EOFError):
        raise RunnerError("audio_unreadable", "invalid_wav") from None

    duration = frames / float(rate) if rate else 0.0
    if duration < MIN_AUDIO_SECONDS:
        raise RunnerError("audio_empty", "no_samples")
    if duration > MAX_AUDIO_SECONDS:
        raise RunnerError("audio_too_long", f"duration_gt_{int(MAX_AUDIO_SECONDS)}")

    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) - (len(pcm) % 2)])
    peak = max((abs(s) for s in samples), default=0)
    return PreparedAudio(wav_path=out, duration_seconds=round(duration, 3), is_silent=peak < SILENCE_PEAK)
