import csv
import json

import build_manifest
import validate_manifest

PROMPTS = build_manifest.load_prompts(build_manifest.Path(build_manifest.__file__).with_name("prompts.draft.jsonl"))


def _approved(prompts):
    out = {}
    for pid, p in prompts.items():
        out[pid] = dict(p, review_status="approved", reference_translation="ref " + p["draft_translation"])
    return out


def _sheet(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(build_manifest.REC_COLS)
        w.writerows(rows)


def test_drafts_are_never_references(tmp_path):
    prompts = tmp_path / "p.jsonl"
    prompts.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in PROMPTS.values()), encoding="utf-8")
    rec = tmp_path / "r.csv"
    _sheet(rec, [["bn2ar-001", "spk01", "dhaka", "no", "a.m4a"]])
    out = tmp_path / "m.jsonl"
    assert build_manifest.main(["--prompts", str(prompts), "--recordings", str(rec), "--out", str(out)]) == 1
    assert not out.exists()


def test_full_build_passes_validator(tmp_path):
    prompts = tmp_path / "p.jsonl"
    prompts.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in _approved(PROMPTS).values()),
                       encoding="utf-8")
    rows = []
    for i, pid in enumerate(PROMPTS):
        bn = pid.startswith("bn2ar")
        accent = ("dhaka" if i % 2 else "sylhet") if bn else ("egyptian" if i % 2 else "gulf")
        rows.append([pid, "spk01" if bn else "spk02", accent, "yes" if i % 10 == 0 else "no", f"{pid}.m4a"])
    rows.append(["bn2ar-001", "spk03", "chittagong", "no", "bn2ar-001-b.m4a"])  # second speaker, same prompt
    rec = tmp_path / "r.csv"
    _sheet(rec, rows)
    out = tmp_path / "m.jsonl"
    assert build_manifest.main(["--prompts", str(prompts), "--recordings", str(rec), "--out", str(out)]) == 0
    entries = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 105
    assert {"bn2ar-001-spk01", "bn2ar-001-spk03"} <= {e["id"] for e in entries}
    assert all(e["reference_translation"].startswith("ref ") for e in entries)
    assert validate_manifest.main([str(out)]) == 0


def test_bad_rows_reported(tmp_path, capsys):
    prompts = tmp_path / "p.jsonl"
    prompts.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in _approved(PROMPTS).values()),
                       encoding="utf-8")
    rec = tmp_path / "r.csv"
    _sheet(rec, [["nope-1", "spk01", "dhaka", "no", "a.m4a"],
                 ["bn2ar-002", "spk01", "dhaka", "maybe", "b.m4a"],
                 ["bn2ar-003", "spk01", "", "no", "c.m4a"],
                 ["bn2ar-004", "spk01", "dhaka", "no", "d.m4a"],
                 ["bn2ar-004", "spk01", "dhaka", "no", "d2.m4a"]])
    assert build_manifest.main(["--prompts", str(prompts), "--recordings", str(rec),
                                "--out", str(tmp_path / "m.jsonl")]) == 1
    err = capsys.readouterr().err
    assert "unknown prompt_id" in err and "yes/no" in err and "empty ['accent']" in err and "twice" in err


def test_plan_sheet(tmp_path):
    plan = tmp_path / "plan.csv"
    assert build_manifest.main(["--plan", str(plan), "--speakers", "bn:spk01,bn:spk02,ar:spk03"]) == 0
    rows = list(csv.DictReader(plan.open(encoding="utf-8")))
    assert len(rows) == 3 * 52
    assert {r["prompt_id"][:5] for r in rows if r["speaker"] == "spk03"} == {"ar2bn"}
    assert {r["prompt_id"][:5] for r in rows if r["speaker"] in ("spk01", "spk02")} == {"bn2ar"}
    assert rows[0]["accent"] == ""
