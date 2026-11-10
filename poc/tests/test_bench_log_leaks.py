"""Criterion C11: the harness scans runner stderr for transcript/translation text."""

import run_bench

ENTRY = {"id": "bn2ar-001", "direction": "bn-BD>ar-SA", "category": "greetings", "accent": "dhaka",
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
