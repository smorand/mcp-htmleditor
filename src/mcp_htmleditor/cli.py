"""CLI entry point for mcp-htmleditor.

``click.echo`` carries the user facing output (what the human asked for) while
``logging`` carries the technical diagnostics; ``-v`` raises the log level to
DEBUG, ``-q`` silences everything but errors. Logging and tracing are configured
once, in the group callback, and the resulting settings are passed down.
"""

from __future__ import annotations

import logging
import os
import webbrowser
from pathlib import Path

import click

from .config import get_settings
from .logging_config import setup_logging
from .tracing import configure_tracing, trace_span
from .version import __version__

logger = logging.getLogger(__name__)


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
def skill_cmd() -> None:
    """Print the full mcp-htmleditor skill (index + all sub-documents).

    Used by the dynamic Pi skill: it simply runs `mcp-htmleditor skill`
    so the skill content lives here and stays in sync with the tool.
    """
    from .skill_content import build_skill_content

    click.echo(build_skill_content())


@main.command("templates")
def templates_cmd() -> None:
    """List the available presentation/document templates."""
    from .templates import list_templates

    click.echo("Templates disponibles (mcp-htmleditor new <key> <fichier>):\n")
    for key, desc in list_templates():
        click.echo(f"  {key:<8} {desc}")


@main.command("new")
@click.argument("template")
@click.argument("output_file")
@click.option("--serve", is_flag=True, help="Ouvrir l'éditeur sur le fichier créé.")
@click.option("--port", default=None, type=int, help="HTTP port (avec --serve).")
@click.option("--host", default=None, help="Adresse d'écoute (avec --serve).")
@click.option("--no-browser", is_flag=True, help="Ne pas ouvrir le navigateur (avec --serve).")
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
    import shutil

    from .templates import list_templates, template_path

    try:
        src = template_path(template)
    except KeyError:
        keys = ", ".join(k for k, _ in list_templates())
        raise click.ClickException(f"Template inconnu: '{template}'. Templates disponibles: {keys}") from None
    except FileNotFoundError as exc:
        raise click.ClickException(f"Fichier template manquant: {exc}") from None

    dest = Path(output_file)
    if dest.exists():
        raise click.ClickException(f"Le fichier existe déjà: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with trace_span("file.write", {"file.path": str(dest), "template.key": template}) as span:
        shutil.copyfile(src, dest)
        span.set_attribute("file.size", dest.stat().st_size)
    logger.info("Created %s from template %s", dest, template)
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


@main.command("export")
@click.argument("format", type=click.Choice(["pptx", "docx"]))
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False))
@click.argument("output_file")
def export_cmd(format: str, input_file: str, output_file: str) -> None:  # noqa: A002 - CLI argument name
    """Export an HTML file to PPTX or DOCX.

    FORMAT is one of: pptx, docx
    INPUT_FILE is the source HTML file.
    OUTPUT_FILE is the destination file path.
    """
    if format == "pptx":
        _export_pptx(input_file, output_file)
    else:
        _export_docx(input_file, output_file)


def _export_pptx(input_file: str, output_file: str) -> None:
    """Run the PPTX export and print its report."""
    from .export.to_pptx import to_pptx

    click.echo(f"Exporting {input_file} → {output_file} (PPTX)")
    report = to_pptx(input_file, output_file)
    for warning in report.warnings:
        click.echo(f"Attention: {warning}", err=True)
    if report.slide_count == 0:
        raise click.ClickException(
            'Aucune slide exportee: verifiez que le document contient des elements data-type="slide".'
        )
    click.echo(f"Done. {report.slide_count} slide(s) exportee(s).")


def _export_docx(input_file: str, output_file: str) -> None:
    """Run the DOCX export and print its report."""
    import subprocess

    from .export.to_docx import to_docx

    click.echo(f"Exporting {input_file} → {output_file} (DOCX via pandoc)")
    try:
        result = to_docx(input_file, output_file)
    except FileNotFoundError:
        message = "pandoc introuvable dans le PATH: installez pandoc pour exporter en DOCX."
        raise click.ClickException(message) from None
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or f"code de sortie {exc.returncode}"
        raise click.ClickException(f"pandoc a echoue: {detail}") from None

    if result.reference_docx is not None:
        click.echo(f"Charte: {result.charter} (reference.docx: {result.reference_docx})")
    elif result.charter is None:
        click.echo("Charte: standard (styles pandoc par defaut)")
    for warning in result.warnings:
        click.echo(f"Attention: {warning}", err=True)
    click.echo("Done.")
