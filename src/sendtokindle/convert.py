"""Markdown to EPUB conversion with Pandoc (SPEC §7.2, §9)."""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from .config import Config, KindleError
from .paths import check_size, is_within, safe_filename

ASSETS = Path(__file__).parent / "assets"
INPUT_FORMAT = "gfm+yaml_metadata_block+footnotes"
PANDOC_TIMEOUT_SECONDS = 60
BLOCKED_IMAGES_VAR = "SENDTOKINDLE_BLOCKED_IMAGES"  # read by assets/drop_images.lua


@dataclass(frozen=True)
class Book:
    path: Path
    title: str
    warnings: list[str]


def run_pandoc(args: list[str], extra_env: dict[str, str] | None = None) -> str:
    try:
        result = subprocess.run(
            ["pandoc", *args],
            capture_output=True,
            text=True,
            timeout=PANDOC_TIMEOUT_SECONDS,
            env={**os.environ, **(extra_env or {})},
        )
    except FileNotFoundError:
        raise KindleError("Pandoc is not installed.") from None
    except subprocess.TimeoutExpired:
        raise KindleError(
            f"Pandoc took longer than {PANDOC_TIMEOUT_SECONDS} s and was stopped."
        ) from None
    if result.returncode != 0:
        raise KindleError("Pandoc failed: " + "\n".join(result.stderr.strip().splitlines()[:5]))
    return result.stdout


def _image_problem(src: str, base: Path, data_dir: Path) -> str | None:
    """Why an image reference must not be embedded, or None if it is fine."""
    if src.startswith("data:"):
        return None
    if urlparse(src).scheme:
        return "remote image skipped"
    path = base / unquote(src)
    if not is_within(path, data_dir):
        return "image outside the mounted folder skipped"
    if not path.is_file():
        return "image not found, skipped"
    return None


def markdown_to_epub(
    source: Path,
    out_dir: Path,
    config: Config,
    title: str | None = None,
    author: str | None = None,
    toc: bool = True,
) -> Book:
    # Defaults go in a metadata file so the document's front matter overrides them;
    # explicit tool arguments go on the command line so they override the front matter.
    defaults = out_dir / "defaults.json"
    defaults.write_text(
        json.dumps({"author": config.default_author, "lang": config.default_language})
    )
    metadata = ["--metadata-file", str(defaults)]
    if author:
        metadata += ["--metadata", f"author={author}"]

    info = json.loads(
        run_pandoc([str(source), "-f", INPUT_FORMAT, *metadata, "-t", str(ASSETS / "inspect.lua")])
    )
    resolved_title = title or info.get("title") or info.get("heading") or source.stem

    images = info.get("images") or []  # an empty Lua table may encode as {}
    problems = {src: _image_problem(src, source.parent, config.data_dir) for src in images}
    blocked = [src for src, problem in problems.items() if problem]

    output = out_dir / safe_filename(resolved_title, ".epub")
    args = [str(source), "-f", INPUT_FORMAT, "-t", "epub3", "-o", str(output), *metadata]
    args += ["--metadata", f"title={resolved_title}", "--resource-path", str(source.parent)]
    args += ["--css", str(ASSETS / "kindle.css"), "--lua-filter", str(ASSETS / "drop_images.lua")]
    args += ["--syntax-highlighting", "monochrome"]
    if toc:
        args.append("--toc")
    run_pandoc(args, {BLOCKED_IMAGES_VAR: json.dumps(blocked)})

    if not output.is_file():
        raise KindleError("Pandoc did not produce an EPUB file.")
    check_size(output, config.max_attachment_mb)
    return Book(output, resolved_title, [f"{problems[src]}: {src}" for src in blocked])
