"""`run_turn` command: process one turn and print exactly one JSON object to stdout (spec: ai-runner)."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from typing import NoReturn

from . import CONTRACT_VERSION, audio, logs, prompts, stt, translate
from .config import SUPPORTED_LANGUAGES, Settings
from .errors import ERROR_CODES, RunnerError, exit_code_for


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:  # never let argparse print to stdout/exit on its own
        raise RunnerError("invalid_arguments", "argparse")


def _parser() -> argparse.ArgumentParser:
    p = _Parser(prog="run_turn.py", description=__doc__, add_help=True)
    p.add_argument("--turn-id", required=True)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--audio", help="path to the validated input audio file")
    src.add_argument("--text", help="translation-only: source text instead of audio")
    p.add_argument("--source", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--dialect", default=None, help="override the default dialect instruction")
    p.add_argument("--stt-timeout", type=float, default=None)
    p.add_argument("--translation-timeout", type=float, default=None)
    p.add_argument("--total-timeout", type=float, default=None)
    p.add_argument("--verbose", action="store_true")
    return p


def _ms(start: float) -> int:
    return int(round((time.monotonic() - start) * 1000))


class _Turn:
    def __init__(self, turn_id: str | None, source: str | None, target: str | None) -> None:
        self.result: dict = {
            "contract_version": CONTRACT_VERSION,
            "turn_id": turn_id,
            "status": "failed",
            "source_language": source,
            "target_language": target,
            "transcription": None,
            "translation": None,
            "models": {"stt": None, "translation": None, "prompt_version": None},
            "timings_ms": {},
            "audio_duration_seconds": None,
            "error_code": None,
            "retryable": False,
            "usage": [],
        }

    def usage(self, operation: str, model: str, ms: int, units: float, unit: str) -> None:
        self.result["usage"].append({
            "provider": "local",
            "operation": operation,
            "model": model,
            "processing_time_ms": ms,
            "input_units": units,
            "input_unit": unit,
            "estimated_cost": 0,
        })


def _remaining(deadline: float, stage_timeout: float, stage: str) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise RunnerError(f"{stage}_timeout", "total_timeout")
    return min(stage_timeout, left)


def _process(args: argparse.Namespace, turn: _Turn, settings: Settings) -> None:
    if args.source not in SUPPORTED_LANGUAGES or args.target not in SUPPORTED_LANGUAGES:
        raise RunnerError("invalid_arguments", "unsupported_language")
    if args.source == args.target:
        raise RunnerError("invalid_arguments", "same_language")
    if args.text is not None and not args.text.strip():
        raise RunnerError("invalid_arguments", "empty_text")

    stt_timeout = args.stt_timeout or settings.stt_timeout
    tr_timeout = args.translation_timeout or settings.translation_timeout
    deadline = time.monotonic() + (args.total_timeout or settings.total_timeout)
    prompt = prompts.load(args.source, args.target)
    r = turn.result
    r["models"]["prompt_version"] = prompt.id
    timings = r["timings_ms"]

    if args.audio is not None:
        with tempfile.TemporaryDirectory(prefix="averon-") as work:
            t = time.monotonic()
            prepared = audio.prepare(args.audio, work, timeout=min(30.0, deadline - time.monotonic()))
            timings["audio_prep"] = _ms(t)
            r["audio_duration_seconds"] = prepared.duration_seconds
            logs.event("audio_prepared", turn_id=args.turn_id, ms=timings["audio_prep"],
                       duration_s=prepared.duration_seconds, silent=prepared.is_silent)
            if prepared.is_silent:
                raise RunnerError("transcription_empty", "digital_silence")

            r["models"]["stt"] = settings.stt_model_id
            t = time.monotonic()
            text = stt.transcribe(settings.stt_url, prepared.wav_path, args.source,
                                  _remaining(deadline, stt_timeout, "stt"))
            timings["stt"] = _ms(t)
            turn.usage("stt", settings.stt_model_id, timings["stt"], prepared.duration_seconds, "audio_seconds")
            logs.event("stt_done", turn_id=args.turn_id, ms=timings["stt"], model=settings.stt_model_id,
                       chars=len(text))
            if not text:
                raise RunnerError("transcription_empty", "no_speech")
        # temp WAV removed here; the caller owns (and deletes) the original input file.
    else:
        text = args.text.strip()
    r["transcription"] = text

    r["models"]["translation"] = settings.llm_model_id
    t = time.monotonic()
    out = translate.translate(settings.llm_url, prompt, text, settings.llm_model_id, args.dialect,
                              _remaining(deadline, tr_timeout, "translation"))
    timings["translation"] = _ms(t)
    turn.usage("translation", settings.llm_model_id, timings["translation"], len(text), "characters")
    logs.event("translation_done", turn_id=args.turn_id, ms=timings["translation"],
               model=settings.llm_model_id, prompt=prompt.id, chars=len(out))
    r["translation"] = out
    r["status"] = "completed"


def _peek(argv: list[str], flag: str) -> str | None:
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return None


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if any(a in ("-h", "--help") for a in argv):
        _parser().print_help(sys.stderr)
        return 0
    logs.configure(verbose="--verbose" in argv)
    start = time.monotonic()
    turn = _Turn(_peek(argv, "--turn-id"), _peek(argv, "--source"), _peek(argv, "--target"))
    try:
        args = _parser().parse_args(argv)
        _process(args, turn, Settings.from_env())
    except RunnerError as e:
        turn.result["error_code"] = e.code
        turn.result["retryable"] = e.retryable
        logs.event("turn_failed", turn_id=turn.result["turn_id"], error_code=e.code, detail=e.detail or None)
    except Exception as e:  # noqa: BLE001 - always emit a result; log the type only (messages may hold user text)
        turn.result["error_code"] = "internal_error"
        turn.result["retryable"] = ERROR_CODES["internal_error"]
        logs.event("turn_failed", turn_id=turn.result["turn_id"], error_code="internal_error",
                   exception=type(e).__name__)
    turn.result["timings_ms"]["total"] = _ms(start)
    if turn.result["status"] == "completed":
        logs.event("turn_completed", turn_id=turn.result["turn_id"], total_ms=turn.result["timings_ms"]["total"])
    sys.stdout.write(json.dumps(turn.result, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return exit_code_for(turn.result["error_code"])
