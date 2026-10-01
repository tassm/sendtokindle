from pathlib import Path

from sendtokindle.config import Config, load_config

ENV = {
    "KINDLE_EMAIL": "reader_1234@kindle.com",
    "SMTP_USERNAME": "me@gmail.com",
    "SMTP_PASSWORD": "app-password",
}


def make_config(data_dir: Path | str = "/data", **overrides: str) -> Config:
    return load_config({**ENV, "DATA_DIR": str(data_dir), **overrides})
