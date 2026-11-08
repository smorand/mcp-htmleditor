"""MCP server for html-editor.

Exposes 21 tools for LLM agents to control the WYSIWYG editor. Every tool call is
traced as ``mcp.<tool>`` (see :mod:`.tracing`).
"""

from __future__ import annotations

import asyncio
import logging
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from .arch_layout import layout_file
from .config import default_host
from .deck import DeckError
from .deck.lint import lint_file
from .deck.patch import apply_patch
from .deck.read import get_slide as read_slide
from .deck.read import outline as read_outline
from .deck.tools import create_file, export_file
from .deck.tools import template_listing as list_template_entries
from .history import list_versions, restore_version
from .http_server import (
    is_server_running,
    start_http_server,
    stop_http_server,
)
from .render.options import DEFAULT_SCALE
from .render.problems import result_to_dict
from .render.service import render_deck
from .request_service import RequestError, build_request_service, request_to_dict, require_file
from .skill_content import SkillError, build_library
from .state import get_state
from .textcheck import UNENCODABLE_BIND_ADDRESS, UNENCODABLE_FILE_NAME, is_utf8_encodable
from .tracing import trace_span

logger = logging.getLogger(__name__)

mcp: FastMCP = FastMCP("html-editor")


@mcp.tool()
def start_server(file: str, port: int | None = None) -> dict[str, Any]:
    """Start the WYSIWYG HTTP server for the given HTML file.

    Idempotent: if the server is already running in this MCP process, returns
    OK without restarting anything (only the served file is switched). Opens
    the browser automatically.

    Args:
        file: Absolute or relative path to the HTML file to edit.
        port: TCP port for the HTTP server. Omit it (default) to auto-pick a
            free port (preferred default, then 7840-7849): starting several
            independent ``mcp-htmleditor mcp`` processes, each editing its
            own file, then lets multiple presentations coexist without
            colliding on the same port. Pass an explicit port only when you
            need a specific one; it is used as-is and the call fails clearly
            if it is already taken.

    Returns:
        Dict with keys: ok, url, file, port, started (bool). `port` is the
        port actually bound, which may differ from the requested one when
        it was auto-picked.
    """
    state = get_state()

    with trace_span("mcp.start_server", {"file.path": _span_path(file)}) as span:
        _require_encodable_file(file)
        if not is_utf8_encodable(default_host()):
            raise ToolError(UNENCODABLE_BIND_ADDRESS)
        abs_file = str(Path(file).resolve())
        already_running = is_server_running() and state.current_file == abs_file

        if already_running:
            started, bound_port = False, state.port
        else:
            started, bound_port = start_http_server(abs_file, port)

        url = f"http://localhost:{bound_port}/"
        if not already_running:
            webbrowser.open(url)

        span.set_attribute("server.started", started)
        span.set_attribute("server.port", bound_port)
        logger.info("start_server file=%s port=%d started=%s", abs_file, bound_port, started)
        return {
            "ok": True,
            "url": url,
            "file": abs_file,
            "port": bound_port,
            "started": started,
        }


@mcp.tool()
def stop_server() -> dict[str, Any]:
    """Stop the WYSIWYG HTTP server.

    Returns:
        Dict with key: ok.
    """
    with trace_span("mcp.stop_server"):
        stop_http_server()
    return {"ok": True}


@mcp.tool()
def get_status() -> dict[str, Any]:
    """Return the current server status.

    Returns:
        Dict with keys: file, port, pid, update_in_progress, update_expires_in, mtime, running.
        `update_expires_in` is the whole seconds left on the update flag (1 to 120), else null.
    """
    state = get_state()
    with trace_span("mcp.get_status", {"server.running": is_server_running()}):
        return {**state.snapshot(), "running": is_server_running()}


