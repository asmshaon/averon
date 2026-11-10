from conftest import AR_TRANSLATION, BN_TRANSCRIPT

ARGS = ["--turn-id", "u1", "--source", "bn-BD", "--target", "ar-SA"]
REQUIRED_KEYS = {
    "turn_id", "status", "source_language", "target_language", "transcription", "translation",
    "models", "timings_ms", "audio_duration_seconds", "error_code", "retryable", "usage",
}


def test_full_turn_result_shape(env, run, clips):
    code, res, _ = run(*ARGS, "--audio", str(clips["speech_m4a"]))
    assert code == 0
    assert REQUIRED_KEYS <= set(res)
    assert res["status"] == "completed" and res["error_code"] is None
    assert res["models"]["stt"] == "whisper-test" and res["models"]["translation"] == "llm-test"
    assert {"audio_prep", "stt", "translation", "total"} <= set(res["timings_ms"])


def test_usage_entries(env, run, clips):
    _, res, _ = run(*ARGS, "--audio", str(clips["speech_m4a"]))
    ops = {u["operation"]: u for u in res["usage"]}
    assert set(ops) == {"stt", "translation"}
    for u in res["usage"]:
        assert u["provider"] == "local"
        assert u["estimated_cost"] == 0
        assert isinstance(u["processing_time_ms"], int)
    assert ops["stt"]["model"] == "whisper-test"
    assert ops["stt"]["input_unit"] == "audio_seconds" and ops["stt"]["input_units"] > 1.5
    assert ops["translation"]["input_units"] == len(BN_TRANSCRIPT)


def test_usage_only_for_executed_stages(env, run):
    _, res, _ = run(*ARGS, "--text", "এটার দাম কত?")
    assert [u["operation"] for u in res["usage"]] == ["translation"]


def test_no_content_in_stderr_on_success(env, run, clips):
    _, res, err = run(*ARGS, "--audio", str(clips["speech_m4a"]), "--verbose")
    assert "event=turn_completed" in err
    assert BN_TRANSCRIPT not in err and AR_TRANSLATION not in err
    for word in BN_TRANSCRIPT.split() + AR_TRANSLATION.split():
        assert word not in err


def test_no_content_in_stderr_on_failure(env, run, llama):
    llama.payload = {"choices": [{"message": {"content": None}}]}
    _, res, err = run(*ARGS, "--text", "গোপন বার্তা", "--verbose")
    assert res["status"] == "failed"
    assert "গোপন" not in err


def test_only_private_services_contacted(env, run, clips, whisper, llama):
    """No paid/external fallback: a turn makes exactly one STT and one LLM request, nothing else."""
    run(*ARGS, "--audio", str(clips["speech_m4a"]))
    assert len(whisper.requests) == 1 and len(llama.requests) == 1


def test_no_fallback_after_local_failure(env, run, clips, whisper, llama):
    whisper.mode = "http500"
    _, res, _ = run(*ARGS, "--audio", str(clips["speech_m4a"]))
    assert res["status"] == "failed"
    assert len(whisper.requests) == 1 and llama.requests == []


def test_usage_recorded_when_stt_ran_but_found_no_speech(env, run, clips, whisper, llama):
    whisper.payload = {"text": "[BLANK_AUDIO]"}
    _, res, _ = run(*ARGS, "--audio", str(clips["speech_m4a"]))
    assert res["error_code"] == "transcription_empty"
    assert [u["operation"] for u in res["usage"]] == ["stt"]
    assert llama.requests == []
