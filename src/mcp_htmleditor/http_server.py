"""HTTP server for the WYSIWYG editor.

Serves the editor shell and proxies HTML content reads/writes to the current
file on disk. Routes: ``/`` (shell), ``/static/*``, ``/content``,
``/content-frame``, ``/status`` (polling), ``/health`` (liveness, pid, loaded file, version, start, uptime; any host),
``/export/pptx``, ``/export/docx`` and ``POST /arch-layout`` (recompute every
declarative diagram in place, used by the browser after a structural edit),
``GET /requests``, ``POST /requests``, ``POST /requests/delete`` (the request queue of the loaded file) and
``POST /review/apply`` (a suggestion of the review becomes a pending request). Any other GET path answers the
picture, media, font or style file it names next to the open deck, contained in its folder (``deck_files.py``,
SPEC-0023), else ``Not found``.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import socket
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, TypeGuard, cast
from urllib.parse import quote, urlparse, urlsplit

from bs4 import BeautifulSoup, Tag

from . import http_deadline
from .config import PORT_RANGE_END, PORT_RANGE_START, default_host, default_port
from .deck_files import SVG, SVG_POLICY, deck_file, media_type
from .fileio import WriteError, atomic_write, is_template_path
from .http_connections import ConnectionRegistry
from .request_service import (
    BODY_MAX_BYTES,
    RequestError,
    build_request_service,
    request_to_dict,
    snapshot_to_dict,
)
from .state import get_state
from .textcheck import UNENCODABLE_TEXT, is_utf8_encodable
from .tracing import trace_span
from .version import __version__

logger = logging.getLogger(__name__)

# IDs/classes injected by the browser editor — must be stripped before saving.
_MAX_CLEAN_PASSES = 5

_EDITOR_ARTIFACTS = {
    "ids": {
        "_mcp_format_bar",
        "_mcp_insert_bar",
        "_mcp_editor_styles",
        "_editor_ctx_host",
        "_mcp_drop_indicator",
    },
    "classes": {
        "_mcp_editable",
        "_mcp_drag_handle",
        "_mcp_drag_host",
        "_mcp_drop_indicator",
        "_mcp_dragging",
        "_mcp_arch_draggable",
        "_mcp_arch_grabbing",
        "gtx-trans-icon",
    },
    "attrs": {"contenteditable"},
}

# Browser-extension attributes (Google Translate, Grammarly, etc.) that pollute
# the serialized DOM and must be stripped on save.
_EXTENSION_ATTR_PREFIXES = ("_msthash", "_msttexthash", "_msthidden", "data-gr-", "data-gramm")

# A save body above 50 MiB is refused unread. A length of more than 10 significant digits is already above
# the cap, so it never reaches ``int()``.
MAX_SAVE_BYTES = 52_428_800
LAYOUT_BODY_MAX_BYTES = BODY_MAX_BYTES
MAX_LENGTH_DIGITS = 10

# Headers read once to decide a request; a repeated line is refused, in this order (SPEC-0013/BR-001).
_SINGLE_HEADERS = ("Host", "Origin", "Content-Length", "Content-Type")

# RequestError.kind to HTTP status (SPEC-0010).
REQUEST_STATUS = {"invalid": 400, "conflict": 409, "not_found": 404, "storage": 500}


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _static_dir() -> Path:
    """Return the path to the bundled static directory."""
    return Path(__file__).parent / "static"


def content_disposition(filename: str) -> str:
    """An attachment header any file name fits in: an ASCII ``filename`` fallback plus the RFC 6266 UTF-8 form."""
    fallback = filename.encode("ascii", "replace").decode("ascii").replace("?", "_").replace('"', "_")
    return f"attachment; filename=\"{fallback.replace(chr(92), '_')}\"; filename*=UTF-8''{quote(filename, safe='')}"


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------


class _EditorHandler(BaseHTTPRequestHandler):  # pragma: no cover - network I/O boundary, exercised manually
    """Handle all HTTP requests for the editor server."""

    # Silence default request logging (MCP context logs are enough)
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    # ------------------------------------------------------------------
    # Connection bounds (SPEC-0013/BR-008, BR-009): every wait ends, no request ends with a traceback
    # ------------------------------------------------------------------

    def setup(self) -> None:
        super().setup()
        buffered = cast(io.BufferedReader, self.rfile)  # makefile("rb", rbufsize=-1) is a BufferedReader
        self.rfile = http_deadline.DeadlineReader(buffered, self.connection)  # type: ignore[assignment]  # duck typed file
        self.wfile = http_deadline.DeadlineWriter(self.connection)  # type: ignore[assignment]  # duck typed file
        self._connections().add(self.connection)  # closing already: shut at once (SPEC-0014 DEC-002)

    def finish(self) -> None:
        try:
            super().finish()
        finally:
            self._connections().remove(self.connection)

    def _connections(self) -> ConnectionRegistry:
        return cast(_EditorServer, self.server).connections

    def parse_request(self) -> bool:
        """Parse the line and headers; once complete the request is busy, or refused unanswered if a stop began.

        A stop shuts idle connections, so what was read here may be cut short: the closing check comes first so a
        cut request line gets no error answer either (SPEC-0014/BR-003).
        """
        if self._connections().closing or not super().parse_request():
            self.close_connection = True
            return False
        if not self._connections().begin_request(self.connection):
            self.close_connection = True
            return False
        self._request_began = True
        return True

    def handle_one_request(self) -> None:
        """Run one request; a timeout, a client gone or an unexpected failure ends it with the DEC-015 answer."""
        self._headers_flushed = False
        self._request_began = False
        try:
            self._handle_with_deadlines()
        finally:
            if self._request_began and self._connections().end_request(self.connection):
                self.close_connection = True  # a stop began while this request ran (SPEC-0014/BR-004)

    def _handle_with_deadlines(self) -> None:
        try:
            super().handle_one_request()
        except http_deadline.RequestTimeout as timeout:
            self.close_connection = True
            if timeout.has_bytes:
                self._answer_timeout()
        except (http_deadline.ResponseTimeout, BrokenPipeError, ConnectionResetError) as gone:
            self.close_connection = True
            logger.debug("Connection closed while answering: %s", type(gone).__name__)
        except Exception as exc:
            self.close_connection = True
            logger.error("Request failed: %s %s: %s", *self._request_names(), type(exc).__name__)
            if not self._headers_flushed:  # headers only buffered never reached the wire: discard them, answer 500
                self._answer_best_effort(500, str(exc))

    def flush_headers(self) -> None:
        self._headers_flushed = True  # set before the write: a partial write may already have put bytes on the wire
        super().flush_headers()

    def _answer_timeout(self) -> None:
        logger.warning("Refused %s %s: Request timeout", *self._request_names())
        self._answer_best_effort(408, "Request timeout")

    def _answer_best_effort(self, status: int, error: str) -> None:
        """Send ``{"error": error}``; a client already gone or not reading gets nothing more."""
        if getattr(self, "request_version", self.default_request_version) == self.default_request_version:
            self.request_version = "HTTP/1.0"  # HTTP/0.9, the default before the request line, has no status line
        if not hasattr(self, "requestline"):
            self.requestline = ""  # read by send_response's log_request
        self._headers_buffer = list[bytes]()
        try:
            self._send_json({"error": error}, status=status)
        except (OSError, http_deadline.ResponseTimeout) as exc:
            logger.debug("Answer %d not sent: %s", status, type(exc).__name__)

    def _request_names(self) -> tuple[str, str]:
        """Method and path of the request, ``-`` for each one its line did not give."""
        command = getattr(self, "command", None)
        path = getattr(self, "path", None)
        return (command or "-", urlparse(path).path if command and path else "-")

    # ------------------------------------------------------------------
    # Request gate: ambiguous headers (SPEC-0013), then own origin and loopback host names (SPEC-0005)
    # ------------------------------------------------------------------

    def _refuse_ambiguous_headers(self) -> bool:
        """Answer 400 and return True when the header block can be read two ways (SPEC-0013/BR-001 to BR-005).

        Checked in this order: a folded line, a repeated ``Host``, ``Origin``, ``Content-Length`` or
        ``Content-Type``, any ``Transfer-Encoding``, a ``Host`` carrying userinfo. The body is never read here.
        """
        if any("\r" in value or "\n" in value for _, value in self.headers.items()):
            self._refuse_request(400, "Invalid header folding")
            return True
        for name in _SINGLE_HEADERS:
            if len(self.headers.get_all(name) or []) > 1:
                self._refuse_request(400, f"Duplicate {name} header")
                return True
        if "Transfer-Encoding" in self.headers:
            self._refuse_request(400, "Transfer-Encoding not supported")
            return True
        if "@" in self.headers.get("Host", ""):
            self._refuse_request(400, "Invalid Host header")
            return True
        return False

    def _refuse_request(self, status: int, error: str) -> None:
        logger.warning("Refused %s %s: %s", self.command, urlparse(self.path).path, error)
        self._send_json({"error": error}, status=status)

    def _refuse_untrusted_request(self) -> bool:
        """Answer 403 and return True when the request comes from elsewhere.

        Any page open in the user's browser can reach a loopback server, and
        any DNS name can be rebound to 127.0.0.1: only requests addressed
        through a trusted host name and, when they carry an Origin, coming
        from that same origin are allowed through.
        """
        if self._refuse_ambiguous_headers():
            return True
        host = self.headers.get("Host", "")
        host_name, host_port = _split_host(host)
        if host_name not in _trusted_host_names(getattr(self.server, "bind_host", "")):
            self._refuse("forbidden host", host)
            return True
        origin = self.headers.get("Origin")
        if origin is not None and not _is_same_origin(origin, host_name, host_port):
            self._refuse("forbidden origin", origin)
            return True
        return False

    def _refuse(self, reason: str, value: str, status: int = 403) -> None:
        logger.warning("Refused %s %s: %s %r", self.command, urlparse(self.path).path, reason, value)
        self._send_json({"error": reason}, status=status)

    def do_OPTIONS(self) -> None:
        """Refuse CORS preflights: no cross origin access is ever granted (SPEC-0005/BR-005)."""
        self.send_response(405)
        self.send_header("Allow", "GET, POST")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ------------------------------------------------------------------
    # GET dispatch
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        """Dispatch GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/health":
            self._send_json(health_payload())
            return
        if self._refuse_untrusted_request():
            return

        if path in {"/", ""}:
            self._serve_editor_html()
        elif path.startswith("/static/"):
            self._serve_static(path[len("/static/") :])
        elif path == "/content":
            self._serve_content()
        elif path == "/content-frame":
            self._serve_content_frame()
        elif path == "/status":
            self._serve_status()
        elif path == "/export/pptx":
            self._export_pptx()
        elif path == "/export/docx":
            self._export_docx()
        elif path == "/requests":
            self._list_requests()
        else:
            self._serve_deck_file(parsed.path)

    # ------------------------------------------------------------------
    # POST dispatch
    # ------------------------------------------------------------------

    def do_POST(self) -> None:
        """Dispatch POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        if self._refuse_untrusted_request():
            return
        if path == "/content":
            self._receive_content()
        elif path == "/arch-layout":
            self._run_arch_layout()
        elif path == "/requests":
            self._queue_request()
        elif path == "/requests/delete":
            self._delete_request()
        elif path == "/review/apply":
            self._apply_suggestion()
        else:
            self._not_found()

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------

    def _serve_editor_html(self) -> None:
        """Serve the GrapesJS shell HTML."""
        html_path = _static_dir() / "editor.html"
        self._send_file(html_path, "text/html")

    def _serve_static(self, filename: str) -> None:
        """Serve a file from the static directory."""
        # Security: prevent path traversal
        safe_name = Path(filename).name
        file_path = _static_dir() / safe_name
        if not file_path.is_file():  # "..", "." name the static folder itself
            logger.warning("Refused %s %s: not served", self.command, urlparse(self.path).path)
            self._not_found()
            return
        mime = self._guess_mime(safe_name)
        self._send_file(file_path, mime)

    def _serve_deck_file(self, raw_path: str) -> None:
        """A picture, media, font or style file next to the open deck (SPEC-0023 FR-NEW-009), else ``Not found``."""
        target = deck_file(get_state().current_file, raw_path)
        if target is None:
            logger.warning("Refused %s %s: not served", self.command, raw_path)
            self._not_found()
            return
        with trace_span("http.deck_file", {"file.suffix": target.suffix.lower()}):
            try:
                data = target.read_bytes()
            except OSError:
                self._not_found()
                return
        self.send_response(200)
        self.send_header("Content-Type", media_type(target))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if target.suffix.lower() == SVG:
            self.send_header("Content-Security-Policy", SVG_POLICY)
        self._send_no_store_headers()
        self.end_headers()
        self.wfile.write(data)

    def _serve_content(self) -> None:
        """Return the raw HTML of the current file (for POST saves)."""
        state = get_state()
        if not state.current_file:
            self._send_json({"error": "No file loaded"}, status=404)
            return
        try:
            html = Path(state.current_file).read_text(encoding="utf-8")
        except OSError as exc:
            self._send_json({"error": str(exc)}, status=500)
            return
        self._send_bytes(html.encode("utf-8"), "text/html")

    def _serve_content_frame(self) -> None:
        """Serve the current HTML file as-is for the iframe (full document)."""
        state = get_state()
        if not state.current_file:
            placeholder = (
                b"<html><body>"
                b"<p style='font-family:sans-serif;padding:40px;color:#525252'>"
                b"No file loaded. Use <code>mcp-htmleditor serve &lt;file&gt;</code> "
                b"or call <code>start_server</code> via MCP."
                b"</p></body></html>"
            )
            self._send_bytes(placeholder, "text/html")
            return
        try:
            html = Path(state.current_file).read_text(encoding="utf-8")
        except OSError as exc:
            self._send_json({"error": str(exc)}, status=500)
            return
        self._send_bytes(html.encode("utf-8"), "text/html")

    def _export_pptx(self) -> None:
        """Generate a PPTX from the current file and return it as a download."""
        from .export.to_pptx import to_pptx

        state = get_state()
        if not state.current_file:
            self._send_json({"error": "No file loaded"}, status=404)
            return
        src = Path(state.current_file)
        stem = src.stem
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            with trace_span("export.pptx", {"file.path": str(src)}):
                to_pptx(str(src), tmp_path)
            data = Path(tmp_path).read_bytes()
        except Exception as exc:
            logger.error("PPTX export failed: %s", exc)
            self._send_json({"error": str(exc)}, status=500)
            return
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        self._send_attachment(
            data, "application/vnd.openxmlformats-officedocument.presentationml.presentation", f"{stem}.pptx"
        )

    def _export_docx(self) -> None:
        """Generate a DOCX from the current file and return it as a download."""
        from .export.to_docx import to_docx

        state = get_state()
        if not state.current_file:
            self._send_json({"error": "No file loaded"}, status=404)
            return
        src = Path(state.current_file)
        stem = src.stem
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            with trace_span("export.docx", {"file.path": str(src)}):
                to_docx(str(src), tmp_path)
            data = Path(tmp_path).read_bytes()
        except Exception as exc:
            logger.error("DOCX export failed: %s", exc)
            self._send_json({"error": str(exc)}, status=500)
            return
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        self._send_attachment(
            data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", f"{stem}.docx"
        )

    def _send_attachment(self, data: bytes, mime: str, filename: str) -> None:
        """Send an export download; outside the export ``try`` so a client not reading reaches the DEC-015 close."""
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Disposition", content_disposition(filename))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_status(self) -> None:
        """Return JSON status for polling."""
        state = get_state()
        payload: dict[str, Any] = {
            "mtime": state.get_mtime(),
            "update_in_progress": state.update_in_progress,
            "update_expires_in": state.update_expires_in,
            "filename": state.current_file,
            "poll_interval": state.poll_interval,
            "port": state.port,
            "requests_revision": build_request_service().revision(Path(state.current_file))
            if state.current_file
            else 0,
        }
        self._send_json(payload)

    def _list_requests(self) -> None:
        """Return the request record of the loaded file: revision, pending count, requests, suggestions."""
        file = self._loaded_file()
        if file is None:
            return
        try:
            snapshot = build_request_service().snapshot(file)
        except RequestError as exc:
            self._send_json({"error": exc.message}, status=REQUEST_STATUS[exc.kind])
            return
        self._send_json(snapshot_to_dict(snapshot))

    def _queue_request(self) -> None:
        """Queue a pending request for the loaded file (SPEC-0010/FR-NEW-001)."""
        file = self._loaded_file()
        body = self._read_json_object() if file is not None else None
        if file is None or body is None:
            return
        instruction, slide = body.get("instruction"), body.get("slide")
        if not _is_text(instruction) or not (slide is None or _is_text(slide)):
            self._invalid_request_body()
            return
        self._answer_request(
            lambda: {"ok": True, "request": request_to_dict(build_request_service().queue(file, instruction, slide))}
        )

    def _delete_request(self) -> None:
        """Delete a request of the loaded file; an unknown id is a no op."""
        file = self._loaded_file()
        body = self._read_json_object() if file is not None else None
        if file is None or body is None:
            return
        request_id = body.get("id")
        if not _is_text(request_id):
            self._invalid_request_body()
            return

        def delete() -> dict[str, Any]:
            build_request_service().delete(file, request_id)
            return {"ok": True}

        self._answer_request(delete)

    def _apply_suggestion(self) -> None:
        """Turn a suggestion of the review into a pending request (SPEC-0010/FR-NEW-007)."""
        file = self._loaded_file()
        body = self._read_json_object() if file is not None else None
        if file is None or body is None:
            return
        suggestion_id = body.get("id")
        if not _is_text(suggestion_id):
            self._invalid_request_body()
            return
        self._answer_request(
            lambda: {
                "ok": True,
                "request": request_to_dict(build_request_service().apply_suggestion(file, suggestion_id)),
            }
        )

    def _answer_request(self, action: Callable[[], dict[str, Any]]) -> None:
        """Run a request operation: its payload with 200, or the ``RequestError`` text with its status."""
        try:
            payload = action()
        except RequestError as exc:
            self._send_json({"ok": False, "error": exc.message}, status=REQUEST_STATUS[exc.kind])
            return
        self._send_json(payload)

    def _loaded_file(self) -> Path | None:
        """The file this server serves, else answer 404 and return None."""
        current = get_state().current_file
        if not current:
            self._send_json({"error": "No file loaded"}, status=404)
            return None
        return Path(current)

    def _read_json_object(self) -> dict[str, Any] | None:
        """Read the body of a request route as a JSON object, answering the refusal and returning None if not.

        Content type first (415), then the length (400, 413 above 1 MiB, before reading), then the JSON (400);
        a body that is not an object is ``Invalid request body``.
        """
        try:
            data = json.loads(self._read_request_body())
        except SaveRefusal as refusal:
            self._send_json(refusal.payload, status=refusal.status)
            return None
        except (ValueError, RecursionError):
            self._send_json({"error": "Invalid JSON body"}, status=400)
            return None
        if not isinstance(data, dict):
            self._invalid_request_body()
            return None
        return data

    def _read_request_body(self) -> bytes:
        content_type = self.headers.get("Content-Type", "")
        try:
            body = self._read_declared_body(BODY_MAX_BYTES)
        except SaveRefusal:
            check_content_type(content_type)  # a wrong content type outranks a bad length
            raise
        check_content_type(content_type)
        return body

    def _read_declared_body(self, limit: int) -> bytes:
        """Raise SaveRefusal 400 (not ASCII digits) or 413 (above ``limit``, before reading); else read the body."""
        length = parse_content_length(self.headers.get("Content-Length"))
        if length > limit:
            raise SaveRefusal(413, {"error": "Request too large"})
        return self.rfile.read(length)

    def _invalid_request_body(self) -> None:
        self._send_json({"ok": False, "error": "Invalid request body"}, status=400)

    def _receive_content(self) -> None:
        """Receive updated HTML from the editor and write it to disk (SPEC-0009 save pipeline)."""
        state = get_state()
        if not state.current_file:
            self._send_json({"error": "No file loaded"}, status=404)
            return
        try:
            request = self._read_save_request()
            refuse_template(state.current_file)
            with state.save_lock:
                mtime = write_save(Path(state.current_file), request)
        except SaveRefusal as refusal:
            logger.warning("Refused %s %s: %s", self.command, urlparse(self.path).path, refusal.payload["error"])
            self._send_json(refusal.payload, status=refusal.status)
            return
        except (OSError, WriteError) as exc:
            logger.error("Save failed for %s: %s", state.current_file, exc)
            self._send_json({"error": failure_text(exc)}, status=500)
            return
        self._send_json({"ok": True, "mtime": mtime})

    def _read_save_request(self) -> SaveRequest:
        """Check the length, read the body, then check the content type and the JSON (spec order)."""
        length = parse_content_length(self.headers.get("Content-Length"))
        body = self.rfile.read(length)
        check_content_type(self.headers.get("Content-Type", ""))
        return parse_save_body(body)

    def _run_arch_layout(self) -> None:
        """Recompute every declarative arch-diagram in the current file.

        Called by the browser right after it saves a structural diagram edit
        (add/remove node or edge, see editor-menus.js's ``saveThenLayout``): the
        browser cannot run the Python layout engine itself, so it POSTs here,
        the server writes the recomputed positions to disk, and the existing
        polling loop picks up the mtime change and reloads the iframe — the
        same path an LLM agent's own ``arch-layout`` call already takes.
        """
        from .arch_layout import layout_file

        state = get_state()
        if not state.current_file:
            self._send_json({"error": "No file loaded"}, status=404)
            return

        try:
            self._read_declared_body(LAYOUT_BODY_MAX_BYTES)  # body is unused, drain it so the connection stays clean
        except SaveRefusal as refusal:
            self._refuse_request(refusal.status, refusal.payload["error"])
            return

        target = Path(state.current_file)
        with trace_span("mcp.layout_arch_diagram", {"file.path": str(target)}) as span:
            try:
                report = layout_file(target)
            except (OSError, WriteError) as exc:
                logger.error("arch-layout failed for %s: %s", target, exc)
                self._send_json({"error": failure_text(exc)}, status=500)
                return
            span.set_attribute("arch_layout.diagrams_updated", report.diagrams_updated)
            span.set_attribute("arch_layout.warnings", len(report.warnings))

        self._send_json({"ok": True, "diagrams_updated": report.diagrams_updated, "warnings": list(report.warnings)})

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _send_file(self, path: Path, mime: str) -> None:
        try:
            data = path.read_bytes()
        except OSError:
            self._not_found()
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self._send_no_store_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, data: bytes, mime: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self._send_no_store_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_no_store_headers(self) -> None:
        """Forbid caching of the editor shell, static JS/CSS and served content.

        This is a live-editing tool: editor.html/editor.js/editor.css change
        between sessions (bug fixes, new features) and the served document
        changes on every save. Without explicit no-store, a browser can keep
        serving a stale cached copy from an already-open tab (no validators
        such as ETag/Last-Modified were sent either, so heuristic caching
        could otherwise kick in on a plain reload).
        """
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")

    def _send_json(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _not_found(self) -> None:
        self._send_json({"error": "Not found"}, status=404)

    @staticmethod
    def _guess_mime(filename: str) -> str:
        ext = Path(filename).suffix.lower()
        return {
            ".html": "text/html",
            ".js": "application/javascript",
            ".css": "text/css",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".json": "application/json",
        }.get(ext, "application/octet-stream")


# ---------------------------------------------------------------------------
# Save pipeline (SPEC-0009): pure checks raising SaveRefusal, in the spec order
# ---------------------------------------------------------------------------


class SaveRefusal(Exception):  # noqa: N818 - name fixed by SPEC-0009 DEC-010
    """A save refused before or instead of the write: the HTTP ``status`` and the JSON ``payload`` to answer."""

    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        super().__init__(status, payload)
        self.status = status
        self.payload = payload


@dataclass(frozen=True)
class SaveRequest:
    """The parts of a save body the server uses: the page, the version it last saw, and ``force``."""

    html: str
    base_mtime: float | None
    force: bool


def _is_text(value: object) -> TypeGuard[str]:
    """A string the record can hold: a lone surrogate (valid in JSON) cannot be written as UTF-8."""
    return isinstance(value, str) and is_utf8_encodable(value)


def parse_content_length(raw: str | None) -> int:
    """Return the declared body length: 0 when absent; 400 when not ASCII digits; 413 above the cap."""
    if raw is None:
        return 0
    if not (raw.isascii() and raw.isdigit()):
        raise SaveRefusal(400, {"error": "Invalid Content-Length"})
    digits = raw.lstrip("0")
    if len(digits) > MAX_LENGTH_DIGITS or int(digits or "0") > MAX_SAVE_BYTES:
        raise SaveRefusal(413, {"error": "Request too large"})
    return int(digits or "0")


def check_content_type(content_type: str) -> None:
    """JSON only: a text/plain or form body is what a foreign page can send without a CORS preflight."""
    if content_type.split(";", 1)[0].strip().lower() != "application/json":
        raise SaveRefusal(415, {"error": "unsupported content type"})


def parse_save_body(body: bytes) -> SaveRequest:
    """Read a save body: a JSON object with a string ``html``, else 400.

    A ``base_mtime`` that is not a JSON number (a boolean included) counts as absent; only ``force`` equal
    to ``true`` forces.
    """
    try:
        data = json.loads(body)
    except (ValueError, RecursionError):
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("html"), str):
        raise SaveRefusal(400, {"error": "Invalid JSON body"})
    if not is_utf8_encodable(data["html"]):
        raise SaveRefusal(400, {"error": UNENCODABLE_TEXT})
    return SaveRequest(
        html=data["html"], base_mtime=_number_or_none(data.get("base_mtime")), force=data.get("force") is True
    )


def _number_or_none(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        return float(value)
    except OverflowError:
        return float("inf")


def refuse_template(current_file: str) -> None:
    """Templates are meant to be copied, not edited in place: answer 403 naming the absolute path."""
    if is_template_path(current_file):
        raise SaveRefusal(403, {"ok": False, "error": f"Refusing to modify a template: {current_file}"})


def check_conflict(target: Path, base_mtime: float | None, force: bool) -> None:
    """Refuse with 409 when the file changed since ``base_mtime``; a missing file reads as 0.0."""
    if base_mtime is None or force:
        return
    current = _mtime_or_zero(target)
    if current != base_mtime:
        raise SaveRefusal(409, {"ok": False, "error": "File changed on disk", "mtime": current})


def write_save(target: Path, request: SaveRequest) -> float:
    """Check the conflict, clean the HTML, write it atomically and return the mtime after the write."""
    check_conflict(target, request.base_mtime, request.force)
    html = request.html
    # The editor sends the full document (DOCTYPE + html); strip ephemeral editor artifacts before writing
    # so the file stays clean for LLM agents.
    if "<html" not in html.lower():
        html = _rebuild_full_html(html, str(target))
    atomic_write(target, _strip_editor_artifacts(html), reason="keep-mine" if request.force else "browser-save")
    return target.stat().st_mtime


def failure_text(exc: OSError | WriteError) -> str:
    """The operating system message of a failed write (``strerror``, else the exception text)."""
    if isinstance(exc, WriteError):
        return exc.reason
    return exc.strerror or str(exc)


def _mtime_or_zero(target: Path) -> float:
    try:
        return target.stat().st_mtime
    except FileNotFoundError:
        return 0.0


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def health_payload() -> dict[str, Any]:
    """Return the ``/health`` body: liveness plus the running version.

    Cheap: it reads no file and writes nothing. ``file`` (absolute) and ``page`` (its base name) are null
    when no file is loaded. ``status`` stays next to ``ok`` for older callers.

    Returns:
        Dict with keys ``ok``, ``status``, ``pid``, ``file``, ``page``, ``port``, ``version``, ``started``
        (UTC ISO) and ``uptime_seconds``.
    """
    state = get_state()
    file = state.current_file
    now = time.time()
    return {
        "ok": True,
        "status": "ok",
        "pid": os.getpid(),
        "file": file,
        "page": Path(file).name if file else None,
        "port": state.port,
        "version": __version__,
        "started": datetime.fromtimestamp(_started_at, tz=UTC).isoformat(timespec="seconds"),
        "uptime_seconds": max(0, int(now - _started_at)),
    }


# ---------------------------------------------------------------------------
# HTML reconstruction
# ---------------------------------------------------------------------------


def _strip_editor_artifacts(html: str) -> str:
    """Clean ``html`` until a further pass changes nothing, so cleaning twice equals cleaning once.

    One parse and serialise pass is not stable on markup the parser repairs (a stray closing tag moves
    whitespace), so a save of the bytes the server wrote would differ from them and add a version.
    The loop is bounded; each pass removes the same things as ``_strip_editor_artifacts_once``.
    """
    cleaned = _strip_editor_artifacts_once(html)
    for _ in range(_MAX_CLEAN_PASSES):
        again = _strip_editor_artifacts_once(cleaned)
        if again == cleaned:
            break
        cleaned = again
    return cleaned


def _strip_editor_artifacts_once(html: str) -> str:
    """Remove ephemeral editor elements injected by the browser UI.

    The JS editor injects helper nodes (format bar, insert bar, style tag,
    context menu host) and attributes (contenteditable, _mcp_editable class)
    directly into the iframe DOM.  Before persisting to disk we strip all of
    them so the saved file stays clean and readable by LLM agents.

    We also clear dynamically-generated <option> elements from the slide
    dropdown (#slide-select) to prevent duplication on each reload (the JS
    rebuilds them from slideNames[] every time the page loads).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove injected elements by id
    for eid in _EDITOR_ARTIFACTS["ids"]:
        el = soup.find(id=eid)
        if isinstance(el, Tag):
            el.decompose()

    # Remove drag-reorder artifacts entirely (handle span + drop indicator).
    # These are whole nodes the editor injects, not just annotated content, so
    # we drop the element rather than merely clearing its class.
    for cls in ("_mcp_drag_handle", "_mcp_drop_indicator"):
        for el in soup.find_all(class_=cls):
            el.decompose()

    # Remove injected CSS class from all elements
    for cls in _EDITOR_ARTIFACTS["classes"]:
        for el in soup.find_all(class_=cls):
            el["class"] = [c for c in el.get("class", []) if c != cls]
            if not el.get("class"):
                del el["class"]

    # Remove injected attributes
    for attr in _EDITOR_ARTIFACTS["attrs"]:
        for el in soup.find_all(attrs={attr: True}):
            del el[attr]

    # Clear dynamically-generated <option> elements from the slide dropdown.
    # The navigation JS regenerates them from slideNames[] on every page load;
    # keeping them in the saved HTML causes duplication on each reload.
    slide_select = soup.find(id="slide-select")
    if isinstance(slide_select, Tag):
        for opt in slide_select.find_all("option"):
            opt.decompose()

    # Strip browser-extension attributes (Google Translate, Grammarly, etc.)
    for el in soup.find_all(True):
        for attr in list(el.attrs.keys()):
            if any(attr.startswith(p) for p in _EXTENSION_ATTR_PREFIXES):
                del el[attr]

    return str(soup)


def _rebuild_full_html(canvas_html: str, current_file: str | None) -> str:
    """Reconstruct a complete HTML document from a GrapesJS canvas fragment.

    GrapesJS returns body content only. This function wraps it in a proper
    document, preserving the head of the existing file when available.

    Attributes of the original ``<html>`` tag that carry meaning downstream are
    preserved: ``lang`` (pandoc turns it into the Word document language, so
    losing it makes an exported DOCX default to en-US), ``data-doc-type``
    (drives the editor mode) and every ``data-asset-*`` (fallback data URIs used
    when inserting a slide, see resolveTemplateAssets in static/editor-slides.js).
    """
    head_content: str = ""
    html_attrs = ""

    if current_file:
        try:
            existing = Path(current_file).read_text(encoding="utf-8")
            # Extract head
            head_start = existing.lower().find("<head")
            head_end = existing.lower().find("</head>")
            if head_start != -1 and head_end != -1:
                head_content = existing[head_start : head_end + 7]
            # Extract lang + data-doc-type from the <html> tag
            html_tag_end = existing.lower().find(">", existing.lower().find("<html"))
            if html_tag_end != -1:
                html_tag = existing[: html_tag_end + 1]
                for attr in ("lang", "data-doc-type"):
                    m = re.search(rf'{attr}=["\']([^"\']+)["\']', html_tag)
                    if m:
                        html_attrs += f' {attr}="{m.group(1)}"'
                for name, value in re.findall(r'(data-asset-[a-z0-9-]+)="([^"]*)"', html_tag):
                    html_attrs += f' {name}="{value}"'
        except OSError:
            pass

    if not head_content:
        head_content = '<head><meta charset="UTF-8"></head>'

    return f"<!DOCTYPE html>\n<html{html_attrs}>\n{head_content}\n<body>\n{canvas_html}\n</body>\n</html>\n"


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

LOOPBACK_HOST_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})
# Wildcard bind addresses: compared against the bind host, never bound here.
_WILDCARD_HOSTS = frozenset({"0.0.0.0", "::"})  # noqa: S104  # nosec B104