@mcp.tool()
def open_file(file: str) -> dict[str, Any]:
    """Change the HTML file being served.

    The browser will pick up the change on its next poll cycle
    (within poll_interval ms) and reload the content automatically.

    Args:
        file: Path to the new HTML file.

    Returns:
        Dict with keys: ok, file.
    """
    state = get_state()
    with trace_span("mcp.open_file", {"file.path": _span_path(file)}):
        _require_encodable_file(file)
        abs_file = str(Path(file).resolve())
        state.set_file(abs_file)
    logger.info("open_file %s", abs_file)
    return {"ok": True, "file": abs_file}


@mcp.tool()
def update_start() -> dict[str, Any]:
    """Signal that a content modification is starting.

    Sets the update_in_progress flag so the browser shows the
    'modification en cours' overlay and does not apply concurrent
    mtime-triggered reloads. The flag expires by itself 120 seconds after the
    last call; calling again restarts the 120 seconds.

    Returns:
        Dict with keys: ok, expires_in (seconds, 120).
    """
    state = get_state()
    with trace_span("mcp.update_start", {"file.path": state.current_file or ""}):
        expires_in = state.start_update()
    return {"ok": True, "expires_in": expires_in}


@mcp.tool()
def update_end() -> dict[str, Any]:
    """Signal that a content modification is complete.

    Clears the update_in_progress flag. The browser will detect the
    changed mtime on the next poll and reload the content automatically.

    Returns:
        Dict with key: ok.
    """
    state = get_state()
    with trace_span("mcp.update_end", {"file.path": state.current_file or ""}):
        state.end_update()
    return {"ok": True}


@mcp.tool()
def layout_arch_diagram(file: str, diagram_id: str | None = None) -> dict[str, Any]:
    """Compute and write the layout of every declarative arch-diagram in a file.

    The LLM authors topology only (arch-row / arch-node / arch-edge / arch-lane,
    see skill/topics/arch-diagram.md), never coordinates. This tool derives the
    final data-x/data-y/data-width/data-height percentages deterministically:
    no collision between nodes, straight connectors on aligned columns, labels
    centered on their segment by construction, lane boxes sized from the union
    of the rows they declare. Diagrams with no arch-row child (legacy, hand
    authored data-x/data-y) are left untouched, so both formats coexist.

    Args:
        file: Path to the HTML file to update in place.
        diagram_id: Restrict the recompute to the diagram whose data-diagram-id
            matches, when a file has more than one. Omit to process every
            declarative diagram in the file.

    Returns:
        Dict with keys: ok, file, diagrams_updated, warnings.
    """
    with trace_span("mcp.layout_arch_diagram", {"file.path": _span_path(file)}) as span:
        _require_encodable_file(file)
        abs_file = str(Path(file).resolve())
        report = layout_file(abs_file, diagram_id=diagram_id)
        span.set_attribute("arch_layout.diagrams_updated", report.diagrams_updated)
        span.set_attribute("arch_layout.warnings", len(report.warnings))
        return {
            "ok": True,
            "file": report.file,
            "diagrams_updated": report.diagrams_updated,
            "warnings": list(report.warnings),
        }


def _require_encodable_file(file: str) -> None:
    if not is_utf8_encodable(file):
        raise ToolError(UNENCODABLE_FILE_NAME)


def _span_path(file: str) -> str:
    """The ``file.path`` span attribute: the resolved path, or ``file`` as given when resolving would raise."""
    return str(Path(file).resolve()) if is_utf8_encodable(file) else file


def run_mcp_server() -> None:
    """Entry point: run the MCP server over stdio transport.

    Logging goes to stderr and to the log file only: stdout carries the MCP
    protocol frames.
    """
    logger.info("Starting MCP server (stdio transport)")
    mcp.run(transport="stdio")


