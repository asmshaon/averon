import time

from conftest import BN_TRANSCRIPT

ARGS = ["--turn-id", "s1", "--source", "bn-BD", "--target", "ar-SA"]


def test_forced_language_sent(env, run, clips, whisper):
    run(*ARGS, "--audio", str(clips["speech_m4a"]))
    body = whisper.requests[0]
    assert b'name="language"\r\n\r\nbn\r\n' in body


def test_arabic_source_forces_ar(env, run, clips, whisper):
    run("--turn-id", "s2", "--source", "ar-SA", "--target", "bn-BD", "--audio", str(clips["speech_m4a"]))
    assert b'name="language"\r\n\r\nar\r\n' in whisper.requests[0]


def test_transcript_returned(env, run, clips):
    _, res, _ = run(*ARGS, "--audio", str(clips["speech_m4a"]))
    assert res["transcription"] == BN_TRANSCRIPT
    assert res["models"]["stt"] == "whisper-test"


def test_blank_audio_marker_is_empty(env, run, clips, whisper, llama):
    whisper.payload = {"text": " [BLANK_AUDIO]\n"}
    _, res, _ = run(*ARGS, "--audio", str(clips["speech_m4a"]))
    assert res["error_code"] == "transcription_empty"
    assert llama.requests == []


def test_stt_unavailable(env, run, clips, closed_port_url, llama):
    env.setenv("AVERON_STT_URL", closed_port_url)
    code, res, _ = run(*ARGS, "--audio", str(clips["speech_m4a"]))
    assert res["error_code"] == "stt_unavailable"
    assert res["retryable"] is True and code == 4
    assert llama.requests == []


def test_stt_loading_503_is_unavailable(env, run, clips, whisper):
    whisper.mode = "http503"
    _, res, _ = run(*ARGS, "--audio", str(clips["speech_m4a"]))
    assert res["error_code"] == "stt_unavailable"


def test_stt_timeout_bounded(env, run, clips, whisper):
    whisper.mode, whisper.delay = "delay", 3
    t = time.monotonic()
    code, res, _ = run(*ARGS, "--audio", str(clips["speech_m4a"]), "--stt-timeout", "0.5")
    assert res["error_code"] == "stt_timeout" and code == 4
    assert time.monotonic() - t < 2.5


def test_stt_server_error(env, run, clips, whisper):
    whisper.mode = "http500"
    code, res, _ = run(*ARGS, "--audio", str(clips["speech_m4a"]))
    assert res["error_code"] == "stt_failed" and code == 3


def test_stt_error_payload(env, run, clips, whisper):
    whisper.payload = {"error": "failed to process audio"}
    _, res, _ = run(*ARGS, "--audio", str(clips["speech_m4a"]))
    assert res["error_code"] == "stt_failed"


def test_stt_bad_json(env, run, clips, whisper):
    whisper.mode = "badjson"
    _, res, _ = run(*ARGS, "--audio", str(clips["speech_m4a"]))
    assert res["error_code"] == "stt_failed"


def test_probe_stt_only(env, clips, whisper, llama, capsys):
    import json
    from averon_ai import probe_stt
    code = probe_stt.main(["--audio", str(clips["speech_m4a"]), "--source", "bn-BD"])
    res = json.loads(capsys.readouterr().out)
    assert code == 0 and res["transcription"] == BN_TRANSCRIPT and "stt" in res["timings_ms"]
    assert llama.requests == []


import pytest  # noqa: E402

from averon_ai.stt import clean_transcript  # noqa: E402


@pytest.mark.parametrize("raw,expected", [
    (" ...", ""), ("[BLANK_AUDIO]", ""), ("(music) ♪♪", ""), (" - ", ""),
    (" আমি  [noise] যাব ", "আমি যাব"), ("هذا بكم؟", "هذا بكم؟"), ("৫০ টাকা", "৫০ টাকা"),
])
def test_clean_transcript(raw, expected):
    assert clean_transcript(raw) == expected


def test_punctuation_only_transcript_is_empty(env, run, clips, whisper, llama):
    whisper.payload = {"text": " ...\n"}
    _, res, _ = run(*ARGS, "--audio", str(clips["speech_m4a"]))
    assert res["error_code"] == "transcription_empty"
    assert llama.requests == []
