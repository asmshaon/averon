#!/usr/bin/env python3
"""Aggregate completed review sheets (task 7.3) into poc/reports/review.md (+ review.json).

  import_reviews.py completed/bn2ar__e2e__reviewerA.csv completed/bn2ar__e2e__reviewerB.csv ...

The file name must start with the sheet name (`bn2ar__e2e`, ...) and end with `__<reviewer>.csv`.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = HERE.parent / "reports"


def _yn(v: str) -> bool | None:
    v = (v or "").strip().lower()
    return True if v in ("y", "yes", "1", "true") else False if v in ("n", "no", "0", "false") else None


def _score(v: str) -> int | None:
    try:
        n = int(float((v or "").strip()))
    except ValueError:
        return None
    return n if 1 <= n <= 5 else None


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def load_reviews(paths: list[Path]) -> tuple[list[dict], list[str]]:
    reviews, problems = [], []
    for p in paths:
        stem = p.stem
        if "__" not in stem or stem.count("__") < 2:
            problems.append(f"{p.name}: expected <sheet>__<reviewer>.csv")
            continue
        sheet, reviewer = stem.rsplit("__", 1)
        with p.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                r = {"sheet": sheet, "reviewer": reviewer, "row_id": row.get("row_id"),
                     "adequacy": _score(row.get("adequacy_1to5", "")),
                     "fluency": _score(row.get("fluency_1to5", "")),
                     "acceptable": _yn(row.get("acceptable_Y_N", "")),
                     "standard_arabic": _yn(row.get("standard_arabic_Y_N", "")) if "standard_arabic_Y_N" in row else None}
                if r["acceptable"] is None:
                    problems.append(f"{p.name} {r['row_id']}: missing/invalid acceptable")
                reviews.append(r)
    return reviews, problems


def aggregate(key: list[dict], reviews: list[dict]) -> list[dict]:
    by_row: dict[str, list[dict]] = defaultdict(list)
    for r in reviews:
        by_row[r["row_id"]].append(r)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for k in key:
        groups[(k["sheet"], k["direction"], k["kind"], k.get("stt_model"), k.get("llm_model"), k.get("variant"),
                k.get("prompt_version"))].append(k)
    out = []
    for (sheet, direction, kind, stt, llm, variant, prompt), entries in sorted(groups.items(), key=lambda x: str(x[0])):
        reviewed = [e for e in entries if e["row_id"] and by_row.get(e["row_id"])]
        failed = [e for e in entries if not e["row_id"]]
        if not reviewed and not failed:
            continue
        # per utterance: majority of reviewers (ties count as not acceptable)
        verdicts: list[tuple[dict, bool]] = [(e, False) for e in failed]
        acc_votes = []
        disagreements = 0
        multi = 0
        for e in reviewed:
            votes = [r["acceptable"] for r in by_row[e["row_id"]] if r["acceptable"] is not None]
            if len(votes) > 1:
                multi += 1
                disagreements += len(set(votes)) > 1
            ok = sum(votes) > len(votes) / 2 if votes else False
            acc_votes.append(ok)
            verdicts.append((e, ok))
        all_r = [r for e in reviewed for r in by_row[e["row_id"]]]
        msa = [r["standard_arabic"] for r in all_r if r["standard_arabic"] is not None]
        total = len(reviewed) + len(failed)
        out.append({
            "sheet": sheet, "direction": direction, "kind": kind, "stt_model": stt, "llm_model": llm,
            "variant": variant, "prompt_version": prompt,
            "utterances": total, "reviewed": len(reviewed), "failed_turns": len(failed),
            "reviewers": sorted({r["reviewer"] for r in all_r}),
            # failed turns count as not acceptable (spec: failures surface, they don't vanish)
            "acceptable_rate": (sum(acc_votes) / total) if total else None,
            "adequacy_mean": _mean([r["adequacy"] for r in all_r]),
            "fluency_mean": _mean([r["fluency"] for r in all_r]),
            "standard_arabic_rate": (sum(msa) / len(msa)) if msa else None,
            "reviewer_disagreement_rate": (disagreements / multi) if multi else None,
            "slices": slices(verdicts),
        })
    return out


SLICE_DIMS = ("category", "accent", "noise")


def slices(verdicts: list[tuple[dict, bool]]) -> dict:
    """Acceptable rate per category / accent / noise group (criteria C9, C10). Failed turns count as not acceptable."""
    out: dict[str, dict] = {}
    for dim in SLICE_DIMS:
        groups: dict[str, list[bool]] = defaultdict(list)
        for e, ok in verdicts:
            if e.get(dim) is not None:
                groups[str(e[dim]).lower()].append(ok)
        out[dim] = {g: {"n": len(v), "acceptable": sum(v), "acceptable_rate": sum(v) / len(v)}
                    for g, v in sorted(groups.items())}
    return out


def _pct(v):
    return "–" if v is None else f"{v * 100:.0f}%"


def _num(v):
    return "–" if v is None else f"{v:.2f}"


def to_markdown(rows: list[dict], problems: list[str]) -> str:
    out = ["# Native-speaker review", "",
           "Acceptable rate = utterances judged acceptable by the reviewer majority ÷ all utterances in the group "
           "(failed turns count as not acceptable; ties count as not acceptable).", "",
           "| Sheet | Models | Variant | n | failed | acceptable | adequacy | fluency | standard Arabic | disagreement | reviewers |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        models = " + ".join(m for m in (r["stt_model"], r["llm_model"]) if m)
        out.append(f"| {r['sheet']} | {models} | {r['variant'] or '–'} | {r['utterances']} | {r['failed_turns']} | "
                   f"{_pct(r['acceptable_rate'])} | {_num(r['adequacy_mean'])} | {_num(r['fluency_mean'])} | "
                   f"{_pct(r['standard_arabic_rate']) if r['direction'] == 'bn-BD>ar' else 'n/a'} | "
                   f"{_pct(r['reviewer_disagreement_rate'])} | {', '.join(r['reviewers'])} |")
    sliced = [r for r in rows if any(r["slices"].get(d) for d in SLICE_DIMS)]
    if sliced:
        out += ["", "## Acceptable rate by slice (criteria C9, C10)", "",
                "Groups with fewer than 5 utterances are shown but are too small to judge on their own.", "",
                "| Sheet | Models | Variant | Slice | n | acceptable |", "|---|---|---|---|---|---|"]
        for r in sliced:
            models = " + ".join(m for m in (r["stt_model"], r["llm_model"]) if m)
            for dim in SLICE_DIMS:
                for g, v in r["slices"].get(dim, {}).items():
                    out.append(f"| {r['sheet']} | {models} | {r['variant'] or '–'} | {dim}={g} | {v['n']} | "
                               f"{v['acceptable']}/{v['n']} ({_pct(v['acceptable_rate'])}) |")
    if problems:
        out += ["", "## Import problems", ""] + [f"- {p}" for p in problems]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheets", type=Path, nargs="+")
    ap.add_argument("--key", type=Path, default=HERE / "keys" / "key.json")
    ap.add_argument("--out", type=Path, default=REPORTS)
    a = ap.parse_args(argv)
    key = json.loads(a.key.read_text(encoding="utf-8"))
    reviews, problems = load_reviews(a.sheets)
    known = {k["row_id"] for k in key if k["row_id"]}
    problems += [f"unknown row_id {r['row_id']} in sheet {r['sheet']}" for r in reviews if r["row_id"] not in known]
    rows = aggregate(key, reviews)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "review.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (a.out / "review.md").write_text(to_markdown(rows, problems), encoding="utf-8")
    print(to_markdown(rows, problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