@mcp.tool()
def get_skill(type: str | None = None) -> str:  # noqa: A002 - argument name "type" is the contract
    """Return the skill core, or one topic when type is given.

    Same text as ``mcp-htmleditor skill`` (``--type <topic>`` when type is set).

    Args:
        type: Topic name. Omit it to get the core.

    Raises:
        ToolError: the topic is unknown, empty, or not installed (or the core is missing).
    """
    with trace_span("mcp.get_skill", {"skill.topic": type or "core"}):
        library = build_library()
        try:
            return library.core_output() if type is None else library.topic_output(type)
        except SkillError as exc:
            raise ToolError(exc.message) from exc


@mcp.tool()
def outline(file: str) -> dict[str, Any]:
    """Read the structure of a file: charter, type, slides and headings, without any image data.

    Same object as the JSON printed by ``mcp-htmleditor outline``.

    Args:
        file: Path to the HTML file.

    Raises:
        ToolError: the file is missing or unreadable (the command line error line without ``error: ``).
    """
    with trace_span("mcp.outline", {"file.path": file}):
        try:
            return read_outline(file)
        except DeckError as exc:
            raise ToolError(str(exc)) from exc


@mcp.tool()
def get_slide(file: str, id: str) -> str:  # noqa: A002 - argument name "id" is the contract
    """Read the HTML of one slide; images with a data address over 1 000 characters become data:ref:img-N.

    Same text as ``mcp-htmleditor get-slide``.

    Args:
        file: Path to the presentation.
        id: Slide id, for example ``slide-3``.

    Raises:
        ToolError: the file is missing, is not a presentation, or the id is unknown.
    """
    with trace_span("mcp.get_slide", {"file.path": file, "slide.id": id}):
        try:
            return read_slide(file, id)
        except DeckError as exc:
            raise ToolError(str(exc)) from exc


@mcp.tool()
def patch(file: str, ops: list[Any], dry_run: bool = False) -> dict[str, Any]:
    """Apply a list of operations to a presentation in one atomic write: every operation or none.

    Operations (objects with an ``op`` field): ``set_text`` (id, selector, text), ``replace_slide`` (id, html),
    ``insert_slide`` (after, html), ``delete_slide`` (id), ``move_slide`` (id, after). Counters, ``TOTAL`` and
    ``slideNames`` are renumbered after a structural patch. The editor flag ``update_in_progress`` is true only
    around the write; a dry run or a patch that changes nothing writes nothing and leaves the flag alone.
    Same result as ``mcp-htmleditor patch``.

    Args:
        file: Path to the presentation.
        ops: The operations, validated all together before anything is written.
        dry_run: Validate and report only; write nothing.

    Returns:
        Dict with keys: ok, changed, slides, problems, plus dry_run when it was requested.

    Raises:
        ToolError: an operation is invalid or the write fails (the command line error line without ``error: ``).
    """
    with trace_span("mcp.patch", {"file.path": file}):
        try:
            return apply_patch(file, ops, dry_run=dry_run, set_update_flag=get_state().set_update_flag)
        except DeckError as exc:
            raise ToolError(str(exc)) from exc


@mcp.tool()
def lint(file: str) -> dict[str, Any]:
    """Check a file against the structure and charter rules and report every problem with a verdict.

    Same object as the JSON printed by ``mcp-htmleditor lint --json``; a file with errors is still a result,
    read ``errors`` to decide.

    Args:
        file: Path to the HTML file.

    Returns:
        Dict with keys: problems (code, severity, slide, message), errors, warnings.

    Raises:
        ToolError: the file is missing or unreadable (the command line error line without ``error: ``).
    """
    with trace_span("mcp.lint", {"file.path": file}):
        try:
            return lint_file(file)
        except DeckError as exc:
            raise ToolError(str(exc)) from exc


@mcp.tool()
def list_templates() -> list[dict[str, str]]:
    """List the template keys with their description, in the order of ``mcp-htmleditor templates``."""
    with trace_span("mcp.list_templates"):
        return list_template_entries()


