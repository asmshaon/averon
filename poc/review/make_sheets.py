#!/usr/bin/env python3
"""Generate blinded native-speaker review sheets (design D8, task 7.1).

  make_sheets.py --e2e bench/results/<run>/results.jsonl --mt bench/results/<run>/results.jsonl [--seed 7]

Per direction it writes two CSVs: `<dir>__e2e.csv` (from audio) and `<dir>__reference.csv` (translations of
reference transcripts). Rows are shuffled. Sheets show only the reference source text and the model output, never
the model, run, prompt or utterance ID. A separate key file (review/keys/, git-ignored) maps row IDs back.
Failed turns don't go on the sheets; they are recorded in the key and count as "not acceptable" in the aggregation.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import secrets
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIRS = {"bn-BD>ar-SA": "bn2ar", "ar-SA>bn-BD": "ar2bn"}
SCORE_COLS = ["adequacy_1to5", "fluency_1to5", "acceptable_Y_N"]


def sheet_columns(direction: str) -> list[str]:
    cols = ["row_id", "source_text", "translation", *SCORE_COLS]
    if direction == "bn-BD>ar-SA":
        cols.append("sounds_saudi_Y_N")
    return cols + ["comment"]


def load_rows(paths: list[Path], kind: str) -> list[dict]:
    rows = []
    for p in paths:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                r["_kind"] = kind
                r["_results_file"] = str(p)
                rows.append(r)
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--e2e", type=Path, action="append", default=[])
    ap.add_argument("--mt", type=Path, action="append", default=[])
    ap.add_argument("--out", type=Path, default=HERE)
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args(argv)
    rng = random.Random(a.seed if a.seed is not None else secrets.randbits(32))

    rows = load_rows(a.e2e, "e2e") + load_rows(a.mt, "reference")
    keys_dir = a.out / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    key: list[dict] = []
    for direction, short in DIRS.items():
        for kind in ("e2e", "reference"):
            subset = [r for r in rows if r["direction"] == direction and r["_kind"] == kind]
            if not subset:
                continue
            rng.shuffle(subset)
            name = f"{short}__{kind}"
            with (a.out / f"{name}.csv").open("w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=sheet_columns(direction))
                w.writeheader()
                n = 0
                for r in subset:
                    entry = {"sheet": name, "direction": direction, "kind": kind, "utterance_id": r["id"],
                             "stt_model": r.get("stt_model"), "llm_model": r.get("llm_model"),
                             "variant": r.get("variant"), "prompt_version": (r.get("models") or {}).get("prompt_version"),
                             "status": r["status"], "error_code": r.get("error_code"),
                             "results_file": r["_results_file"], "row_id": None}
                    if r["status"] == "completed" and r.get("translation"):
                        n += 1
                        entry["row_id"] = f"{short[:2].upper()}{kind[0].upper()}-{n:04d}"
                        w.writerow({"row_id": entry["row_id"], "source_text": r["reference_transcript"],
                                    "translation": r["translation"]})
                    key.append(entry)
            print(f"{name}.csv: {n} rows to review ({len(subset) - n} failed turns recorded in key only)")
    (keys_dir / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"key: {keys_dir / 'key.json'} (do not share with reviewers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