class _EditorServer(ThreadingHTTPServer):
    """HTTP server that remembers the host it was asked to bind (SPEC-0005 host gate) and its open connections."""

    def __init__(self, bind_host: str, port: int) -> None:
        self.connections = ConnectionRegistry()  # before the bind: a handler may look it up as soon as one exists
        super().__init__((bind_host, port), _EditorHandler)
        self.bind_host = bind_host


def _split_host(host: str) -> tuple[str, int | None]:
    """Return the lower cased name and the port of a ``Host`` header, ``("", None)`` if unparsable."""
    try:
        parts = urlsplit(f"//{host}")
        return (parts.hostname or "", parts.port)
    except ValueError:
        return ("", None)


def _trusted_host_names(bind_host: str) -> frozenset[str]:
    """Loopback names, plus the bind host when it names one interface (not a wildcard)."""
    extra = bind_host.strip("[]").lower()
    if not extra or extra in _WILDCARD_HOSTS:
        return LOOPBACK_HOST_NAMES
    return LOOPBACK_HOST_NAMES | {extra}


def _is_same_origin(origin: str, host_name: str, host_port: int | None) -> bool:
    """True when ``origin`` is exactly ``http://`` plus the host the request was sent to."""
    try:
        parts = urlsplit(origin)
        origin_port = parts.port
    except ValueError:
        return False
    return parts.scheme == "http" and (parts.hostname or "") == host_name and (origin_port or 80) == (host_port or 80)


