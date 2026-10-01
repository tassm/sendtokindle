"""Host-to-container path mapping and confinement to the mounted folder (SPEC §7.1)."""

import os
import re
import unicodedata
from pathlib import Path

from .config import Config, KindleError

MAX_FILENAME_LENGTH = 100


def to_container_path(raw: str, data_dir: Path, host_data_dir: str | None) -> Path:
    """Map a host path, container path or relative path to a path inside the container."""
    if host_data_dir and (raw == host_data_dir or raw.startswith(host_data_dir + "/")):
        return data_dir / raw[len(host_data_dir) :].lstrip("/")
    return data_dir / raw  # an absolute `raw` replaces `data_dir`


def is_within(path: Path, root: Path) -> bool:
    """True if `path` resolves (following symlinks and `..`) to somewhere inside `root`."""
    return Path(os.path.realpath(path)).is_relative_to(os.path.realpath(root))


def check_size(path: Path, limit_mb: int) -> None:
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > limit_mb:
        raise KindleError(f"{path.name} is {size_mb:.0f} MB; the limit is {limit_mb} MB.")


def resolve_input(raw: str, config: Config, suffixes: tuple[str, ...], limit_mb: int) -> Path:
    """Resolve a user-supplied path to an existing, size-checked file inside the mount."""
    path = Path(os.path.realpath(to_container_path(raw, config.data_dir, config.host_data_dir)))
    if not is_within(path, config.data_dir):
        raise KindleError(
            f"{raw} is outside the mounted folder {config.mounted_folder}. "
            "Move the file into that folder or change the mount."
        )
    if path.suffix.lower() not in suffixes:
        raise KindleError(f"{raw} must be a {' or '.join(suffixes)} file.")
    if not path.is_file():
        raise KindleError(f"{raw} was not found in the mounted folder {config.mounted_folder}.")
    check_size(path, limit_mb)
    return path


def safe_filename(name: str, extension: str) -> str:
    """Make an attachment filename: no separators or control characters, bounded length."""
    if name.lower().endswith(extension):
        name = name[: -len(extension)]
    name = "".join(
        " " if c in "/\\" or unicodedata.category(c).startswith("C") else c for c in name
    )
    name = re.sub(r"\s+", " ", name).strip(" .")
    return (name or "document")[: MAX_FILENAME_LENGTH - len(extension)].rstrip(" .") + extension
