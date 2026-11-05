"""CLI entry point for mcp-htmleditor.

``click.echo`` carries the user facing output (what the human asked for) while
``logging`` carries the technical diagnostics; ``-v`` raises the log level to
DEBUG, ``-q`` silences everything but errors. Logging and tracing are configured
once, in the group callback, and the resulting settings are passed down.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import sys
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import click

from .config import get_settings
from .logging_config import setup_logging
from .tracing import configure_tracing
from .version import __version__

if TYPE_CHECKING:
    from .deck.tools import ExportOutcome

logger = logging.getLogger(__name__)


def deck_command[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Turn a ``DeckError`` raised by the command body into ``error: <message>`` and status 1."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        from .deck import DeckError

        try:
            return func(*args, **kwargs)
        except DeckError as exc:
            click.echo(f"error: {exc}", err=True)
            raise SystemExit(1) from exc

    return wrapper


@click.group()
@click.version_option(__version__, "-V", "--version", prog_name="mcp-htmleditor")
@click.option("-v", "--verbose", count=True, help="Augmenter la verbosite des logs (-v = DEBUG).")
@click.option("-q", "--quiet", is_flag=True, help="Ne journaliser que les erreurs.")
def main(verbose: int, quiet: bool) -> None:
    """mcp-htmleditor: WYSIWYG HTML editor with MCP server support."""
    settings = get_settings()
    setup_logging(verbosity=verbose, is_quiet=quiet, settings=settings)
    configure_tracing(settings)
    logger.debug("mcp-htmleditor %s starting (log dir: %s)", __version__, settings.log_dir)


@main.command("skill")
@click.option("--type", "topic", default=None, help="Print one topic instead of the core.")
@click.option("--all", "show_all", is_flag=True, help="Print the core then every topic.")
def skill_cmd(topic: str | None, show_all: bool) -> None:
    """Print the mcp-htmleditor skill: the core, one topic (--type) or everything (--all).

    Used by the dynamic Pi skill, so the skill content lives here and stays in
    sync with the tool. Errors are one line on stderr, nothing on stdout.
    """
    from .skill_content import BOTH_OPTIONS_MESSAGE, SkillError, build_library

    if topic is not None and show_all:
        click.echo(BOTH_OPTIONS_MESSAGE, err=True)
        raise click.exceptions.Exit(2)
    library = build_library()
    try:
        if show_all:
            text = library.all_output()
        elif topic is not None:
            text = library.topic_output(topic)
        else:
            text = library.core_output()
    except SkillError as exc:
        click.echo(exc.message, err=True)
        raise click.exceptions.Exit(exc.exit_code) from exc
    click.echo(text, nl=False)


@main.command("skill-audit")
@click.option("--json", "as_json", is_flag=True, help="Machine readable report.")
def skill_audit_cmd(as_json: bool) -> None:
    """Audit the skill: sizes and budgets, tool list, stale statements and the routing skill.

    Exits 0 when no problem is found, 1 otherwise. Never prompts.
    """
    from . import arch_checks
    from .config import routing_skill_path
    from .mcp_server import registered_tool_names
    from .skill_audit import format_json, format_text, read_routing_skill, run_audit, source_routing_skill_path
    from .skill_content import build_library

    library = build_library(read_checklist=arch_checks.read_shipped_checklist)
    routing_text = read_routing_skill(routing_skill_path(), source_routing_skill_path())
    report = run_audit(library, registered_tool_names(), routing_text)
    click.echo(format_json(report) if as_json else format_text(report), nl=False)
    if report.problems:
        raise click.exceptions.Exit(1)


@main.command("templates")
@deck_command
def templates_cmd() -> None:
    """List the available presentation/document templates."""
    from .deck.tools import template_listing

    click.echo("Templates disponibles (mcp-htmleditor new <key> <fichier>):\n")
    for entry in template_listing():
        click.echo(f"  {entry['key']:<8} {entry['description']}")


@main.command("new")
@click.argument("template")
@click.argument("output_file", type=click.Path(dir_okay=False))
@click.option("--serve", is_flag=True, help="Ouvrir l'éditeur sur le fichier créé.")
@click.option("--port", default=None, type=int, help="HTTP port (avec --serve).")
@click.option("--host", default=None, help="Adresse d'écoute (avec --serve).")
@click.option("--no-browser", is_flag=True, help="Ne pas ouvrir le navigateur (avec --serve).")
@deck_command
def new_cmd(  # noqa: PLR0913, PLR0917 - one parameter per CLI flag, click passes them by name
    template: str,
    output_file: str,
    serve: bool,
    port: int | None,
    host: str | None,
    no_browser: bool,
) -> None:
    """Create a new file from a template.

    TEMPLATE is a template key (see `mcp-htmleditor templates`): ei, carbon, doc.
    OUTPUT_FILE is the destination path for the new HTML file.
    """
    from .deck.tools import create_file

    dest = create_file(template, output_file)
    click.echo(f"Créé: {dest}  (template: {template})")

    if serve:
        settings = get_settings()
        _serve_file(
            str(dest),
            port,
            None,
            host if host is not None else settings.host,
            open_browser=not no_browser,
        )


@main.command("mcp")
def mcp_cmd() -> None:
    """Start the MCP server using stdio transport.

    Connect your LLM agent to this process via stdin/stdout.
    """
    from .mcp_server import run_mcp_server

    run_mcp_server()


@main.command("serve")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--port", default=None, type=int, help="HTTP port (défaut: HTMLEDITOR_PORT ou 7842).")
@click.option("--host", default=None, help="Adresse d'écoute (défaut: HTMLEDITOR_HOST ou localhost).")
@click.option(
    "--poll",
    default=None,
    type=int,
    help="Polling interval in ms (overrides HTMLEDITOR_POLL_INTERVAL env var).",
)
@click.option("--no-browser", is_flag=True, help="Ne pas ouvrir le navigateur (serveur distant, conteneur).")
def serve_cmd(file: str, port: int | None, host: str | None, poll: int | None, no_browser: bool) -> None:
    """Open an HTML file in the WYSIWYG browser editor.

    FILE is the path to the HTML file to edit. Without --port, a free port is
    auto-picked (preferred default, then 7840-7849) so several presentations
    can be served at once without colliding.
    """
    settings = get_settings()
    _serve_file(
        file,
        port,
        poll,
        host if host is not None else settings.host,
        open_browser=not no_browser,
    )


def _serve_file(file: str, port: int | None, poll: int | None, host: str, *, open_browser: bool = True) -> None:
    """Start the HTTP server on a file and block until Ctrl+C.

    `port` is None when the caller did not pass --port explicitly: start_http_server
    then auto-picks a free port (preferred default, then 7840-7849) instead of always
    binding the same one, so several presentations can be served concurrently.
    """
    import time

    from .http_server import start_http_server
    from .state import get_state

    if poll is not None:
        os.environ["HTMLEDITOR_POLL_INTERVAL"] = str(poll)

    abs_file = str(Path(file).resolve())
    state = get_state()
    if poll is not None:
        state.poll_interval = poll

    click.echo(f"Editing: {abs_file}")
    click.echo("Press Ctrl+C to stop.")

    try:
        _started, bound_port = start_http_server(abs_file, port, host)
    except OSError as exc:
        raise click.ClickException(str(exc)) from exc
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Serving on http://{host}:{bound_port}/")

    if open_browser:
        webbrowser.open(f"http://{host}:{bound_port}/")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\nStopping server.")
        from .http_server import stop_http_server

        stop_http_server()


@main.command("arch-checklist")
def arch_checklist_cmd() -> None:
    """Print the resolved arch-diagram QA checklist and where it lives.

    Resolution order: HTMLEDITOR_ARCH_CHECKS_DIR, then
    ~/.config/mcp-htmleditor/arch-checks/ (seeded once by `make install`, never
    overwritten on reinstall), then the bundled repo copy. Edit the resolved
    file directly to add or change a control: no code change, no reinstall.
    """
    from .arch_checks import checklist_path, read_checklist

    click.echo(f"Fichier: {checklist_path()}\n")
    content = read_checklist()
    if not content:
        click.echo("(checklist introuvable a cet emplacement)")
        return
    click.echo(content)


@main.command("arch-layout")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--diagram-id", default=None, help="Ne recalculer que le diagramme portant ce data-diagram-id.")
def arch_layout_cmd(file: str, diagram_id: str | None) -> None:
    """Compute and write the layout of every declarative arch-diagram in FILE.

    A diagram is "declarative" once it has at least one arch-row child; legacy
    diagrams (data-x/data-y written by hand) are left untouched. See
    skill/types/arch-diagram.md for the authored format.
    """
    from .arch_layout import layout_file

    report = layout_file(file, diagram_id=diagram_id)
    for warning in report.warnings:
        click.echo(f"Attention: {warning}", err=True)
    if report.diagrams_updated == 0:
        click.echo('Aucun diagramme declaratif trouve (data-type="arch-diagram" avec un arch-row): rien a faire.')
    else:
        click.echo(f"Done. {report.diagrams_updated} diagramme(s) recalcule(s).")


@main.command("outline")
@click.argument("file", type=click.Path(dir_okay=False))
@deck_command
def outline_cmd(file: str) -> None:
    """Print the structure of FILE as JSON: charter, type, slides or headings, never image data."""
    from .deck.read import outline

    click.echo(json.dumps(outline(file), separators=(",", ":"), ensure_ascii=False))


@main.command("get-slide")
@click.argument("file", type=click.Path(dir_okay=False))
@click.argument("slide_id")
@deck_command
def get_slide_cmd(file: str, slide_id: str) -> None:
    """Print the raw HTML of slide SLIDE_ID of FILE, large images replaced by data:ref:img-N."""
    from .deck.read import get_slide

    click.echo(get_slide(file, slide_id))


@main.command("lint")
@click.argument("file", type=click.Path(dir_okay=False))
@click.option("--json", "as_json", is_flag=True, help="Print the report as compact JSON only.")
@deck_command
def lint_cmd(file: str, as_json: bool) -> None:
    """Check FILE against the structure rules and print every problem then a verdict; exit 1 on an error."""
    from .deck import load_deck
    from .deck.lint import ERROR, format_report, lint_deck, report_dict

    problems = lint_deck(load_deck(file))
    if as_json:
        click.echo(json.dumps(report_dict(problems), separators=(",", ":"), ensure_ascii=False))
    else:
        click.echo("\n".join(format_report(problems)))
    if any(p.severity == ERROR for p in problems):
        raise SystemExit(1)


@main.command("patch")
@click.argument("file", type=click.Path(dir_okay=False))
@click.option("--ops", "ops_source", required=True, help="Operations JSON file, or - for standard input.")
@click.option("--dry-run", is_flag=True, help="Check and report, write nothing.")
@deck_command
def patch_cmd(file: str, ops_source: str, dry_run: bool) -> None:
    """Apply a JSON list of operations to FILE in one atomic write: every operation or none."""
    from .deck.patch import apply_patch, check_target

    check_target(file)  # before reading the operations, so a missing FILE is reported first
    result = apply_patch(file, _read_operations(ops_source), dry_run=dry_run)
    click.echo(json.dumps(result, separators=(",", ":"), ensure_ascii=False))


def _read_operations(source: str) -> object:
    from .deck import DeckError

    try:
        text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise DeckError(f"Cannot read {source}: {getattr(exc, 'strerror', None) or exc}") from exc
    try:
        return json.loads(text)
    except ValueError as exc:
        raise DeckError(f"Invalid operations JSON: {exc}") from exc


@main.command("history")
@click.argument("file", type=click.Path(dir_okay=False))
@deck_command
def history_cmd(file: str) -> None:
    """List the kept versions of FILE, newest first."""
    from .history import list_versions

    _, versions = list_versions(file)
    for version in versions:
        click.echo(f"{version.id}  {version.bytes} bytes  {version.reason}")
    if not versions:
        click.echo(f"No history for {file}")


@main.command("restore")
@click.argument("file", type=click.Path(dir_okay=False))
@click.argument("version_id")
@deck_command
def restore_cmd(file: str, version_id: str) -> None:
    """Put version VERSION_ID of FILE back, keeping the current content in the history first."""
    from .history import restore_version

    restore_version(file, version_id)
    click.echo(f"Restored {file} to {version_id}")


@main.command("requests")
@click.argument("file")
def requests_cmd(file: str) -> None:
    """List the requests queued for FILE, oldest first."""
    from .request_service import RequestError, build_request_service, require_file

    try:
        found = build_request_service().list_requests(require_file(file))
    except RequestError as exc:
        _request_fail(exc.message)
    for request in found:
        click.echo(f"{request.id}  {request.status}  {request.slide or '-'}  {request.title}")
    if not found:
        click.echo(f"No requests for {file}")


@main.command("request-done")
@click.argument("file")
@click.argument("request_id")
def request_done_cmd(file: str, request_id: str) -> None:
    """Mark request REQUEST_ID of FILE done."""
    _complete_request(file, request_id, "done", None)


@main.command("request-skip")
@click.argument("file")
@click.argument("request_id")
@click.option("--reason", default=None, help="Why the request is skipped (required).")
def request_skip_cmd(file: str, request_id: str, reason: str | None) -> None:
    """Mark request REQUEST_ID of FILE skipped, with a reason."""
    _complete_request(file, request_id, "skipped", reason)


def _complete_request(file: str, request_id: str, status: str, reason: str | None) -> None:
    from .request_service import RequestError, build_request_service, require_file

    try:
        build_request_service().complete(require_file(file), request_id, status, reason)
    except RequestError as exc:
        _request_fail(exc.message)
    click.echo(f"Request {request_id} marked {status}")


def _request_fail(message: str) -> NoReturn:
    click.echo(f"error: {message}", err=True)
    raise SystemExit(1)


@main.command("export")
@click.argument("format")
@click.argument("input_file", type=click.Path(dir_okay=False))
@click.argument("output_file", type=click.Path(dir_okay=False))
@deck_command
def export_cmd(format: str, input_file: str, output_file: str) -> None:  # noqa: A002 - CLI argument name
    """Export an HTML file to PPTX or DOCX.

    FORMAT is one of: pptx, docx
    INPUT_FILE is the source HTML file.
    OUTPUT_FILE is the destination file path.
    """
    from .deck.tools import export_file

    outcome = export_file(input_file, format, output_file)
    if format == "pptx":
        click.echo(f"Exporting {input_file} → {output_file} (PPTX)")
    else:
        click.echo(f"Exporting {input_file} → {output_file} (DOCX via pandoc)")
        _echo_charter(outcome)
    for warning in outcome.warnings:
        click.echo(f"Attention: {warning}", err=True)
    if format == "pptx":
        click.echo(f"Done. {outcome.slide_count} slide(s) exportee(s).")
    else:
        click.echo("Done.")


def _echo_charter(outcome: ExportOutcome) -> None:
    """Print the DOCX charter line, if any."""
    if outcome.reference_docx is not None:
        click.echo(f"Charte: {outcome.charter} (reference.docx: {outcome.reference_docx})")
    elif outcome.charter is None:
        click.echo("Charte: standard (styles pandoc par defaut)")