@mcp.tool()
def new_file(template: str, file: str) -> dict[str, Any]:
    """Create a file from a template key; an existing target is refused. Nothing is served or opened.

    Same operation as ``mcp-htmleditor new`` without ``--serve``; call ``start_server`` to edit the file.

    Args:
        template: A key returned by ``list_templates``.
        file: Path of the file to create; parent folders are created.

    Returns:
        Dict with keys: ok, file (the path as given).

    Raises:
        ToolError: unknown template, existing target or failed write.
    """
    with trace_span("mcp.new_file", {"file.path": file, "template.key": template}):
        try:
            create_file(template, file)
        except DeckError as exc:
            raise ToolError(str(exc)) from exc
        return {"ok": True, "file": file}


@mcp.tool()
def export(file: str, format: str, output: str) -> dict[str, Any]:  # noqa: A002 - argument name "format" is the contract
    """Export a presentation to pptx or a document to docx.

    Same operation as ``mcp-htmleditor export``.

    Args:
        file: Path to the HTML source.
        format: ``pptx`` or ``docx``.
        output: Path of the file to write.

    Returns:
        Dict with keys: ok, output, warnings (the export warnings, a list of text).

    Raises:
        ToolError: unknown format, missing file, no slide to export, pandoc missing or failing.
    """
    with trace_span("mcp.export", {"file.path": file, "export.format": format}):
        try:
            outcome = export_file(file, format, output)
        except DeckError as exc:
            raise ToolError(str(exc)) from exc
        return {"ok": True, "output": outcome.output, "warnings": outcome.warnings}


@mcp.tool()
def history(file: str) -> dict[str, Any]:
    """List the saved previous versions of a file, newest first.

    A version is kept before a browser save, a ``patch`` or a ``restore`` changes the file. Same result as
    ``mcp-htmleditor history``.

    Args:
        file: Path to the file.

    Returns:
        Dict with keys: file (absolute path), versions (list of ``{id, bytes, reason}``).

    Raises:
        ToolError: the file is missing (the command line error line without ``error: ``).
    """
    with trace_span("mcp.history", {"file.path": file}):
        try:
            target, versions = list_versions(file)
        except DeckError as exc:
            raise ToolError(str(exc)) from exc
        return {
            "file": str(target),
            "versions": [{"id": v.id, "bytes": v.bytes, "reason": v.reason} for v in versions],
        }


@mcp.tool()
def restore(file: str, id: str) -> dict[str, Any]:  # noqa: A002 - argument name "id" is the contract
    """Put a previous version of a file back by id; the replaced content is kept in the history.

    Same result as ``mcp-htmleditor restore``.

    Args:
        file: Path to the file.
        id: A version id from ``history``.

    Returns:
        Dict with keys: ok, file (absolute path), id.

    Raises:
        ToolError: unknown id, missing file, template, or failed write (the command line error line without
            ``error: ``).
    """
    with trace_span("mcp.restore", {"file.path": file, "history.id": id}):
        try:
            target = restore_version(file, id)
        except DeckError as exc:
            raise ToolError(str(exc)) from exc
        return {"ok": True, "file": str(target), "id": id}


@mcp.tool()
def list_requests(file: str) -> dict[str, Any]:
    """List the requests the person queued in the editor for a file, oldest first.

    Every status is listed (pending, done, skipped); deleted requests are gone.

    Args:
        file: Path to the file.

    Returns:
        Dict with keys: file (absolute path), requests (list of ``{id, slide, title, queued, instruction,
        status, reason}``).

    Raises:
        ToolError: the file is missing or its request record is unreadable.
    """
    with trace_span("mcp.list_requests", {"file.path": _span_path(file)}):
        try:
            path = require_file(file)
            requests = build_request_service().list_requests(path)
        except RequestError as exc:
            raise ToolError(exc.message) from exc
        return {"file": str(path), "requests": [request_to_dict(request) for request in requests]}


