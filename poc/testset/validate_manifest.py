#!/usr/bin/env python3
"""Validate the PoC test-set manifest (spec: poc-evaluation, "Representative test set"). Stdlib only."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

DIRECTIONS = ("bn-BD>ar-SA", "ar-SA>bn-BD")
CATEGORIES = ("greetings", "directions", "shopping", "food_ordering", "workplace", "numbers_prices_dates", "general")
REQUIRED_CATEGORIES = CATEGORIES[:-1]  # "general" is allowed but not required
REQUIRED_TAGS = {"bn-BD>ar-SA": {"formal", "informal"}, "ar-SA>bn-BD": {"saudi_colloquial"}}
REQUIRED_FIELDS = ("id", "direction", "category", "speaker", "accent", "noise", "audio",
                   "reference_transcript", "reference_translation")
MAX_SECONDS = 30.0


def probe_duration(path: Path) -> float | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration:format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            return None
        data = json.loads(out.stdout or "{}")
        if not data.get("streams"):
            return None
        for src in (data["streams"][0], data.get("format", {})):
            if src.get("duration") not in (None, "N/A"):
                return float(src["duration"])
    except (subprocess.SubprocessError, ValueError, OSError):
        return None
    return None


def load(path: Path) -> tuple[list[dict], list[str]]:
    entries, errors = [], []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            errors.append(f"line {n}: invalid JSON")
            continue
        if not isinstance(obj, dict):
            errors.append(f"line {n}: not an object")
            continue
        obj["_line"] = n
        entries.append(obj)
    return entries, errors


def validate(entries: list[dict], min_total: int, min_per_direction: int, audio_dir: Path | None) -> list[str]:
    errors: list[str] = []
    ids = Counter(e.get("id") for e in entries)
    for i, c in ids.items():
        if c > 1:
            errors.append(f"duplicate id: {i}")

    by_dir: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        where = f"line {e['_line']} ({e.get('id')})"
        missing = [f for f in REQUIRED_FIELDS if f not in e]
        if missing:
            errors.append(f"{where}: missing fields {missing}")
            continue
        if e["direction"] not in DIRECTIONS:
            errors.append(f"{where}: bad direction {e['direction']!r}")
            continue
        if e["category"] not in CATEGORIES:
            errors.append(f"{where}: bad category {e['category']!r}")
        if not isinstance(e["noise"], bool):
            errors.append(f"{where}: noise must be true/false")
        for f in ("reference_transcript", "reference_translation", "speaker", "accent", "audio"):
            if not isinstance(e[f], str) or not e[f].strip():
                errors.append(f"{where}: empty {f}")
        by_dir[e["direction"]].append(e)

    if len(entries) < min_total:
        errors.append(f"only {len(entries)} entries (need >= {min_total})")
    for d in DIRECTIONS:
        items = by_dir.get(d, [])
        if len(items) < min_per_direction:
            errors.append(f"{d}: only {len(items)} entries (need >= {min_per_direction})")
        cats = {e["category"] for e in items}
        for c in REQUIRED_CATEGORIES:
            if c not in cats:
                errors.append(f"{d}: no entry for category {c!r}")
        tags = {t for e in items for t in e.get("tags", [])}
        for t in sorted(REQUIRED_TAGS[d] - tags):
            errors.append(f"{d}: no entry tagged {t!r}")
        if len({e["accent"] for e in items}) < 2:
            errors.append(f"{d}: fewer than 2 accents")
        if not any(e["noise"] is True for e in items):
            errors.append(f"{d}: no noisy clip")

    if audio_dir is not None:
        for e in entries:
            if "audio" not in e:
                continue
            p = audio_dir / e["audio"]
            if not p.is_file():
                errors.append(f"{e.get('id')}: audio file missing ({e['audio']})")
                continue
            dur = probe_duration(p)
            if dur is None:
                errors.append(f"{e.get('id')}: audio not decodable")
            elif dur > MAX_SECONDS:
                errors.append(f"{e.get('id')}: audio {dur:.1f}s > {MAX_SECONDS:.0f}s")
    return errors


def summary(entries: list[dict]) -> str:
    lines = []
    for d in DIRECTIONS:
        items = [e for e in entries if e.get("direction") == d]
        cats = Counter(e.get("category") for e in items)
        lines.append(f"{d}: {len(items)} entries, accents={sorted({e['accent'] for e in items if isinstance(e.get('accent'), str)})}, "
                     f"noisy={sum(1 for e in items if e.get('noise') is True)}, categories={dict(cats)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--audio-dir", type=Path, default=None)
    ap.add_argument("--min-total", type=int, default=100)
    ap.add_argument("--min-per-direction", type=int, default=50)
    a = ap.parse_args(argv)
    entries, errors = load(a.manifest)
    errors += validate(entries, a.min_total, a.min_per_direction, a.audio_dir)
    print(summary(entries))
    if errors:
        print(f"\nFAIL: {len(errors)} problem(s)", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
