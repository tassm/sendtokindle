"""MCP server exposing the send_markdown, send_pdf and check_config tools (SPEC §7)."""

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import mailer
from .config import REQUIRED, Config, KindleError, load_config, mask_email, require_config
from .convert import markdown_to_epub, run_pandoc
from .paths import resolve_input, safe_filename

MAX_MARKDOWN_MB = 5


@contextmanager
def _as_tool_error() -> Iterator[None]:
    """Report anticipated failures to the model as tool errors (`isError: true`)."""
    try:
        yield
    except KindleError as error:
        raise ToolError(str(error)) from None


def _human_size(size: int) -> str:
    return f"{size / 1024:.0f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB"


def _sent_summary(
    config: Config, attachment: Path, filename: str, warnings: list[str] | None = None
) -> str:
    size = _human_size(attachment.stat().st_size)
    lines = [
        f'Sent "{filename}" ({size}) to {mask_email(config.kindle_email)}.',
        f"Amazon will email a delivery confirmation to {config.sender_email}; "
        "this usually takes 1–5 minutes.",
    ]
    if warnings:
        lines += ["Warnings:", *(f"- {warning}" for warning in warnings)]
    return "\n".join(lines)


def send_markdown(
    path: str, title: str | None = None, author: str | None = None, toc: bool = True
) -> str:
    with _as_tool_error():
        config = require_config()
        source = resolve_input(path, config, (".md", ".markdown"), MAX_MARKDOWN_MB)
        with tempfile.TemporaryDirectory() as out_dir:
            book = markdown_to_epub(source, Path(out_dir), config, title, author, toc)
            mailer.send(config, book.title, book.path, book.path.name)
            return _sent_summary(config, book.path, book.path.name, book.warnings)


def send_pdf(path: str, filename: str | None = None) -> str:
    with _as_tool_error():
        config = require_config()
        source = resolve_input(path, config, (".pdf",), config.max_attachment_mb)
        with source.open("rb") as file:
            if file.read(5) != b"%PDF-":
                raise KindleError(f"{path} is not a valid PDF file.")
        name = safe_filename(filename or source.name, ".pdf")
        subject = Path(name).stem
        if subject.strip().lower() == "convert":  # that subject makes Amazon convert the PDF
            subject = name
        mailer.send(config, subject, source, name)
        return _sent_summary(config, source, name)


def check_config(test_smtp: bool = False) -> str:
    config = load_config()
    lines = [
        f"{name}: {'set' if os.environ.get(name, '').strip() else 'MISSING'}" for name in REQUIRED
    ]
    lines += [f"Problem: {problem}" for problem in config.problems]

    try:
        lines.append("Pandoc: " + run_pandoc(["--version"]).splitlines()[0])
    except KindleError as error:
        lines.append(f"Pandoc: {error}")

    host = config.host_data_dir or "(HOST_DATA_DIR not set)"
    readable = config.data_dir.is_dir() and os.access(config.data_dir, os.R_OK)
    lines.append(
        f"Mounted folder: {host} -> {config.data_dir} "
        f"({'readable' if readable else 'NOT readable'})"
    )

    if not test_smtp:
        lines.append("SMTP login: not tested (pass test_smtp=true)")
    elif config.problems:
        lines.append("SMTP login: skipped until the problems above are fixed")
    else:
        try:
            mailer.check_login(config)
            lines.append(f"SMTP login: OK ({config.smtp_host}:{config.smtp_port})")
        except KindleError as error:
            lines.append(f"SMTP login: failed. {error}")
    return "\n".join(lines)


def build_server() -> MCPServer:
    config = load_config()
    mount = (
        f"Files must be inside the mounted folder {config.mounted_folder}; "
        "pass a full path in that folder or a path relative to it."
    )
    server = MCPServer(
        "sendtokindle", instructions=f"Sends documents to the user's Kindle by email. {mount}"
    )
    server.tool(
        description=(
            "Convert a Markdown (.md) file to EPUB and email it to the user's Kindle. "
            "Local images are embedded; remote images are skipped. The title defaults to the "
            f"front-matter title, then the first heading, then the filename. {mount}"
        )
    )(send_markdown)
    server.tool(description=f"Email a PDF file to the user's Kindle unchanged. {mount}")(send_pdf)
    server.tool(
        description=(
            "Report whether sendtokindle is configured: required settings (values hidden), "
            "Pandoc, the mounted folder and, if test_smtp is true, whether the SMTP login works. "
            "Sends nothing."
        )
    )(check_config)
    return server
