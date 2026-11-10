#!/usr/bin/env python3
"""PoC benchmark harness (design D7). Run on the VPS host, from the repo checkout.

  run_bench.py stt --model whisper-small-q5_1=ggml-small-q5_1.bin --model whisper-base=ggml-base.bin
  run_bench.py mt  --model qwen3-4b-q4km=Qwen3-4B-Q4_K_M.gguf [--dialect-variants variants.json]
  run_bench.py e2e --stt whisper-small-q5_1=ggml-small-q5_1.bin --llm qwen3-4b-q4km=Qwen3-4B-Q4_K_M.gguf \
                   [--fault llama@10 --fault whisper@20]

Utterances run strictly one at a time through the `ai-runner` container (`docker compose exec`).
Models are swapped by recreating the service with STT_MODEL/LLM_MODEL overrides, which also resets
cgroup memory.peak. Results land in poc/bench/results/<run-id>/: results.jsonl, summary.json, summary.md.
Results contain test-set transcripts/translations (scripted test data, not user data) and stay out of git.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import metrics  # noqa: E402
from profile import Profiler  # noqa: E402

DEPLOY = REPO / "deploy"
LANG_OF = {"bn-BD>ar-SA": ("bn-BD", "ar-SA"), "ar-SA>bn-BD": ("ar-SA", "bn-BD")}


# --------------------------------------------------------------------------- docker helpers

def read_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


class Stack:
    def __init__(self, compose_dir: Path, env_file: Path | None) -> None:
        self.dir = compose_dir
        self.env_file = env_file
        self.overrides: dict[str, str] = {}

    def _compose(self, *args: str, check: bool = True, capture: bool = True,
                 timeout: float | None = None) -> subprocess.CompletedProcess:
        cmd = ["docker", "compose"]
        if self.env_file:
            cmd += ["--env-file", str(self.env_file)]
        cmd += list(args)
        env = {**os.environ, **self.overrides}
        return subprocess.run(cmd, cwd=self.dir, env=env, check=check, text=True,
                              capture_output=capture, timeout=timeout)

    def use(self, services: list[str], **overrides: str) -> None:
        """Recreate services with model overrides and wait until healthy."""
        self.overrides.update(overrides)
        self._compose("up", "-d", "--wait", "--force-recreate", *services, "ai-runner", capture=False)

    def container(self, service: str) -> str:
        return self._compose("ps", "-q", service).stdout.strip()

    def exec_runner(self, args: list[str], timeout: float) -> tuple[dict | None, int, float]:
        t = time.monotonic()
        try:
            p = self._compose("exec", "-T", "ai-runner", "python", *args, check=False, capture=True,
                              timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, -1, (time.monotonic() - t) * 1000
        wall = (time.monotonic() - t) * 1000
        lines = [ln for ln in p.stdout.splitlines() if ln.strip().startswith("{")]
        try:
            return (json.loads(lines[-1]) if lines else None), p.returncode, wall
        except ValueError:
            return None, p.returncode, wall

    def stop(self, service: str) -> None:
        self._compose("stop", service)

    def start(self, service: str) -> None:
        self._compose("start", service)

    def crash_nowait(self, service: str) -> None:
        subprocess.run(["docker", "exec", self.container(service), "sh", "-c", "kill -9 -1"],
                       capture_output=True)

    def wait_healthy(self, service: str, max_wait: float = 300) -> float | None:
        cid = self.container(service)
        t = time.monotonic()
        while time.monotonic() - t < max_wait:
            st = subprocess.run(["docker", "inspect", "-f",
                                 "{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{end}}", cid],
                                capture_output=True, text=True).stdout.strip()
            if st == "running/healthy":
                return time.monotonic() - t
            time.sleep(2)
        return None

    def restart_count(self, service: str) -> int:
        return int(subprocess.run(["docker", "inspect", "-f", "{{.RestartCount}}", self.container(service)],
                                  capture_output=True, text=True).stdout.strip() or 0)


# --------------------------------------------------------------------------- data

def load_manifest(path: Path, limit: int | None, direction: str | None) -> list[dict]:
    items = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if direction:
        items = [e for e in items if e["direction"] == direction]
    if limit:
        # keep both directions represented in dry runs
        by_dir: dict[str, list[dict]] = defaultdict(list)
        for e in items:
            by_dir[e["direction"]].append(e)
        out: list[dict] = []
        while len(out) < limit and any(by_dir.values()):
            for d in list(by_dir):
                if by_dir[d] and len(out) < limit:
                    out.append(by_dir[d].pop(0))
        items = out
    return items


def parse_model(spec: str) -> tuple[str, str]:
    if "=" not in spec:
        raise SystemExit(f"model must be ID=FILE, got {spec!r}")
    mid, f = spec.split("=", 1)
    return mid, f


def model_size(models_dir: Path, file: str) -> int | None:
    p = models_dir / file
    return p.stat().st_size if p.is_file() else None


# --------------------------------------------------------------------------- per-utterance runs

def base_row(e: dict, mode: str) -> dict:
    src, tgt = LANG_OF[e["direction"]]
    return {
        "id": e["id"], "mode": mode, "direction": e["direction"], "source_language": src,
        "target_language": tgt, "category": e["category"], "accent": e["accent"], "noise": e["noise"],
        "tags": e.get("tags", []), "reference_transcript": e["reference_transcript"],
        "reference_translation": e["reference_translation"],
    }


def run_stt(stack: Stack, e: dict, audio_root: str, timeout: float) -> dict:
    row = base_row(e, "stt")
    res, code, wall = stack.exec_runner(
        ["-m", "averon_ai.probe_stt", "--audio", f"{audio_root}/{e['audio']}", "--source", row["source_language"]],
        timeout)
    row.update(harness_wall_ms=round(wall), exit_code=code)
    if res is None:
        row.update(status="failed", error_code="harness_no_result")
        return row
    row.update(status=res["status"], error_code=res["error_code"], transcription=res["transcription"],
               stt_ms=res["timings_ms"].get("stt"), audio_prep_ms=res["timings_ms"].get("audio_prep"),
               audio_duration_seconds=res["audio_duration_seconds"])
    if res["transcription"] is not None:
        row["cer"] = metrics.cer(e["reference_transcript"], res["transcription"])
        row["wer"] = metrics.wer(e["reference_transcript"], res["transcription"])
    return row


def run_turn(stack: Stack, e: dict, mode: str, audio_root: str, timeout: float,
             dialect: str | None = None) -> dict:
    row = base_row(e, mode)
    args = ["run_turn.py", "--turn-id", e["id"], "--source", row["source_language"],
            "--target", row["target_language"]]
    if mode == "mt":
        args += ["--text", e["reference_transcript"]]
    else:
        args += ["--audio", f"{audio_root}/{e['audio']}"]
    if dialect:
        args += ["--dialect", dialect]
    res, code, wall = stack.exec_runner(args, timeout)
    row.update(harness_wall_ms=round(wall), exit_code=code)
    if res is None:
        row.update(status="failed", error_code="harness_no_result")
        return row
    t = res.get("timings_ms", {})
    row.update(
        status=res["status"], error_code=res["error_code"], retryable=res.get("retryable"),
        transcription=res["transcription"], translation=res["translation"], models=res["models"],
        audio_duration_seconds=res.get("audio_duration_seconds"),
        audio_prep_ms=t.get("audio_prep"), stt_ms=t.get("stt"), translation_ms=t.get("translation"),
        total_ms=t.get("total"), usage=res.get("usage", []),
    )
    if mode == "e2e" and res["transcription"] is not None:
        row["cer"] = metrics.cer(e["reference_transcript"], res["transcription"])
        row["wer"] = metrics.wer(e["reference_transcript"], res["transcription"])
    if res["translation"] is not None:
        row["chrf"] = metrics.chrf(e["reference_translation"], res["translation"])
    return row


# --------------------------------------------------------------------------- summaries

def _lat(rows: list[dict], key: str) -> dict:
    xs = [r[key] for r in rows if r.get(key) is not None and r["status"] == "completed"]
    return {"n": len(xs), "median": metrics.percentile(xs, 50), "p95": metrics.percentile(xs, 95),
            "max": max(xs) if xs else None}


def _quality(rows: list[dict]) -> dict:
    out: dict = {}
    by_lang: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_lang[r["source_language"]].append(r)
    for lang, rs in sorted(by_lang.items()):
        scored = [r for r in rs if "cer" in r]
        q = {"n_scored": len(scored),
             "cer_mean": metrics.mean([r["cer"] for r in scored]),
             "wer_mean": metrics.mean([r["wer"] for r in scored])}
        for dim in ("accent", "noise"):
            groups: dict[str, list[dict]] = defaultdict(list)
            for r in scored:
                groups[str(r[dim])].append(r)
            q[f"by_{dim}"] = {g: {"n": len(v), "cer_mean": metrics.mean([x["cer"] for x in v]),
                                  "wer_mean": metrics.mean([x["wer"] for x in v])} for g, v in sorted(groups.items())}
        out[lang] = q
    return out


def _chrf(rows: list[dict]) -> dict:
    out = {}
    for d in LANG_OF:
        rs = [r for r in rows if r["direction"] == d and r.get("translation")]
        out[d] = {"n": len(rs), "corpus_chrf": metrics.corpus_chrf(
            [r["reference_translation"] for r in rs], [r["translation"] for r in rs])}
    return out


def summarize(rows: list[dict], mode: str, label: dict, resources: dict, sizes: dict) -> dict:
    ok = [r for r in rows if r["status"] == "completed"]
    usage = [u for r in rows for u in r.get("usage", [])]
    s = {
        "mode": mode, **label,
        "utterances": len(rows),
        "completed": len(ok),
        "success_rate": len(ok) / len(rows) if rows else None,
        "error_counts": dict(Counter(r["error_code"] for r in rows if r["status"] != "completed")),
        "latency_ms": {k: _lat(rows, k) for k in ("total_ms", "audio_prep_ms", "stt_ms", "translation_ms",
                                                   "harness_wall_ms") if any(k in r for r in rows)},
        "resources": resources,
        "model_file_bytes": sizes,
        "external_api_calls": sum(1 for u in usage if u.get("provider") != "local"),
        "estimated_cost": sum(float(u.get("estimated_cost") or 0) for u in usage),
    }
    if mode in ("stt", "e2e"):
        s["stt_quality"] = _quality(rows)
    if mode in ("mt", "e2e"):
        s["chrf"] = _chrf(rows)
    return s


def _fmt(v, nd=0):
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{v:.{nd}f}" if nd else f"{v:.0f}"
    return str(v)


def summary_markdown(summaries: list[dict], reserve_note: str) -> str:
    out = ["# Benchmark summary", ""]
    for s in summaries:
        out.append(f"## {s['mode']} · " + " · ".join(f"{k}={s[k]}" for k in ("stt_model", "llm_model", "variant")
                                                     if s.get(k)))
        out.append("")
        out.append(f"- Utterances: {s['utterances']}; completed: {s['completed']} "
                   f"({_fmt((s['success_rate'] or 0) * 100, 1)}%)")
        if s["error_counts"]:
            out.append(f"- Failures by code: {s['error_counts']}")
        out.append(f"- External API calls: {s['external_api_calls']}; estimated cost: {s['estimated_cost']}")
        out.append("")
        out.append("| Latency (ms) | n | median | p95 | max |")
        out.append("|---|---|---|---|---|")
        for k, v in s["latency_ms"].items():
            out.append(f"| {k} | {v['n']} | {_fmt(v['median'])} | {_fmt(v['p95'])} | {_fmt(v['max'])} |")
        out.append("")
        out.append("| Service | peak RAM (MiB) | source | CPU mean % | CPU max % |")
        out.append("|---|---|---|---|---|")
        for svc, r in s["resources"].items():
            mib = r["peak_mem_bytes"] / 2**20 if r["peak_mem_bytes"] else None
            out.append(f"| {svc} | {_fmt(mib)} | {r['peak_mem_source']} | {_fmt(r['cpu_percent_mean'])} | "
                       f"{_fmt(r['cpu_percent_max'])} |")
        out.append("")
        out.append("CPU % is per `docker stats`: 100% = one vCPU, so the maximum on the VPS is 200%.")
        if "stt_quality" in s:
            out.append("")
            out.append("| Source language | n | CER | WER |")
            out.append("|---|---|---|---|")
            for lang, q in s["stt_quality"].items():
                out.append(f"| {lang} | {q['n_scored']} | {_fmt(q['cer_mean'], 3)} | {_fmt(q['wer_mean'], 3)} |")
                for dim in ("by_accent", "by_noise"):
                    for g, v in q[dim].items():
                        out.append(f"| ↳ {dim[3:]}={g} | {v['n']} | {_fmt(v['cer_mean'], 3)} | "
                                   f"{_fmt(v['wer_mean'], 3)} |")
        if "chrf" in s:
            out.append("")
            out.append("| Direction | n | corpus chrF (automatic signal only) |")
            out.append("|---|---|---|")
            for d, v in s["chrf"].items():
                out.append(f"| {d} | {v['n']} | {_fmt(v['corpus_chrf'], 1)} |")
        if s.get("faults"):
            out.append("")
            out.append("### Fault injection")
            for f in s["faults"]:
                out.append(f"- {f}")
        out.append("")
    if reserve_note:
        out += ["## Memory headroom", "", reserve_note, ""]
    return "\n".join(out)


# --------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("stt", "mt", "e2e"))
    ap.add_argument("--model", action="append", default=[], help="ID=FILE (stt/mt modes, repeatable)")
    ap.add_argument("--stt", help="ID=FILE (e2e)")
    ap.add_argument("--llm", help="ID=FILE (e2e)")
    ap.add_argument("--dialect-variants", type=Path,
                    help='mt: JSON {"variant-name": "dialect instruction" | null}; null = prompt default')
    ap.add_argument("--fault", action="append", default=[],
                    help="e2e: SERVICE@INDEX: stop SERVICE for utterance INDEX, restart it, then SIGKILL-crash "
                         "it and check the restart policy")
    ap.add_argument("--manifest", type=Path, default=REPO / "poc/testset/manifest.jsonl")
    ap.add_argument("--audio-root", default="/data/audio", help="audio dir as seen inside ai-runner")
    ap.add_argument("--compose-dir", type=Path, default=DEPLOY)
    ap.add_argument("--env-file", type=Path, default=DEPLOY / ".env")
    ap.add_argument("--direction", choices=tuple(LANG_OF))
    ap.add_argument("--limit", type=int, help="dry run on the first N utterances (both directions)")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--reserve-mib", type=int, default=2560,
                    help="memory reserved for OS + MySQL + PHP-FPM + worker (design D3), for the headroom check")
    ap.add_argument("--host-mem-mib", type=int, default=8192)
    ap.add_argument("--out", type=Path, default=HERE / "results")
    a = ap.parse_args(argv)

    env_file = a.env_file if a.env_file.is_file() else None
    models_dir = Path(read_env_file(a.env_file).get("MODELS_DIR", "/opt/averon/models"))
    stack = Stack(a.compose_dir, env_file)
    items = load_manifest(a.manifest, a.limit, a.direction)
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{a.mode}"
    out_dir = a.out / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.jsonl"
    summaries: list[dict] = []

    def record(rows_file, row):
        rows_file.write(json.dumps(row, ensure_ascii=False) + "\n")
        rows_file.flush()
        status = row["status"] if row["status"] == "completed" else f"failed:{row['error_code']}"
        print(f"  {row['id']:<14} {status:<32} {row.get('total_ms') or row.get('stt_ms') or '-'} ms", flush=True)

    with results_path.open("w", encoding="utf-8") as rows_file:
        if a.mode == "stt":
            for mid, f in map(parse_model, a.model):
                print(f"== STT {mid} ({f})", flush=True)
                stack.use(["whisper"], STT_MODEL=f, STT_MODEL_ID=mid)
                rows = []
                with Profiler({"whisper": stack.container("whisper")}) as prof:
                    for e in items:
                        row = run_stt(stack, e, a.audio_root, a.timeout)
                        row["stt_model"] = mid
                        record(rows_file, row)
                        rows.append(row)
                summaries.append(summarize(rows, "stt", {"stt_model": mid}, prof.summary(),
                                           {mid: model_size(models_dir, f)}))

        elif a.mode == "mt":
            variants = {"default": None}
            if a.dialect_variants:
                variants = json.loads(a.dialect_variants.read_text(encoding="utf-8"))
            for mid, f in map(parse_model, a.model):
                print(f"== MT {mid} ({f})", flush=True)
                stack.use(["llama"], LLM_MODEL=f, LLM_MODEL_ID=mid)
                for vname, dialect in variants.items():
                    rows = []
                    with Profiler({"llama": stack.container("llama")}) as prof:
                        for e in items:
                            row = run_turn(stack, e, "mt", a.audio_root, a.timeout, dialect)
                            row.update(llm_model=mid, variant=vname)
                            record(rows_file, row)
                            rows.append(row)
                    summaries.append(summarize(rows, "mt", {"llm_model": mid, "variant": vname}, prof.summary(),
                                               {mid: model_size(models_dir, f)}))

        else:  # e2e
            if not (a.stt and a.llm):
                raise SystemExit("e2e needs --stt ID=FILE and --llm ID=FILE")
            smid, sf = parse_model(a.stt)
            lmid, lf = parse_model(a.llm)
            faults = {}
            for spec in a.fault:
                svc, idx = spec.split("@")
                faults[int(idx)] = svc
            print(f"== E2E {smid} + {lmid}", flush=True)
            stack.use(["whisper", "llama"], STT_MODEL=sf, STT_MODEL_ID=smid, LLM_MODEL=lf, LLM_MODEL_ID=lmid)
            rows, fault_notes = [], []
            with Profiler({"whisper": stack.container("whisper"), "llama": stack.container("llama")}) as prof:
                for i, e in enumerate(items):
                    if i in faults:
                        svc = faults[i]
                        # 1) outage: the service is down while a turn runs -> expect *_unavailable, retryable
                        stack.stop(svc)
                        row = run_turn(stack, e, "e2e", a.audio_root, a.timeout)
                        row.update(stt_model=smid, llm_model=lmid, fault_injected=svc)
                        record(rows_file, row)
                        rows.append(row)
                        stack.start(svc)
                        back = stack.wait_healthy(svc)
                        # 2) crash: SIGKILL the server process -> restart policy must bring it back
                        before = stack.restart_count(svc)
                        stack.crash_nowait(svc)
                        time.sleep(3)
                        recovered = stack.wait_healthy(svc)
                        after = stack.restart_count(svc)
                        fault_notes.append(
                            f"`{svc}` stopped during {e['id']}: turn → {row['status']}/{row['error_code']} "
                            f"(retryable={row.get('retryable')}, exit={row.get('exit_code')}); healthy again "
                            f"{_fmt(back, 1)} s after start. SIGKILL crash: restarts {before}→{after}, healthy after "
                            f"{_fmt(recovered, 1)} s → {'OK' if after > before and recovered is not None else 'FAILED'}")
                        continue
                    row = run_turn(stack, e, "e2e", a.audio_root, a.timeout)
                    row.update(stt_model=smid, llm_model=lmid)
                    record(rows_file, row)
                    rows.append(row)
            clean = [r for r in rows if not r.get("fault_injected")]
            s = summarize(clean, "e2e", {"stt_model": smid, "llm_model": lmid}, prof.summary(),
                          {smid: model_size(models_dir, sf), lmid: model_size(models_dir, lf)})
            s["faults"] = fault_notes
            summaries.append(s)

    reserve_note = ""
    for s in summaries:
        if s["mode"] == "e2e":
            peaks = [r["peak_mem_bytes"] or 0 for r in s["resources"].values()]
            combined = sum(peaks) / 2**20
            budget = a.host_mem_mib - a.reserve_mib
            ok = combined <= budget
            s["headroom"] = {"combined_inference_peak_mib": round(combined), "inference_budget_mib": budget,
                             "reserve_mib": a.reserve_mib, "within_budget": ok}
            reserve_note = (f"Combined inference peak {combined:.0f} MiB vs budget {budget} MiB "
                            f"({a.host_mem_mib} MiB host − {a.reserve_mib} MiB reserve): "
                            f"**{'within budget' if ok else 'OVER BUDGET'}**.")

    (out_dir / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(summary_markdown(summaries, reserve_note), encoding="utf-8")
    print(f"\nresults: {results_path}\nsummary: {out_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
