"""Resource profiling of inference containers (design D7): peak RAM from cgroup v2 `memory.peak`,
CPU and memory sampled from `docker stats` about once a second."""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path


def _docker(*args: str) -> str:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=True).stdout.strip()


def _bytes(s: str) -> float:
    units = {"b": 1, "kib": 1024, "kb": 1000, "mib": 1024**2, "mb": 1000**2, "gib": 1024**3, "gb": 1000**3}
    s = s.strip().lower()
    for u in sorted(units, key=len, reverse=True):
        if s.endswith(u):
            return float(s[: -len(u)]) * units[u]
    return float(s or 0)


def cgroup_memory_peak(container_id: str) -> int | None:
    """Read memory.peak (cgroup v2) for the container's cgroup. Works on a Linux Docker host (the VPS);
    returns None on Docker Desktop or cgroup v1."""
    try:
        pid = _docker("inspect", "-f", "{{.State.Pid}}", container_id)
        for line in Path(f"/proc/{pid}/cgroup").read_text().splitlines():
            if line.startswith("0::"):
                peak = Path("/sys/fs/cgroup") / line[3:].lstrip("/") / "memory.peak"
                return int(peak.read_text().strip())
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None
    return None


class Profiler:
    """Samples `docker stats` for the given {service: container_id} until stopped."""

    def __init__(self, containers: dict[str, str], interval: float = 1.0) -> None:
        self.containers = containers
        self.interval = interval
        self.samples: dict[str, list[tuple[float, float]]] = {s: [] for s in containers}  # (cpu%, mem bytes)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def __enter__(self) -> "Profiler":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join(timeout=10)

    def _loop(self) -> None:
        by_id = {cid[:12]: svc for svc, cid in self.containers.items()}
        while not self._stop.is_set():
            try:
                out = _docker("stats", "--no-stream", "--format", "{{json .}}", *self.containers.values())
                for line in out.splitlines():
                    d = json.loads(line)
                    svc = by_id.get(d.get("ID", "")[:12])
                    if svc:
                        cpu = float(d["CPUPerc"].rstrip("%") or 0)
                        mem = _bytes(d["MemUsage"].split("/")[0])
                        self.samples[svc].append((cpu, mem))
            except (subprocess.CalledProcessError, ValueError, KeyError):
                pass
            self._stop.wait(self.interval)

    def summary(self) -> dict:
        out = {}
        for svc, cid in self.containers.items():
            s = self.samples[svc]
            cpus = [c for c, _ in s]
            mems = [m for _, m in s]
            peak = cgroup_memory_peak(cid)
            out[svc] = {
                "peak_mem_bytes": peak if peak is not None else (max(mems) if mems else None),
                "peak_mem_source": "cgroup.memory.peak" if peak is not None else "docker_stats_max",
                "sampled_max_mem_bytes": max(mems) if mems else None,
                "cpu_percent_mean": sum(cpus) / len(cpus) if cpus else None,
                "cpu_percent_max": max(cpus) if cpus else None,
                "samples": len(s),
            }
        return out
