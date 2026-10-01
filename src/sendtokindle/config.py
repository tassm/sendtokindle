"""Configuration loaded from environment variables (SPEC §6)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

REQUIRED = ("KINDLE_EMAIL", "SMTP_USERNAME", "SMTP_PASSWORD")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class KindleError(Exception):
    """An anticipated failure whose message is shown to the user as-is."""


@dataclass(frozen=True)
class Config:
    kindle_email: str
    smtp_username: str
    smtp_password: str
    smtp_host: str
    smtp_port: int
    smtp_security: str
    sender_email: str
    default_author: str
    default_language: str
    data_dir: Path
    host_data_dir: str | None
    max_attachment_mb: int
    log_level: str
    problems: tuple[str, ...]

    @property
    def mounted_folder(self) -> str:
        return self.host_data_dir or str(self.data_dir)


def _parse_int(env: Mapping[str, str], name: str, default: int, problems: list[str]) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    if not raw.isdigit() or int(raw) == 0:
        problems.append(f"{name} must be a positive whole number, got {raw!r}.")
        return default
    return int(raw)


def load_config(env: Mapping[str, str] = os.environ) -> Config:
    """Read the configuration. Never raises; problems are collected in `Config.problems`."""

    def get(name: str, default: str = "") -> str:
        return env.get(name, "").strip() or default

    problems = [
        f"Missing configuration: {name}. Add it to your env file."
        for name in REQUIRED
        if not get(name)
    ]

    security = get("SMTP_SECURITY", "starttls").lower()
    if security not in ("starttls", "ssl"):
        problems.append(f"SMTP_SECURITY must be 'starttls' or 'ssl', got {security!r}.")

    log_level = get("LOG_LEVEL", "INFO").upper()
    if log_level not in LOG_LEVELS:
        problems.append(f"LOG_LEVEL must be one of {', '.join(LOG_LEVELS)}, got {log_level!r}.")
        log_level = "INFO"

    return Config(
        kindle_email=get("KINDLE_EMAIL"),
        smtp_username=get("SMTP_USERNAME"),
        smtp_password=env.get("SMTP_PASSWORD", ""),
        smtp_host=get("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=_parse_int(env, "SMTP_PORT", 587, problems),
        smtp_security=security,
        sender_email=get("SENDER_EMAIL") or get("SMTP_USERNAME"),
        default_author=get("DEFAULT_AUTHOR", "Unknown"),
        default_language=get("DEFAULT_LANGUAGE", "en"),
        data_dir=Path(get("DATA_DIR", "/data")),
        host_data_dir=get("HOST_DATA_DIR").rstrip("/") or None,
        max_attachment_mb=_parse_int(env, "MAX_ATTACHMENT_MB", 50, problems),
        log_level=log_level,
        problems=tuple(problems),
    )


def require_config() -> Config:
    """Load the configuration, raising `KindleError` if it is unusable."""
    config = load_config()
    if config.problems:
        raise KindleError("\n".join(config.problems))
    return config


def mask_email(address: str) -> str:
    """`name_1234@kindle.com` -> `n***1234@kindle.com`."""
    local, at, domain = address.partition("@")
    if len(local) <= 5:
        return f"{local[:1]}***{at}{domain}"
    return f"{local[:1]}***{local[-4:]}{at}{domain}"
