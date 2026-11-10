import csv
import json

import import_reviews
import make_sheets


def _results(tmp_path, kind, n=6):
    rows = []
    for d in ("bn-BD>ar-SA", "ar-SA>bn-BD"):
        for i in range(n):
            failed = i == n - 1
            rows.append({
                "id": f"{d[:2]}-{i}", "direction": d, "status": "failed" if failed else "completed",
                "error_code": "stt_timeout" if failed else None,
                "reference_transcript": f"src {d[:2]} {i}", "translation": None if failed else f"out {d[:2]} {i}",
                "stt_model": "whisper-secret-model" if kind == "e2e" else None, "llm_model": "llm-secret-model",
                "variant": "default", "models": {"prompt_version": "bn-BD__ar-SA@v1"},
            })
    p = tmp_path / f"{kind}.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def test_sheets_are_blind_and_shuffled(tmp_path):
    out = tmp_path / "review"
    make_sheets.main(["--e2e", str(_results(tmp_path, "e2e")), "--mt", str(_results(tmp_path, "mt")),
                      "--out", str(out), "--seed", "3"])
    names = sorted(p.name for p in out.glob("*.csv"))
    assert names == ["ar2bn__e2e.csv", "ar2bn__reference.csv", "bn2ar__e2e.csv", "bn2ar__reference.csv"]
    for p in out.glob("*.csv"):
        text = p.read_text(encoding="utf-8-sig")
        assert "secret-model" not in text and "@v1" not in text
        assert "bn-" not in text.split("\n", 1)[1].split(",")[0]  # row ids don't leak utterance ids
    header = (out / "bn2ar__e2e.csv").read_text(encoding="utf-8-sig").splitlines()[0]
    assert "sounds_saudi_Y_N" in header
    assert "sounds_saudi_Y_N" not in (out / "ar2bn__e2e.csv").read_text(encoding="utf-8-sig").splitlines()[0]
    rows = list(csv.DictReader((out / "bn2ar__e2e.csv").open(encoding="utf-8-sig")))
    assert len(rows) == 5  # failed turn not on sheet
    assert [r["source_text"] for r in rows] != sorted(r["source_text"] for r in rows)  # shuffled
    key = json.loads((out / "keys" / "key.json").read_text())
    assert sum(1 for k in key if k["row_id"] is None) == 4


def _fill(src, dst, acceptable, saudi="Y"):
    rows = list(csv.DictReader(src.open(encoding="utf-8-sig")))
    with dst.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for i, r in enumerate(rows):
            r.update(adequacy_1to5="4", fluency_1to5="5", acceptable_Y_N=acceptable(i))
            if "sounds_saudi_Y_N" in r:
                r["sounds_saudi_Y_N"] = saudi
            w.writerow(r)


def test_aggregation(tmp_path):
    out = tmp_path / "review"
    make_sheets.main(["--e2e", str(_results(tmp_path, "e2e")), "--out", str(out), "--seed", "1"])
    done = tmp_path / "done"
    done.mkdir()
    _fill(out / "bn2ar__e2e.csv", done / "bn2ar__e2e__revA.csv", lambda i: "Y")
    _fill(out / "bn2ar__e2e.csv", done / "bn2ar__e2e__revB.csv", lambda i: "Y" if i < 4 else "N")
    reports = tmp_path / "reports"
    code = import_reviews.main([str(done / "bn2ar__e2e__revA.csv"), str(done / "bn2ar__e2e__revB.csv"),
                                "--key", str(out / "keys" / "key.json"), "--out", str(reports)])
    assert code == 0
    agg = json.loads((reports / "review.json").read_text())
    (g,) = [r for r in agg if r["sheet"] == "bn2ar__e2e"]
    assert g["utterances"] == 6 and g["failed_turns"] == 1 and g["reviewed"] == 5
    # 4 unanimous Y; 1 tie (Y/N) -> not acceptable; failed turn -> not acceptable => 4/6
    assert abs(g["acceptable_rate"] - 4 / 6) < 1e-9
    assert g["sounds_saudi_rate"] == 1.0
    assert abs(g["reviewer_disagreement_rate"] - 1 / 5) < 1e-9
    assert g["reviewers"] == ["revA", "revB"]
    assert "bn2ar__e2e" in (reports / "review.md").read_text()


def test_invalid_answers_reported(tmp_path):
    out = tmp_path / "review"
    make_sheets.main(["--e2e", str(_results(tmp_path, "e2e")), "--out", str(out), "--seed", "1"])
    done = tmp_path / "done"
    done.mkdir()
    _fill(out / "ar2bn__e2e.csv", done / "ar2bn__e2e__revA.csv", lambda i: "maybe")
    code = import_reviews.main([str(done / "ar2bn__e2e__revA.csv"), "--key", str(out / "keys" / "key.json"),
                                "--out", str(tmp_path / "r")])
    assert code == 1
