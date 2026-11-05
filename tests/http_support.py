"""Raw HTTP client for the request hardening tests (SPEC-0013, DEC-018).

A standard HTTP client merges or rejects duplicated headers and would neutralize the payloads, so the tests send
the exact bytes through a TCP socket and read the answer until the server closes the connection.
"""

from __future__ import annotations

import contextlib
import json
import socket
import time
from dataclasses import dataclass
from typing import Any

HEADER_END = b"\r\n\r\n"


@dataclass(frozen=True)
class RawReply:
    """What came back: parsed status line, headers (lower case names), body, the raw bytes, the wait, and closure."""

    status: int | None
    headers: dict[str, str]
    body: bytes
    raw: bytes
    elapsed: float
    closed: bool


def exchange(port: int, data: bytes, *, timeout: float = 5.0) -> RawReply:
    """Send exactly ``data`` to ``127.0.0.1:port`` and read until the server closes or ``timeout`` expires."""
    started = time.monotonic()
    chunks: list[bytes] = []
    closed = False
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        with contextlib.suppress(OSError):  # the server may answer and close before reading everything
            sock.sendall(data)
        try:
            while chunk := sock.recv(65536):
                chunks.append(chunk)
            closed = True
        except ConnectionResetError:
            closed = True
        except TimeoutError:
            closed = False
    raw = b"".join(chunks)
    status, headers, body = _parse(raw)
    return RawReply(
        status=status, headers=headers, body=body, raw=raw, elapsed=time.monotonic() - started, closed=closed
    )


def json_body(reply: RawReply) -> Any:
    """Decode the JSON body of ``reply``."""
    return json.loads(reply.body)


def _parse(raw: bytes) -> tuple[int | None, dict[str, str], bytes]:
    head, separator, body = raw.partition(HEADER_END)
    if not separator:
        return None, {}, b""
    lines = head.decode("iso-8859-1").split("\r\n")
    parts = lines[0].split(" ", 2)
    status = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else None
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()
    return status, headers, body