_server_instance: _EditorServer | None = None
_started_at: float = time.time()  # reset when the server starts; the import time before that
_server_thread: threading.Thread | None = None
_server_lock = threading.Lock()


def _port_is_free(host: str, port: int) -> bool:
    """Return True if `port` can be bound on `host` right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
        return True


def find_free_port(host: str, preferred: int) -> int:
    """Return a free TCP port, so several presentations can coexist.

    Tries `preferred` first (the configured default, HTMLEDITOR_PORT or
    7842), then scans PORT_RANGE_START..PORT_RANGE_END (7840-7849) in order.
    Each independent ``mcp-htmleditor serve``/``mcp-htmleditor mcp`` process
    picks its own free slot, so up to 10 decks can be edited at once without
    the caller having to hand-pick non-colliding ports.

    Args:
        host: Bind address to probe against (a port can be free on
            ``127.0.0.1`` and taken on ``0.0.0.0``, or vice versa).
        preferred: Port to try first.

    Returns:
        A currently free port.

    Raises:
        RuntimeError: every port in the range is taken (10 presentations
            already running).
    """
    candidates = [preferred, *(p for p in range(PORT_RANGE_START, PORT_RANGE_END + 1) if p != preferred)]
    for candidate in candidates:
        if _port_is_free(host, candidate):
            return candidate
    raise RuntimeError(
        f"No free port available (tried {preferred} and {PORT_RANGE_START}-{PORT_RANGE_END}): "
        "10 presentations already running? Stop one or pass an explicit --port."
    )


def start_http_server(
    file: str,
    port: int | None = None,
    host: str | None = None,
) -> tuple[bool, int]:  # pragma: no cover - starts a real server thread
    """Start the HTTP server serving the given HTML file.

    Idempotent: if a server is already running in this process, this is a
    no-op that just switches the served file (see `open_file`) and returns
    ``(False, <port already bound>)``.

    Args:
        file: HTML file to serve.
        port: TCP port to bind. If None (not explicitly requested), a free
            port is auto-picked (see `find_free_port`) so several
            independent mcp-htmleditor processes can each serve a different
            presentation without colliding on the same default port. If
            explicitly given, it is used as-is: a clear `OSError` is raised
            if it is already taken, rather than silently falling back.
        host: Bind address; defaults to HTMLEDITOR_HOST (localhost). Use
            ``0.0.0.0`` inside a container so the published port is reachable.

    Returns:
        ``(started, port)``: `started` is False if a server was already
        running in this process (no-op); `port` is the TCP port actually
        bound.
    """
    global _server_instance, _server_thread, _started_at

    state = get_state()
    bind_host = host if host is not None else default_host()

    with _server_lock:
        if _server_instance is not None:
            # Already running; just update the file
            state.set_file(file)
            logger.info("Server already running, switched file to %s", file)
            return False, state.port

        resolved_port = port if port is not None else find_free_port(bind_host, default_port())

        state.set_file(file)
        state.port = resolved_port
        state.server_pid = os.getpid()
        state.save()
        _started_at = time.time()

        try:
            server = _EditorServer(bind_host, resolved_port)
        except OSError as exc:
            hint = (
                "pass no --port to auto-pick a free one in "
                f"{PORT_RANGE_START}-{PORT_RANGE_END}, or choose another port explicitly"
            )
            raise OSError(f"Port {resolved_port} is already in use ({hint}): {exc}") from exc
        _server_instance = server
        logger.info("HTTP server listening on http://%s:%d/ (file: %s)", bind_host, resolved_port, file)

        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        _server_thread = thread

    return True, resolved_port


def stop_http_server() -> None:
    """Stop the running HTTP server if any, and release its port (SPEC-0014 DEC-001).

    ``shutdown`` only ends the serving loop; ``server_close`` closes the listening socket, so a new connect is
    refused and the port can be bound again at once; handler threads are daemons, so it joins none. Idle
    connections are then shut; a request already received finishes its answer on its own thread.
    """
    global _server_instance, _server_thread

    with _server_lock:
        server = _server_instance
        _server_instance = None
        _server_thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
            server.connections.close_idle()
            logger.info("HTTP server stopped")

    state = get_state()
    state.server_pid = None
    state.save()


def is_server_running() -> bool:  # pragma: no cover - trivial global check
    """Return True if the HTTP server is currently running."""
    return _server_instance is not None
