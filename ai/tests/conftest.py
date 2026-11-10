from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from averon_ai.cli import main  # noqa: E402

BN_TRANSCRIPT = "আমি বাজারে যেতে চাই"
AR_TRANSLATION = "أبغى أروح السوق"


class FakeService:
    """Configurable stand-in for whisper-server / llama-server."""

    def __init__(self) -> None:
        self.mode = "ok"          # ok | delay | http500 | http503 | badjson
        self.delay = 0.0
        self.payload: dict = {}
        self.requests: list[bytes] = []
        svc = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence
                pass

            def do_GET(self):
                self._reply(200, {"status": "ok"})

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                svc.requests.append(body)
                if svc.mode == "delay":
                    time.sleep(svc.delay)
                if svc.mode == "http500":
                    return self._reply(500, {"error": "boom"})
                if svc.mode == "http503":
                    return self._reply(503, {"status": "loading model"})
                if svc.mode == "badjson":
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"not json")
                    return
                self._reply(200, svc.payload)

            def _reply(self, code, data):
                raw = json.dumps(data, ensure_ascii=False).encode()
                try:
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def whisper():
    s = FakeService()
    s.payload = {"text": f" {BN_TRANSCRIPT}\n"}
    yield s
    s.close()


@pytest.fixture
def llama():
    s = FakeService()
    s.payload = {"choices": [{"message": {"role": "assistant", "content": AR_TRANSLATION}}]}
    yield s
    s.close()


@pytest.fixture
def closed_port_url():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"


@pytest.fixture
def env(monkeypatch, whisper, llama):
    monkeypatch.setenv("AVERON_STT_URL", whisper.url)
    monkeypatch.setenv("AVERON_LLM_URL", llama.url)
    monkeypatch.setenv("AVERON_STT_MODEL_ID", "whisper-test")
    monkeypatch.setenv("AVERON_LLM_MODEL_ID", "llm-test")
    monkeypatch.setenv("AVERON_STT_TIMEOUT", "5")
    monkeypatch.setenv("AVERON_TRANSLATION_TIMEOUT", "5")
    monkeypatch.setenv("AVERON_TOTAL_TIMEOUT", "20")
    return monkeypatch


def _ffmpeg(args: list[str], out: Path) -> Path:
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", *args, str(out)], check=True)
    return out


@pytest.fixture(scope="session")
def clips(tmp_path_factory):
    d = tmp_path_factory.mktemp("clips")
    tone = "sine=frequency=440:sample_rate=44100"
    zero = d / "zero.wav"
    with wave.open(str(zero), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"")
    garbage = d / "clip.wav"
    garbage.write_bytes(b"RIFF\x00\x00garbage-not-audio" * 50)
    empty = d / "empty.m4a"
    empty.write_bytes(b"")
    return {
        "speech_m4a": _ffmpeg(["-f", "lavfi", "-i", f"{tone}:duration=2", "-c:a", "aac"], d / "speech.m4a"),
        "long_wav": _ffmpeg(["-f", "lavfi", "-i", f"{tone}:duration=31"], d / "long.wav"),
        "exact30_wav": _ffmpeg(["-f", "lavfi", "-i", f"{tone}:duration=29.9"], d / "exact30.wav"),
        "silent_wav": _ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-t", "2"], d / "silent.wav"),
        "zero_wav": zero,
        "garbage_wav": garbage,
        "empty_file": empty,
    }


@pytest.fixture
def run(capsys):
    """Run the CLI in-process; return (exit_code, result_dict, stderr)."""

    def _run(*argv: str):
        code = main(list(argv))
        out, err = capsys.readouterr()
        lines = [ln for ln in out.splitlines() if ln.strip()]
        assert len(lines) == 1, f"expected exactly one JSON line on stdout, got: {out!r}"
        return code, json.loads(lines[0]), err

    return _run
