"""Criterion C11: the harness scans runner stderr for transcript/translation text."""

import run_bench

ENTRY = {"id": "bn2ar-001", "direction": "bn-BD>ar", "category": "greetings", "accent": "dhaka",
         "noise": False, "audio": "x.m4a", "reference_transcript": "আসসালামু আলাইকুম, কেমন আছেন?",
         "reference_translation": "السلام عليكم، كيف حالك؟"}

RESULT = {"status": "completed", "error_code": None, "retryable": False,
          "transcription": "আসসালামু আলাইকুম কেমন আছেন", "translation": "السلام عليكم، كيف حالك؟",
          "models": {"stt": "s", "translation": "l", "prompt_version": "v1"}, "audio_duration_seconds": 2.0,
          "timings_ms": {"total": 10}, "usage": [{"provider": "local", "estimated_cost": 0}]}


class FakeStack:
    def __init__(self, stderr):
        self.stderr = stderr

    def exec_runner(self, args, timeout):
        return dict(RESULT), 0, 12.0, self.stderr


def test_log_leaks_counts_only_content():
    assert run_bench.log_leaks("turn_id=t1 stage=stt ms=900 model=s", ["আসসালামু", None, ""]) == 0
    assert run_bench.log_leaks("debug text=السلام عليكم، كيف حالك؟", ["السلام عليكم، كيف حالك؟"]) == 1
    assert run_bench.log_leaks("ms=12 ok", ["ok"]) == 0  # too short to count


def test_clean_logs_pass_and_leaky_logs_fail_in_summary():
    clean = run_bench.run_turn(FakeStack("turn_id=bn2ar-001 stage=total ms=10 status=completed"), ENTRY, "e2e",
                               "/data", 30)
    leaky = run_bench.run_turn(FakeStack("transcription=" + RESULT["transcription"]), ENTRY, "e2e", "/data", 30)
    assert clean["log_leaks"] == 0 and leaky["log_leaks"] == 1
    s = run_bench.summarize([clean, leaky], "e2e", {"stt_model": "s", "llm_model": "l"}, {}, {})
    assert s["log_content_leaks"] == 1 and s["log_leak_utterances"] == ["bn2ar-001"]
    md = run_bench.summary_markdown([s], "")
    assert "found in runner logs: 1 (**FAIL**" in md
    # the stderr itself is never stored in the row
    assert all(RESULT["transcription"] not in str(v) for k, v in leaky.items()
               if k not in ("transcription", "reference_transcript"))


def test_dialect_variant_only_reaches_bn_to_ar():
    ar_entry = dict(ENTRY, id="ar2bn-001", direction="ar>bn-BD")
    assert run_bench.dialect_for(ENTRY, "Use simple MSA.") == "Use simple MSA."
    assert run_bench.dialect_for(ar_entry, "Use simple MSA.") is None
    assert run_bench.dialect_for(ENTRY, None) is None


def test_variants_file_is_valid():
    import json
    from pathlib import Path
    v = json.loads((Path(run_bench.__file__).parent / "dialect-variants.json").read_text(encoding="utf-8"))
    assert v["default"] is None and all(isinstance(x, str) and "فصحى" in x for k, x in v.items() if k != "default")


def test_arabic_cer_split_by_register():
    def row(i, reg):
        return dict(run_bench.base_row(dict(ENTRY, id=f"ar2bn-{i}", direction="ar>bn-BD", tags=[reg]), "stt"),
                    status="completed", cer=0.1 if reg == "msa" else 0.3, wer=0.2)
    rows = [row(1, "msa"), row(2, "msa"), row(3, "dialect")]
    q = run_bench._quality(rows)["ar"]
    assert q["by_register"]["msa"]["n"] == 2 and abs(q["by_register"]["dialect"]["cer_mean"] - 0.3) < 1e-9
    bn = run_bench._quality([dict(run_bench.base_row(ENTRY, "stt"), status="completed", cer=0.1, wer=0.1)])
    assert bn["bn-BD"]["by_register"] == {}
    md = run_bench.summary_markdown([{"mode": "stt", "stt_model": "s", "utterances": 3, "completed": 3,
                                      "success_rate": 1.0, "error_counts": {}, "external_api_calls": 0,
                                      "estimated_cost": 0, "latency_ms": {}, "resources": {},
                                      "stt_quality": run_bench._quality(rows)}], "")
    assert "register=dialect" in md
