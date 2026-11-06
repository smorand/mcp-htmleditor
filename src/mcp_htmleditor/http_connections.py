"""Open connections of one editor server, so a stop can close the idle ones (SPEC-0014/BR-003, BR-004).

A connection is idle until its request line and headers are complete, busy while that request runs, then idle again.
``close_idle`` marks the registry closing and shuts every idle socket with ``shutdown(SHUT_RDWR)``: that wakes the
handler blocked in ``recv`` with end of stream, which ends the connection silently. Closing the descriptor from the
stopping thread instead would not wake that ``recv``. Busy connections are left alone and answer normally. One lock
covers every change, so a request is either busy before ``close_idle`` (answered) or refused by ``begin_request``
after it (closed), never both.
"""

from __future__ import annotations

import logging
import socket
import threading

logger = logging.getLogger(__name__)


class ConnectionRegistry:
    """Open connections of one editor server and whether each has a request in progress."""

    __slots__ = ("_busy", "_closing", "_lock")

    def __init__(self) -> None:
        self._busy: dict[socket.socket, bool] = {}
        self._closing = False
        self._lock = threading.Lock()

    @property
    def closing(self) -> bool:
        return self._closing

    def add(self, sock: socket.socket) -> None:
        """Register an idle connection; one arriving after ``close_idle`` is shut at once."""
        with self._lock:
            self._busy[sock] = False
            if self._closing:
                _shut(sock)

    def begin_request(self, sock: socket.socket) -> bool:
        """Mark the connection busy; False when closing (the caller closes it without an answer)."""
        with self._lock:
            if self._closing:
                return False
            self._busy[sock] = True
            return True

    def close_idle(self) -> int:
        """Mark the registry closing and shut every idle connection; return how many were shut."""
        with self._lock:
            self._closing = True
            idle = [sock for sock, busy in self._busy.items() if not busy]
            for sock in idle:
                _shut(sock)
            return len(idle)

    def end_request(self, sock: socket.socket) -> bool:
        """Mark the connection idle again; True when closing (the caller closes it after its answer)."""
        with self._lock:
            if sock in self._busy:
                self._busy[sock] = False
            return self._closing

    def remove(self, sock: socket.socket) -> None:
        """Forget the connection; an unknown one is fine."""
        with self._lock:
            self._busy.pop(sock, None)


def _shut(sock: socket.socket) -> None:
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError as exc:
        logger.debug("Connection already closed: %s", type(exc).__name__)
