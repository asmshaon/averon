"""Minimal HTTP client (stdlib) with normalized failure kinds."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
import uuid


class HttpFailure(Exception):
    """kind is one of: unavailable, timeout, failed."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(kind)
        self.kind = kind
        self.detail = detail


def _send(req: urllib.request.Request, timeout: float) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        # 503 = model still loading / overloaded: transient.
        kind = "unavailable" if e.code in (502, 503, 504) else "failed"
        raise HttpFailure(kind, f"http_status={e.code}") from None
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise HttpFailure("timeout", "timeout") from None
        raise HttpFailure("unavailable", f"connect_error={type(reason).__name__}") from None
    except (TimeoutError, socket.timeout):
        raise HttpFailure("timeout", "timeout") from None
    except (ConnectionError, OSError) as e:
        raise HttpFailure("unavailable", f"connect_error={type(e).__name__}") from None
    try:
        data = json.loads(body)
    except ValueError:
        raise HttpFailure("failed", "invalid_json") from None
    if not isinstance(data, dict):
        raise HttpFailure("failed", "unexpected_json")
    return data


def post_json(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _send(req, timeout)


def post_multipart(url: str, fields: dict[str, str], file_field: str, filename: str, content: bytes,
                   content_type: str, timeout: float) -> dict:
    boundary = uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    chunks.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n".encode()
    )
    chunks.append(content)
    chunks.append(f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        url,
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    return _send(req, timeout)
