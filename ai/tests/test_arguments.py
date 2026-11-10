import pytest

BASE = ["--turn-id", "t1"]


@pytest.mark.parametrize("argv", [
    BASE + ["--text", "hi", "--source", "en-US", "--target", "ar-SA"],
    BASE + ["--text", "hi", "--source", "bn-BD", "--target", "ar-EG"],
    BASE + ["--text", "hi", "--source", "bn-BD", "--target", "bn-BD"],
    BASE + ["--text", "hi", "--audio", "/x.wav", "--source", "bn-BD", "--target", "ar-SA"],
    BASE + ["--source", "bn-BD", "--target", "ar-SA"],
    ["--text", "hi", "--source", "bn-BD", "--target", "ar-SA"],
    BASE + ["--text", "   ", "--source", "bn-BD", "--target", "ar-SA"],
    BASE + ["--text", "hi", "--source", "bn-BD", "--target", "ar-SA", "--stt-timeout", "abc"],
])
def test_invalid_arguments(env, run, whisper, llama, argv):
    code, res, _ = run(*argv)
    assert code == 2
    assert res["status"] == "failed"
    assert res["error_code"] == "invalid_arguments"
    assert res["retryable"] is False
    assert whisper.requests == [] and llama.requests == []


def test_turn_id_and_languages_echoed_on_failure(env, run):
    code, res, _ = run("--turn-id", "abc-123", "--text", "x", "--source", "bn-BD", "--target", "bn-BD")
    assert res["turn_id"] == "abc-123"
    assert res["source_language"] == "bn-BD"
