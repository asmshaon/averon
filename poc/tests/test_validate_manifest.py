import json
import subprocess

import pytest

import validate_manifest as vm


def _entries(n_per_dir=50):
    out = []
    for d, tags, accents in (("bn-BD>ar-SA", ["formal", "informal"], ["dhaka", "sylhet"]),
                             ("ar-SA>bn-BD", ["saudi_colloquial"], ["najdi", "hijazi"])):
        for i in range(n_per_dir):
            out.append({
                "id": f"{d[:2]}-{i:03d}", "direction": d,
                "category": vm.CATEGORIES[i % len(vm.CATEGORIES)],
                "tags": [tags[i % len(tags)]], "speaker": f"spk{i % 5}", "accent": accents[i % 2],
                "noise": i % 7 == 0, "audio": f"{d[:2]}-{i:03d}.wav",
                "reference_transcript": "x", "reference_translation": "y",
            })
    return out


def _write(tmp_path, entries):
    p = tmp_path / "manifest.jsonl"
    p.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8")
    return p


def test_valid_manifest_passes(tmp_path):
    assert vm.main([str(_write(tmp_path, _entries()))]) == 0


@pytest.mark.parametrize("breaker,needle", [
    (lambda es: es[:-1], "only 49 entries"),
    (lambda es: es + [dict(es[0])], "duplicate id"),
    (lambda es: [dict(e, category="general") if e["direction"] == "bn-BD>ar-SA" and e["category"] == "shopping"
                 else e for e in es], "no entry for category 'shopping'"),
    (lambda es: [dict(e, tags=[]) if e["direction"] == "ar-SA>bn-BD" else e for e in es],
     "no entry tagged 'saudi_colloquial'"),
    (lambda es: [dict(e, tags=["formal"]) if e["direction"] == "bn-BD>ar-SA" else e for e in es],
     "no entry tagged 'informal'"),
    (lambda es: [dict(e, accent="dhaka") if e["direction"] == "bn-BD>ar-SA" else e for e in es],
     "fewer than 2 accents"),
    (lambda es: [dict(e, noise=False) for e in es], "no noisy clip"),
    (lambda es: [dict(es[0], reference_translation=" ")] + es[1:], "empty reference_translation"),
    (lambda es: [dict(es[0], direction="en>ar")] + es[1:], "bad direction"),
    (lambda es: [{k: v for k, v in es[0].items() if k != "accent"}] + es[1:], "missing fields"),
])
def test_broken_manifest_fails(tmp_path, capsys, breaker, needle):
    assert vm.main([str(_write(tmp_path, breaker(_entries())))]) == 1
    assert needle in capsys.readouterr().err


def test_audio_checks(tmp_path, capsys):
    es = _entries()
    audio = tmp_path / "audio"
    audio.mkdir()
    ok = audio / "ok.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "sine=duration=1", str(ok)],
                   check=True)
    long = audio / "long.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "sine=duration=31", str(long)],
                   check=True)
    (audio / "bad.wav").write_bytes(b"not audio at all")
    for e in es:
        e["audio"] = "ok.wav"
    es[0]["audio"], es[1]["audio"], es[2]["audio"] = "long.wav", "bad.wav", "missing.wav"
    assert vm.main([str(_write(tmp_path, es)), "--audio-dir", str(audio)]) == 1
    err = capsys.readouterr().err
    assert "31.0s > 30s" in err and "not decodable" in err and "audio file missing" in err
    assert err.count("- ") == 3
