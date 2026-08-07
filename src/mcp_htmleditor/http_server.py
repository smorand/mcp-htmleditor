"""HTTP server for the WYSIWYG editor.

Serves the GrapesJS editor shell and proxies HTML content
reads/writes to the current file on disk.
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .state import get_state

# IDs/classes injected by the browser editor — must be stripped before saving.
_EDITOR_ARTIFACTS = {
    "ids":     {"_mcp_format_bar", "_mcp_insert_bar", "_mcp_editor_styles", "_editor_ctx_host"},
    "classes": {"_mcp_editable", "gtx-trans-icon"},
    "attrs":   {"contenteditable"},
}

# Browser-extension attributes (Google Translate, Grammarly, etc.) that pollute
# the serialized DOM and must be stripped on save.
_EXTENSION_ATTR_PREFIXES = ("_msthash", "_msttexthash", "_msthidden", "data-gr-", "data-gramm")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _static_dir() -> Path:
    """Return the path to the bundled static directory."""
    return Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class _EditorHandler(BaseHTTPRequestHandler):  # pragma: no cover - network I/O boundary, exercised manually
    """Handle all HTTP requests for the editor server."""

    # Silence default request logging (MCP context logs are enough)
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    # ------------------------------------------------------------------
    # CORS helper
    # ------------------------------------------------------------------

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Handle pre-flight CORS requests."""
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    # ------------------------------------------------------------------
    # GET dispatch
    # ------------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        """Dispatch GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/" or path == "":
            self._serve_editor_html()
        elif path.startswith("/static/"):
            self._serve_static(path[len("/static/"):])
        elif path == "/content":
            self._serve_content()
        elif path == "/content-frame":
            self._serve_content_frame()
        elif path == "/status":
            self._serve_status()
        else:
            self._not_found()

    # ------------------------------------------------------------------
    # POST dispatch
    # ------------------------------------------------------------------

    def do_POST(self) -> None:  # noqa: N802
        """Dispatch POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/content":
            self._receive_content()
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
        if not file_path.exists():
            self._not_found()
            return
        mime = self._guess_mime(safe_name)
        self._send_file(file_path, mime)

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

    def _serve_status(self) -> None:
        """Return JSON status for polling."""
        state = get_state()
        payload: dict[str, Any] = {
            "mtime": state.get_mtime(),
            "update_in_progress": state.update_in_progress,
            "filename": state.current_file,
            "poll_interval": state.poll_interval,
            "port": state.port,
        }
        self._send_json(payload)

    def _receive_content(self) -> None:
        """Receive updated HTML from the editor and write it to disk."""
        state = get_state()
        if not state.current_file:
            self._send_json({"error": "No file loaded"}, status=404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        content_type = self.headers.get("Content-Type", "")

        if "application/json" in content_type:
            try:
                data: dict[str, Any] = json.loads(body)
                html: str = data.get("html", "")
            except (json.JSONDecodeError, KeyError):
                self._send_json({"error": "Invalid JSON body"}, status=400)
                return
        else:
            html = body.decode("utf-8")

        # The editor sends the full document (DOCTYPE + html); strip ephemeral
        # editor artifacts before writing so the file stays clean for LLM agents.
        if "<html" not in html.lower():
            html = _rebuild_full_html(html, state.current_file)

        html = _strip_editor_artifacts(html)

        # Safety: never overwrite reference/bootstrap templates. They are meant
        # to be copied, not edited in place. Silently ignore such saves.
        # Safety: never overwrite reference/bootstrap templates. They are meant
        # to be copied, not edited in place. Silently ignore such saves.
        normalized = state.current_file.replace("\\", "/")
        if "/templates/bootstrap/" in normalized or "/templates/reference/" in normalized:
            self._send_json({"ok": True, "skipped": "template file is read-only"})
            return

        try:
            Path(state.current_file).write_text(html, encoding="utf-8")
        except OSError as exc:
            self._send_json({"error": str(exc)}, status=500)
            return

        self._send_json({"ok": True})

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
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, data: bytes, mime: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self._send_cors_headers()
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
# HTML reconstruction
# ---------------------------------------------------------------------------

def _strip_editor_artifacts(html: str) -> str:
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
        if el:
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
    if slide_select:
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
    """
    head_content: str = ""
    doc_type_attr = ""

    if current_file:
        try:
            existing = Path(current_file).read_text(encoding="utf-8")
            # Extract head
            head_start = existing.lower().find("<head")
            head_end = existing.lower().find("</head>")
            if head_start != -1 and head_end != -1:
                head_content = existing[head_start : head_end + 7]
            # Extract data-doc-type from <html> tag
            html_tag_end = existing.lower().find(">", existing.lower().find("<html"))
            if html_tag_end != -1:
                html_tag = existing[: html_tag_end + 1]
                import re
                m = re.search(r'data-doc-type=["\']([^"\']+)["\']', html_tag)
                if m:
                    doc_type_attr = f' data-doc-type="{m.group(1)}"'
        except OSError:
            pass

    if not head_content:
        head_content = "<head><meta charset=\"UTF-8\"></head>"

    return (
        f"<!DOCTYPE html>\n"
        f"<html{doc_type_attr}>\n"
        f"{head_content}\n"
        f"<body>\n{canvas_html}\n</body>\n"
        f"</html>\n"
    )


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

_server_instance: ThreadingHTTPServer | None = None
_server_thread: threading.Thread | None = None
_server_lock = threading.Lock()


def start_http_server(file: str, port: int = 7842) -> bool:  # pragma: no cover - starts a real server thread
    """Start the HTTP server serving the given HTML file.

    Idempotent: if a server is already running on the same port with the
    same file, this is a no-op and returns False. Returns True if a new
    server was started.
    """
    global _server_instance, _server_thread

    state = get_state()

    with _server_lock:
        if _server_instance is not None:
            # Already running; just update the file
            state.set_file(file)
            return False

        state.set_file(file)
        state.port = port
        state.server_pid = os.getpid()
        state.save()

        server = ThreadingHTTPServer(("localhost", port), _EditorHandler)
        _server_instance = server

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        _server_thread = thread

    return True


def stop_http_server() -> None:  # pragma: no cover - stops a real server thread
    """Stop the running HTTP server if any."""
    global _server_instance, _server_thread

    with _server_lock:
        if _server_instance is not None:
            _server_instance.shutdown()
            _server_instance = None
            _server_thread = None

    state = get_state()
    state.server_pid = None
    state.save()


def is_server_running() -> bool:  # pragma: no cover - trivial global check
    """Return True if the HTTP server is currently running."""
    return _server_instance is not None
