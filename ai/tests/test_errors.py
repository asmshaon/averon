import pytest

from averon_ai.errors import ERROR_CODES, RunnerError, exit_code_for

EXPECTED_RETRYABLE = {"stt_unavailable", "stt_timeout", "translation_unavailable", "translation_timeout"}


def test_fixed_error_code_set():
    assert set(ERROR_CODES) == {
        "invalid_arguments", "audio_unreadable", "audio_empty", "audio_too_long",
        "stt_unavailable", "stt_timeout", "stt_failed", "transcription_empty",
        "translation_unavailable", "translation_timeout", "translation_failed", "internal_error",
    }


@pytest.mark.parametrize("code", sorted(ERROR_CODES))
def test_retryable_and_exit_code(code):
    err = RunnerError(code)
    assert err.retryable is (code in EXPECTED_RETRYABLE)
    expected_exit = 2 if code == "invalid_arguments" else (4 if code in EXPECTED_RETRYABLE else 3)
    assert exit_code_for(code) == expected_exit


def test_success_exit_code():
    assert exit_code_for(None) == 0


def test_unknown_code_rejected():
    with pytest.raises(ValueError):
        RunnerError("made_up")


def test_unexpected_exception_still_emits_json(env, run, monkeypatch):
    import averon_ai.cli as cli

    def boom(*a, **k):
        raise RuntimeError("secret user text must not leak")

    monkeypatch.setattr(cli.prompts, "load", boom)
    code, res, err = run("--turn-id", "t", "--text", "x", "--source", "bn-BD", "--target", "ar-SA")
    assert code == 3
    assert res["error_code"] == "internal_error"
    assert "secret user text" not in err
