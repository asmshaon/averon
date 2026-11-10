"""Normalized error codes (spec: ai-runner, "Normalized error codes")."""

from __future__ import annotations

# code -> retryable (transient)
ERROR_CODES: dict[str, bool] = {
    "invalid_arguments": False,
    "audio_unreadable": False,
    "audio_empty": False,
    "audio_too_long": False,
    "stt_unavailable": True,
    "stt_timeout": True,
    "stt_failed": False,
    "transcription_empty": False,
    "translation_unavailable": True,
    "translation_timeout": True,
    "translation_failed": False,
    "internal_error": False,
}

EXIT_COMPLETED = 0
EXIT_INVALID_ARGUMENTS = 2
EXIT_FAILED = 3
EXIT_RETRYABLE = 4


class RunnerError(Exception):
    """A failure with a normalized code. `detail` is for logs and must never contain user text."""

    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise ValueError(f"unknown error code: {code}")
        super().__init__(code)
        self.code = code
        self.detail = detail

    @property
    def retryable(self) -> bool:
        return ERROR_CODES[self.code]


def exit_code_for(code: str | None) -> int:
    if code is None:
        return EXIT_COMPLETED
    if code == "invalid_arguments":
        return EXIT_INVALID_ARGUMENTS
    return EXIT_RETRYABLE if ERROR_CODES[code] else EXIT_FAILED