@mcp.tool()
def complete_request(file: str, id: str, status: str, reason: str | None = None) -> dict[str, Any]:  # noqa: A002 - argument name "id" is the contract
    """Mark a request done, or skipped with a reason.

    ``status`` is a plain string so the product message answers a wrong value. A reason is required for
    ``skipped`` and ignored for ``done``.

    Args:
        file: Path to the file.
        id: A request id from ``list_requests``.
        status: ``done`` or ``skipped``.
        reason: Why the request is skipped.

    Returns:
        Dict with keys: ok, id, status.

    Raises:
        ToolError: the file is missing, the id is unknown, the status or reason is invalid, or the request is
            already completed.
    """
    with trace_span("mcp.complete_request", {"file.path": _span_path(file)}):
        try:
            path = require_file(file)
            done = build_request_service().complete(path, id, status, reason)
        except RequestError as exc:
            raise ToolError(exc.message) from exc
        return {"ok": True, "id": done.id, "status": done.status}


@mcp.tool()
def write_review(file: str, suggestions: Any) -> dict[str, Any]:
    """Replace the AI suggestions shown in the editor for a file (at most 6).

    ``suggestions`` is untyped on purpose: the service answers a non list or a malformed item with its own
    message. Each item is an object with ``id`` (unique), ``slide`` (a slide id or null), ``title`` (at most 60
    characters), ``why`` and ``change``.
    Other keys are dropped and every suggestion starts not applied.

    Args:
        file: Path to the file.
        suggestions: Array of at most 6 objects {id, slide, title, why, change}; it replaces the previous review.

    Returns:
        Dict with keys: ok, count.

    Raises:
        ToolError: the file is missing, the list is longer than 6 or an item breaks a rule.
    """
    with trace_span("mcp.write_review", {"file.path": _span_path(file)}):
        try:
            path = require_file(file)
            count = build_request_service().write_review(path, suggestions)
        except RequestError as exc:
            raise ToolError(exc.message) from exc
        return {"ok": True, "count": count}


@mcp.tool()
def render(
    file: str,
    slide: str | None = None,
    scale: float = 0.5,
    report: bool = False,
    report_only: bool = False,
) -> dict[str, Any]:
    """Render one slide of a presentation to a PNG picture and, on request, report its layout problems.

    Needs Chromium (``make install-browser``). Never modifies the file nor the state of a running editor. A plain
    function on purpose: fastmcp runs it in a worker thread without an event loop, which Playwright's sync API needs.

    Args:
        file: Path to the presentation.
        slide: Id of the slide to render (default: the first).
        scale: Scale of the picture, 0.1 to 1 (default 0.5, a 480x270 picture).
        report: Also measure the rendered slide and return its layout problems.
        report_only: Measure every slide and write no picture; cannot be combined with slide, a scale other than
            the default, or report.

    Returns:
        Dict with keys: ok, path, width, height, problems (a list of {kind, slide, message}). path, width and
        height are null for report_only; problems is empty unless report or report_only is set.

    Raises:
        ToolError: the file is missing or not a presentation, the options conflict, the slide id is unknown or
            Chromium is not installed (same messages as the command line).
    """
    with trace_span("mcp.render", {"file.path": _span_path(file)}):
        try:
            result = render_deck(
                file,
                slide=slide,
                scale=None if scale == DEFAULT_SCALE else scale,
                report=report,
                report_only=report_only,
            )
        except DeckError as exc:
            raise ToolError(str(exc)) from exc
        return result_to_dict(result)


def registered_tool_names() -> list[str]:
    """Names of the tools registered on the server, in registration order.

    Synchronous. When the calling thread already runs an event loop (a sync Playwright session
    keeps one alive), the listing runs in a worker thread with its own loop instead of nesting
    ``asyncio.run``; async callers should still compute the names before awaiting.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _list_tool_names()
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_list_tool_names).result()


def _list_tool_names() -> list[str]:
    return [tool.name for tool in asyncio.run(mcp.list_tools())]
