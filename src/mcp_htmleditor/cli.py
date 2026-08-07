"""CLI entry point for mcp-htmleditor."""

from __future__ import annotations

import os
import webbrowser
from pathlib import Path

import click


@click.group()
def main() -> None:
    """mcp-htmleditor: WYSIWYG HTML editor with MCP server support."""


@main.command("mcp")
def mcp_cmd() -> None:
    """Start the MCP server using stdio transport.

    Connect your LLM agent to this process via stdin/stdout.
    """
    from .mcp_server import run_mcp_server

    run_mcp_server()


@main.command("serve")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--port", default=7842, show_default=True, help="HTTP port.")
@click.option(
    "--poll",
    default=None,
    type=int,
    help="Polling interval in ms (overrides HTMLEDITOR_POLL_INTERVAL env var).",
)
def serve_cmd(file: str, port: int, poll: int | None) -> None:
    """Open an HTML file in the WYSIWYG browser editor.

    FILE is the path to the HTML file to edit.
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

    click.echo(f"Starting editor server on http://localhost:{port}/")
    click.echo(f"Editing: {abs_file}")
    click.echo("Press Ctrl+C to stop.")

    start_http_server(abs_file, port)

    url = f"http://localhost:{port}/"
    webbrowser.open(url)

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
def export_cmd(format: str, input_file: str, output_file: str) -> None:
    """Export an HTML file to PPTX or DOCX.

    FORMAT is one of: pptx, docx
    INPUT_FILE is the source HTML file.
    OUTPUT_FILE is the destination file path.
    """
    if format == "pptx":
        from .export.to_pptx import to_pptx

        click.echo(f"Exporting {input_file} → {output_file} (PPTX)")
        to_pptx(input_file, output_file)
        click.echo("Done.")
    else:
        from .export.to_docx import to_docx

        click.echo(f"Exporting {input_file} → {output_file} (DOCX via pandoc)")
        to_docx(input_file, output_file)
        click.echo("Done.")
