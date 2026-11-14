#!/usr/bin/env python3
"""Export completed e2e translations into samples.json for the TTS check (design D9).

  python3 scripts/export_samples.py ../bench/results/<run>/results.jsonl [--per-language 10]
"""

import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("results", type=Path)
ap.add_argument("--per-language", type=int, default=10)
a = ap.parse_args()
picked: dict[str, list[dict]] = {"ar": [], "bn-BD": []}
for line in a.results.read_text(encoding="utf-8").splitlines():
    r = json.loads(line) if line.strip() else None
    if r and r.get("status") == "completed" and r.get("translation"):
        bucket = picked[r["target_language"]]
        if len(bucket) < a.per_language:
            bucket.append({"id": r["id"], "language": r["target_language"], "text": r["translation"]})
out = Path(__file__).resolve().parents[1] / "samples.json"
out.write_text(json.dumps({"source": str(a.results.name), "samples": picked["ar"] + picked["bn-BD"]},
                          ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote {out}: {len(picked['ar'])} ar, {len(picked['bn-BD'])} bn-BD")
