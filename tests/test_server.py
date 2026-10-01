import asyncio
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import ENV


@unittest.skipUnless(importlib.util.find_spec("mcp"), "mcp not installed")
class ServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name).resolve()
        env = {**ENV, "DATA_DIR": str(self.data), "HOST_DATA_DIR": "/Users/me/Docs"}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

        from sendtokindle.server import build_server

        self.server = build_server()

    def call(self, name: str, arguments: dict) -> str:
        from mcp.server.mcpserver.exceptions import ToolError

        try:
            result = asyncio.run(self.server.call_tool(name, arguments))
        except ToolError as error:
            return f"ERROR: {error}"
        return result.content[0].text

    def test_lists_tools_with_mount_in_description(self) -> None:
        tools = {tool.name: tool for tool in asyncio.run(self.server.list_tools())}
        self.assertEqual(set(tools), {"send_markdown", "send_pdf", "check_config"})
        self.assertIn("/Users/me/Docs", tools["send_pdf"].description)

    def test_send_pdf(self) -> None:
        (self.data / "Paper.pdf").write_bytes(b"%PDF-1.7 content")
        with mock.patch("sendtokindle.mailer.send") as send:
            result = self.call("send_pdf", {"path": "/Users/me/Docs/Paper.pdf"})
        send.assert_called_once()
        self.assertEqual(send.call_args.args[1:], ("Paper", self.data / "Paper.pdf", "Paper.pdf"))
        self.assertIn('Sent "Paper.pdf"', result)

    def test_send_pdf_never_uses_convert_subject(self) -> None:
        (self.data / "convert.pdf").write_bytes(b"%PDF-1.7")
        with mock.patch("sendtokindle.mailer.send") as send:
            self.call("send_pdf", {"path": "convert.pdf"})
        self.assertEqual(send.call_args.args[1], "convert.pdf")

    def test_errors_are_tool_errors(self) -> None:
        (self.data / "fake.pdf").write_bytes(b"not a pdf")
        self.assertIn("not a valid PDF", self.call("send_pdf", {"path": "fake.pdf"}))
        self.assertIn(
            "outside the mounted folder", self.call("send_pdf", {"path": "/etc/passwd.pdf"})
        )
        with mock.patch.dict(os.environ, {"SMTP_PASSWORD": ""}):
            self.assertIn(
                "Missing configuration: SMTP_PASSWORD", self.call("send_pdf", {"path": "x.pdf"})
            )

    def test_check_config(self) -> None:
        result = self.call("check_config", {})
        self.assertIn("SMTP_PASSWORD: set", result)
        self.assertNotIn("app-password", result)
        self.assertIn("/Users/me/Docs ->", result)


if __name__ == "__main__":
    unittest.main()
