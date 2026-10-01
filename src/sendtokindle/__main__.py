import logging
import sys

from .config import load_config
from .server import build_server

logging.basicConfig(
    stream=sys.stderr, level=load_config().log_level
)  # stdout carries the MCP protocol
build_server().run("stdio")
