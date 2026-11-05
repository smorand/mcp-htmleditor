"""Time bounds of an editor server connection (SPEC-0013/BR-008, BR-009, BR-022).

Every wait on the connection is bounded: ``WAIT_SECONDS`` without a byte received, or without the client taking a
chunk of the answer, ends the wait. Receiving a request is also bounded as a whole: ``TOTAL_SECONDS`` after the first
byte of the connection the request is cut, however steadily bytes keep coming (the total never covers running the
request nor sending the answer). The constants are read through the module object at each use
(``http_deadline.WAIT_SECONDS``) so the test suite can shorten them; production code never reassigns them and they
are not a setting.

Two stdlib behaviors shape this module: a socket file that timed out refuses every later read with an ``OSError``
(so the first timeout must be remembered), and ``socket.sendall`` applies its timeout to the whole call (so the
answer is sent in chunks, each with a fresh wait).
"""

from __future__ import annotations

import io
import socket
import time
from collections.abc import Callable

WAIT_SECONDS: float = 30.0
TOTAL_SECONDS: float = 300.0
WRITE_CHUNK_BYTES = 65_536


class RequestTimeout(Exception):  # noqa: N818 - name fixed by SPEC-0013 DEC-015
    """No byte came for ``WAIT_SECONDS`` while reading a request.

    Deliberately not a ``TimeoutError``: the stdlib ``handle_one_request`` swallows those without an answer.
    ``has_bytes`` tells a connection that sent part of a request from one that sent nothing.
    """

    def __init__(self, *, has_bytes: bool) -> None:
        super().__init__("Request timeout")
        self.has_bytes = has_bytes


class ResponseTimeout(Exception):  # noqa: N818 - name fixed by SPEC-0013 DEC-014
    """The client took no chunk of an answer for ``WAIT_SECONDS``."""


class DeadlineReader:
    """The request side of a connection: every read waits at most ``WAIT_SECONDS`` for the next byte."""

    def __init__(
        self, stream: io.BufferedReader, sock: socket.socket, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._stream = stream
        self._sock = sock
        self._clock = clock
        self._started_at: float | None = None  # clock value at the first byte of the connection
        self._timed_out = False
        self.bytes_received = 0

    @property
    def closed(self) -> bool:
        return self._stream.closed

    def close(self) -> None:
        self._stream.close()

    def read(self, size: int = -1) -> bytes:
        """Read ``size`` bytes (all of them until end of stream when negative), fewer only at end of stream."""
        out = bytearray()
        while size < 0 or len(out) < size:
            peeked = self._peek()
            if not peeked:
                break
            wanted = len(peeked) if size < 0 else min(len(peeked), size - len(out))
            out += self._take(wanted)
        return bytes(out)

    def readline(self, limit: int = -1) -> bytes:
        """Read up to and including ``b"\\n"``, at most ``limit`` bytes when positive, fewer at end of stream."""
        out = bytearray()
        while limit < 0 or len(out) < limit:
            peeked = self._peek()
            if not peeked:
                break
            window = peeked if limit < 0 else peeked[: limit - len(out)]
            newline = window.find(b"\n")
            out += self._take(len(window) if newline < 0 else newline + 1)
            if newline >= 0:
                break
        return bytes(out)

    def _arm(self) -> None:
        """Bound the next wait by the wait bound and by what is left of the total bound; raise when none is left."""
        timeout = WAIT_SECONDS
        if self._started_at is not None:
            remaining = self._started_at + TOTAL_SECONDS - self._clock()
            if remaining <= 0:
                self._timed_out = True
                raise RequestTimeout(has_bytes=True)
            timeout = min(timeout, remaining)
        self._sock.settimeout(timeout)

    def _peek(self) -> bytes:
        """The buffered bytes, after at most one ``recv`` bounded by the wait; ``b""`` at end of stream."""
        if self._timed_out:
            raise RequestTimeout(has_bytes=self.bytes_received > 0)
        self._arm()
        try:
            peeked = self._stream.peek(1)
        except TimeoutError:
            self._timed_out = True
            raise RequestTimeout(has_bytes=self.bytes_received > 0) from None
        if peeked and self._started_at is None:
            self._started_at = self._clock()
        return peeked

    def _take(self, count: int) -> bytes:
        """Take ``count`` bytes already in the buffer: never blocks."""
        data = self._stream.read(count)
        self.bytes_received += len(data)
        return data


class DeadlineWriter:
    """The answer side of a connection: each chunk must be taken by the client within ``WAIT_SECONDS``."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._closed = False
        self._timed_out = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._closed = True

    def flush(self) -> None:
        """Nothing is buffered: every write is sent before it returns."""

    def write(self, data: bytes) -> int:
        """Send ``data`` in chunks; raise ``ResponseTimeout`` when a chunk waits ``WAIT_SECONDS``, and on every write
        after that (the answer is broken, the connection is only good for closing)."""
        view = memoryview(data)
        for start in range(0, len(view), WRITE_CHUNK_BYTES):
            self._send(view[start : start + WRITE_CHUNK_BYTES])
        return len(view)

    def _send(self, chunk: memoryview) -> None:
        if self._timed_out:
            raise ResponseTimeout
        self._sock.settimeout(WAIT_SECONDS)
        try:
            self._sock.sendall(chunk)
        except TimeoutError:
            self._timed_out = True
            raise ResponseTimeout from None
