"""find_free_port(): several presentations coexisting without a colliding default port.

A port held by another process counts as taken (SPEC-0014 BR-015, DEC-015). The whole range test binds the real
ports 7839 to 7849 and counts a refused bind as taken; the two others run on a block of free ports found at run time.
"""

from __future__ import annotations

import random
import socket
from collections.abc import Iterator
from contextlib import closing

import pytest

from mcp_htmleditor import http_server
from mcp_htmleditor.config import PORT_RANGE_END, PORT_RANGE_START
from mcp_htmleditor.http_server import find_free_port

BLOCK_SIZE = PORT_RANGE_END - PORT_RANGE_START + 1
SEARCH_FIRST_PORT = 30000
SEARCH_LAST_PORT = 32000  # below 32768, where Linux hands out ephemeral ports
WHOLE_RANGE_MESSAGE = (
    f"No free port available (tried {PORT_RANGE_START - 1} and {PORT_RANGE_START}-{PORT_RANGE_END}): "
    "10 presentations already running? Stop one or pass an explicit --port."
)


def can_bind(port: int) -> bool:
    """True when ``127.0.0.1:port`` can be bound without ``SO_REUSEADDR`` right now."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


@pytest.fixture
def free_block(monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    """Redirect the scanned range to 10 consecutive free ports; yield the first port of the block.

    The port just below the block is free too, so it can serve as the preferred port.
    """
    first_candidates = list(range(SEARCH_FIRST_PORT + 1, SEARCH_LAST_PORT - BLOCK_SIZE))
    random.shuffle(first_candidates)
    for base in first_candidates:
        if all(can_bind(port) for port in range(base - 1, base + BLOCK_SIZE)):
            break
    else:
        pytest.fail(f"no block of {BLOCK_SIZE + 1} consecutive free ports in {SEARCH_FIRST_PORT}-{SEARCH_LAST_PORT}")
    monkeypatch.setattr(http_server, "PORT_RANGE_START", base)
    monkeypatch.setattr(http_server, "PORT_RANGE_END", base + BLOCK_SIZE - 1)
    yield base


def listen_on(port: int) -> socket.socket:
    """A listening socket on ``127.0.0.1:port``; the caller closes it."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.listen(1)
    return sock


def test_returns_the_preferred_port_when_free() -> None:
    """No collision: the preferred port itself is returned."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    assert find_free_port("127.0.0.1", free_port) == free_port


def test_falls_back_into_the_range_when_preferred_is_taken(free_block: int) -> None:
    """The preferred port is occupied: falls back into the range, skipping the occupied one."""
    with closing(listen_on(free_block)):
        result = find_free_port("127.0.0.1", free_block)

        assert result != free_block
        assert free_block <= result <= free_block + BLOCK_SIZE - 1


def test_two_presentations_get_two_different_ports(free_block: int) -> None:
    """Simulates two independent processes each auto-picking a port: no collision."""
    port_a = find_free_port("127.0.0.1", free_block - 1)
    with closing(listen_on(port_a)):
        port_b = find_free_port("127.0.0.1", free_block - 1)

        assert port_b != port_a
        assert free_block <= port_b <= free_block + BLOCK_SIZE - 1


def hold_port_or_none(port: int) -> socket.socket | None:
    """Listen on ``127.0.0.1:port``; ``None`` when another process holds it so that no bind of ours can succeed.

    A bind without ``SO_REUSEADDR`` comes first. On BSD and macOS a listener on the wildcard address (an editor
    started with ``--host 0.0.0.0``) refuses it, while ``find_free_port`` probes with ``SO_REUSEADDR`` and still
    counts the port free; the second try with ``SO_REUSEADDR`` makes the port taken for the probe as well.
    """
    for reuse_address in (False, True):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if reuse_address:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            sock.close()
            continue
        sock.listen(1)
        return sock
    return None


def test_raises_a_clear_error_when_the_whole_range_is_taken() -> None:
    """Every port of 7839 to 7849 unavailable, held by this test or by another process: a clear RuntimeError."""
    held = [hold_port_or_none(port) for port in range(PORT_RANGE_START - 1, PORT_RANGE_END + 1)]
    try:
        with pytest.raises(RuntimeError) as excinfo:
            find_free_port("127.0.0.1", PORT_RANGE_START - 1)
        assert str(excinfo.value) == WHOLE_RANGE_MESSAGE
    finally:
        for sock in held:
            if sock is not None:
                sock.close()
