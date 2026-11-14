import time

ARGS = ["--turn-id", "a1", "--source", "bn-BD", "--target", "ar"]


def test_valid_m4a_completes(env, run, clips, whisper, llama):
    code, res, _ = run(*ARGS, "--audio", str(clips["speech_m4a"]))
    assert code == 0, res
    assert res["status"] == "completed"
    assert 1.9 <= res["audio_duration_seconds"] <= 2.2
    # whisper received 16 kHz mono PCM WAV
    body = whisper.requests[0]
    assert b"RIFF" in body and b"WAVE" in body


def test_just_under_30s_accepted(env, run, clips):
    code, res, _ = run(*ARGS, "--audio", str(clips["exact30_wav"]))
    assert code == 0, res


def test_over_30s_rejected_before_stt(env, run, clips, whisper, llama):
    code, res, _ = run(*ARGS, "--audio", str(clips["long_wav"]))
    assert res["error_code"] == "audio_too_long"
    assert code == 3
    assert whisper.requests == [] and llama.requests == []


def test_mislabelled_non_audio(env, run, clips, whisper):
    code, res, _ = run(*ARGS, "--audio", str(clips["garbage_wav"]))
    assert res["error_code"] == "audio_unreadable"
    assert whisper.requests == []


def test_empty_file_unreadable(env, run, clips):
    _, res, _ = run(*ARGS, "--audio", str(clips["empty_file"]))
    assert res["error_code"] == "audio_unreadable"


def test_missing_file_unreadable(env, run, tmp_path):
    _, res, _ = run(*ARGS, "--audio", str(tmp_path / "nope.wav"))
    assert res["error_code"] == "audio_unreadable"


def test_zero_length_audio_empty(env, run, clips, whisper):
    _, res, _ = run(*ARGS, "--audio", str(clips["zero_wav"]))
    assert res["error_code"] == "audio_empty"
    assert whisper.requests == []


def test_silent_audio_transcription_empty_without_calls(env, run, clips, whisper, llama):
    code, res, _ = run(*ARGS, "--audio", str(clips["silent_wav"]))
    assert res["error_code"] == "transcription_empty"
    assert res["retryable"] is False
    assert whisper.requests == [] and llama.requests == []


def test_temp_wav_removed(env, run, clips, tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    import tempfile
    monkeypatch.setattr(tempfile, "tempdir", None)
    run(*ARGS, "--audio", str(clips["speech_m4a"]))
    assert list(tmp_path.iterdir()) == []
    assert clips["speech_m4a"].exists()  # caller-owned input is not deleted
