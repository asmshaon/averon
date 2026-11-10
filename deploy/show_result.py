"""Pretty-print the runner's JSON result (used by try.sh). Exit code mirrors the turn status."""
import json
import sys

lines = [ln for ln in sys.stdin.read().splitlines() if ln.strip().startswith("{")]
if not lines:
    print("✘ no result from runner (is the stack up? try: ./try.sh logs)")
    sys.exit(1)
d = json.loads(lines[-1])
ok = d["status"] == "completed"
print()
print("✔ completed" if ok else f"✘ failed: {d['error_code']} (retryable={d['retryable']})")
if d.get("transcription"):
    print(f"  heard      : {d['transcription']}")
if d.get("translation"):
    print(f"  translation: {d['translation']}")
if d.get("audio_duration_seconds"):
    print(f"  audio      : {d['audio_duration_seconds']} s")
print(f"  timings ms : {d['timings_ms']}")
print(f"  models     : {d['models']}")
print(f"  usage      : {[(u['operation'], u['model'], 'cost', u['estimated_cost']) for u in d['usage']]}")
sys.exit(0 if ok else 1)
