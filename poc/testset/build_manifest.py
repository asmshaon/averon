#!/usr/bin/env python3
"""Build manifest.jsonl from the prompt list and a recordings sheet (tasks 4.1 / 4.3). Stdlib only.

  build_manifest.py --prompts prompts.draft.jsonl --recordings recordings.csv --out manifest.jsonl
  build_manifest.py --plan recordings.csv --speakers bn:spk01,bn:spk02,ar:spk03   # blank sheet to fill in

recordings.csv columns: prompt_id, speaker, accent, noise (yes/no), audio (file name in the audio dir).
One row per recording. A prompt read by several speakers gives several manifest entries
(`bn2ar-001-spk03`). Only prompts with review_status "approved" and a non-empty reference_translation
are used: AI drafts never become references.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REC_COLS = ("prompt_id", "speaker", "accent", "noise", "audio")
TRUE, FALSE = {"y", "yes", "true", "1"}, {"n", "no", "false", "0"}


def load_prompts(path: Path) -> dict[str, dict]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            p = json.loads(line)
            out[p["id"]] = p
    return out


def build(prompts: dict[str, dict], recordings: list[dict]) -> tuple[list[dict], list[str]]:
    entries, problems, seen = [], [], set()
    for n, r in enumerate(recordings, 2):  # line 1 is the header
        where = f"recordings line {n}"
        missing = [c for c in REC_COLS if not (r.get(c) or "").strip()]
        if missing:
            problems.append(f"{where}: empty {missing}")
            continue
        pid, speaker = r["prompt_id"].strip(), r["speaker"].strip()
        p = prompts.get(pid)
        if p is None:
            problems.append(f"{where}: unknown prompt_id {pid!r}")
            continue
        if p.get("review_status") != "approved" or not (p.get("reference_translation") or "").strip():
            problems.append(f"{where}: prompt {pid} has no approved native-speaker reference_translation")
            continue
        noise = r["noise"].strip().lower()
        if noise not in TRUE | FALSE:
            problems.append(f"{where}: noise must be yes/no, got {r['noise']!r}")
            continue
        eid = f"{pid}-{speaker}"
        if eid in seen:
            problems.append(f"{where}: {speaker} recorded {pid} twice")
            continue
        seen.add(eid)
        entries.append({
            "id": eid, "direction": p["direction"], "category": p["category"], "tags": p.get("tags", []),
            "speaker": speaker, "accent": r["accent"].strip().lower(), "noise": noise in TRUE,
            "audio": r["audio"].strip(), "reference_transcript": p["reference_transcript"],
            "reference_translation": p["reference_translation"],
        })
    return entries, problems


SPEAKER_LANG = {"bn": "bn-BD", "ar": "ar"}


def write_plan(prompts: dict[str, dict], speakers: list[tuple[str, str]], out: Path) -> int:
    """Blank recordings sheet: every speaker gets every prompt in their own language (source side)."""
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(REC_COLS)
        rows = 0
        for lang, spk in speakers:
            for pid, p in prompts.items():
                if p["direction"].split(">")[0] == SPEAKER_LANG[lang]:
                    w.writerow([pid, spk, "", "", ""])
                    rows += 1
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompts", type=Path, default=Path(__file__).with_name("prompts.draft.jsonl"))
    ap.add_argument("--recordings", type=Path)
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("manifest.jsonl"))
    ap.add_argument("--plan", type=Path, help="write a blank recordings sheet instead of a manifest")
    ap.add_argument("--speakers", default="",
                    help="with --plan: comma-separated LANG:ID, LANG = bn or ar, ID pseudonymous (bn:spk01,ar:spk02)")
    a = ap.parse_args(argv)
    prompts = load_prompts(a.prompts)
    if a.plan:
        speakers = []
        for item in filter(None, (x.strip() for x in a.speakers.split(","))):
            lang, _, spk = item.partition(":")
            if lang not in SPEAKER_LANG or not spk:
                ap.error(f"bad speaker {item!r}: use bn:ID or ar:ID")
            speakers.append((lang, spk))
        if not speakers:
            ap.error("--plan needs --speakers bn:spk01,ar:spk02,...")
        print(f"{write_plan(prompts, speakers, a.plan)} rows -> {a.plan}. Fill in accent/noise/audio and delete "
              "rows a speaker won't record.")
        return 0
    if not a.recordings:
        ap.error("--recordings is required (or use --plan)")
    with a.recordings.open(encoding="utf-8-sig", newline="") as f:
        entries, problems = build(prompts, list(csv.DictReader(f)))
    if problems:
        print(f"FAIL: {len(problems)} problem(s); manifest not written", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    a.out.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
    print(f"{len(entries)} entries -> {a.out}; now run validate_manifest.py on it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
