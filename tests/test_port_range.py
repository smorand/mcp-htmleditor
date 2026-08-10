"""find_free_port(): several presentations coexisting without a colliding default port."""

from __future__ import annotations

import socket

import pytest

from mcp_htmleditor.config import PORT_RANGE_END, PORT_RANGE_START
from mcp_htmleditor.http_server import find_free_port


def test_returns_the_preferred_port_when_free() -> None:
    """No collision: the preferred port itself is returned."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    assert find_free_port("127.0.0.1", free_port) == free_port


def test_falls_back_into_the_range_when_preferred_is_taken() -> None:
    """The preferred port is occupied: falls back into 7840-7849, skipping the occupied one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        occupied.bind(("127.0.0.1", PORT_RANGE_START))
        occupied.listen(1)

        result = find_free_port("127.0.0.1", PORT_RANGE_START)

        assert result != PORT_RANGE_START
        assert PORT_RANGE_START <= result <= PORT_RANGE_END


def test_two_presentations_get_two_different_ports() -> None:
    """Simulates two independent processes each auto-picking a port: no collision."""
    port_a = find_free_port("127.0.0.1", PORT_RANGE_START)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock_a:
        sock_a.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock_a.bind(("127.0.0.1", port_a))
        sock_a.listen(1)

        port_b = find_free_port("127.0.0.1", PORT_RANGE_START)

        assert port_b != port_a
        assert PORT_RANGE_START <= port_b <= PORT_RANGE_END


def test_raises_a_clear_error_when_the_whole_range_is_taken() -> None:
    """All 10 slots occupied (preferred + full range): a clear RuntimeError, no silent fallback."""
    sockets = []
    try:
        for candidate_port in [PORT_RANGE_START - 1, *range(PORT_RANGE_START, PORT_RANGE_END + 1)]:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", candidate_port))
            sock.listen(1)
            sockets.append(sock)

        with pytest.raises(RuntimeError, match="No free port available"):
            find_free_port("127.0.0.1", PORT_RANGE_START - 1)
    finally:
        for sock in sockets:
            sock.close()
