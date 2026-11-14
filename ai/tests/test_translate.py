import json
import time

import pytest

from averon_ai import prompts
from averon_ai.translate import clean_translation
from conftest import AR_TRANSLATION

TEXT = ["--turn-id", "m1", "--text", "আমি বাজারে যেতে চাই"]


def _request(llama):
    return json.loads(llama.requests[-1])


def test_translation_only_mode(env, run, whisper):
    code, res, _ = run(*TEXT, "--source", "bn-BD", "--target", "ar")
    assert code == 0
    assert res["transcription"] == "আমি বাজারে যেতে চাই"
    assert res["translation"] == AR_TRANSLATION
    assert res["models"]["stt"] is None
    assert whisper.requests == []


def test_msa_instruction_sent(env, run, llama):
    run(*TEXT, "--source", "bn-BD", "--target", "ar")
    system = _request(llama)["messages"][0]["content"]
    assert "Modern Standard Arabic" in system and "Do NOT use a regional dialect" in system
    assert "Saudi Arabia" not in system  # no country framing for the output


def test_former_ar_sa_code_rejected(env, run, llama):
    code, res, _ = run(*TEXT, "--source", "bn-BD", "--target", "ar-SA")
    assert code == 2 and res["error_code"] == "invalid_arguments"
    assert llama.requests == []


def test_contract_version_is_1_1(env, run):
    _, res, _ = run(*TEXT, "--source", "bn-BD", "--target", "ar")
    assert res.get("contract_version") == "1.1"


def test_bangladeshi_bangla_instruction_for_bn_target(env, run, llama):
    run("--turn-id", "m2", "--text", "هذا بكم؟", "--source", "ar", "--target", "bn-BD")
    system = _request(llama)["messages"][0]["content"]
    assert "Bangladesh" in system


def test_dialect_override_replaces_default(env, run, llama):
    run(*TEXT, "--source", "bn-BD", "--target", "ar", "--dialect", "Use very simple, short Modern Standard Arabic.")
    system = _request(llama)["messages"][0]["content"]
    assert "Use very simple, short Modern Standard Arabic." in system
    assert prompts.load("bn-BD", "ar").default_dialect not in system


def test_request_shape(env, run, llama):
    run(*TEXT, "--source", "bn-BD", "--target", "ar")
    req = _request(llama)
    assert req["model"] == "llm-test"
    assert req["chat_template_kwargs"] == {"enable_thinking": False}
    assert req["temperature"] <= 0.3
    assert 64 <= req["max_tokens"] <= 512
    assert req["messages"][-1] == {"role": "user", "content": "আমি বাজারে যেতে চাই"}


def test_prompt_version_reported(env, run):
    _, res, _ = run(*TEXT, "--source", "bn-BD", "--target", "ar")
    assert res["models"]["prompt_version"] == "bn-BD__ar@v2"


@pytest.mark.parametrize("raw,expected", [
    ("أبغى أروح السوق", "أبغى أروح السوق"),
    ('"أبغى أروح السوق"', "أبغى أروح السوق"),
    ("<think>\nlet me think\n</think>\n\nأبغى أروح السوق", "أبغى أروح السوق"),
    ("</think>أبغى أروح السوق", "أبغى أروح السوق"),
    ("Translation: أريد أن أذهب إلى السوق\n(Note: Modern Standard Arabic)", "أريد أن أذهب إلى السوق"),
    ("«এটার দাম কত?»", "এটার দাম কত?"),
    ("   \n\n", ""),
])
def test_clean_translation(raw, expected):
    assert clean_translation(raw) == expected


def test_empty_model_output_fails(env, run, llama):
    llama.payload = {"choices": [{"message": {"content": "<think></think>\n"}}]}
    code, res, _ = run(*TEXT, "--source", "bn-BD", "--target", "ar")
    assert res["error_code"] == "translation_failed" and code == 3


def test_unexpected_response_fails(env, run, llama):
    llama.payload = {"foo": 1}
    _, res, _ = run(*TEXT, "--source", "bn-BD", "--target", "ar")
    assert res["error_code"] == "translation_failed"


def test_translation_unavailable(env, run, closed_port_url):
    env.setenv("AVERON_LLM_URL", closed_port_url)
    code, res, _ = run(*TEXT, "--source", "bn-BD", "--target", "ar")
    assert res["error_code"] == "translation_unavailable"
    assert res["retryable"] is True and code == 4


def test_translation_timeout_bounded(env, run, llama):
    llama.mode, llama.delay = "delay", 3
    t = time.monotonic()
    code, res, _ = run(*TEXT, "--source", "bn-BD", "--target", "ar", "--translation-timeout", "0.5")
    assert res["error_code"] == "translation_timeout" and code == 4
    assert time.monotonic() - t < 2.5


def test_total_timeout_caps_stage(env, run, llama):
    llama.mode, llama.delay = "delay", 3
    t = time.monotonic()
    _, res, _ = run(*TEXT, "--source", "bn-BD", "--target", "ar", "--total-timeout", "0.5")
    assert res["error_code"] == "translation_timeout"
    assert time.monotonic() - t < 2.5
