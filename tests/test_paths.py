import tempfile
import unittest
from pathlib import Path

from helpers import make_config
from sendtokindle.config import KindleError
from sendtokindle.paths import resolve_input, safe_filename, to_container_path


class ToContainerPathTest(unittest.TestCase):
    def test_mapping(self) -> None:
        data, host = Path("/data"), "/Users/me/Docs"
        self.assertEqual(
            to_container_path("/Users/me/Docs/a/b.md", data, host), Path("/data/a/b.md")
        )
        self.assertEqual(to_container_path("/data/a.md", data, host), Path("/data/a.md"))
        self.assertEqual(to_container_path("a.md", data, host), Path("/data/a.md"))
        self.assertEqual(
            to_container_path("/Users/me/Docsx/a.md", data, host), Path("/Users/me/Docsx/a.md")
        )
        self.assertEqual(to_container_path("~/a.md", data, host), Path("/data/~/a.md"))


class ResolveInputTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.data, self.outside = root / "data", root / "outside"
        self.data.mkdir()
        self.outside.mkdir()
        (self.data / "note.md").write_text("# Hi")
        (self.outside / "secret.md").write_text("secret")
        (self.data / "link.md").symlink_to(self.outside / "secret.md")
        self.config = make_config(self.data, HOST_DATA_DIR="/Users/me/Docs")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def resolve(self, raw: str) -> Path:
        return resolve_input(raw, self.config, (".md",), 5)

    def test_accepts_host_container_and_relative_paths(self) -> None:
        expected = self.data / "note.md"
        for raw in ("/Users/me/Docs/note.md", str(expected), "note.md"):
            self.assertEqual(self.resolve(raw), expected)

    def test_rejects_escapes(self) -> None:
        for raw in (
            "../outside/secret.md",
            "link.md",
            str(self.outside / "secret.md"),
            "/etc/passwd",
        ):
            with self.assertRaisesRegex(KindleError, "outside the mounted folder /Users/me/Docs"):
                self.resolve(raw)

    def test_rejects_wrong_extension_and_missing(self) -> None:
        (self.data / "a.txt").write_text("x")
        with self.assertRaisesRegex(KindleError, "must be a .md"):
            self.resolve("a.txt")
        with self.assertRaisesRegex(KindleError, "not found"):
            self.resolve("missing.md")

    def test_rejects_large_file(self) -> None:
        (self.data / "big.md").write_bytes(b"x" * (6 * 1024 * 1024))
        with self.assertRaisesRegex(KindleError, "limit is 5 MB"):
            self.resolve("big.md")


class SafeFilenameTest(unittest.TestCase):
    def test_sanitises(self) -> None:
        self.assertEqual(safe_filename("a/b\\c\x00d", ".epub"), "a b c d.epub")
        self.assertEqual(safe_filename("report.PDF", ".pdf"), "report.pdf")
        self.assertEqual(safe_filename("  ..  ", ".epub"), "document.epub")
        self.assertEqual(safe_filename("Ünïcödé 日本", ".epub"), "Ünïcödé 日本.epub")
        self.assertEqual(len(safe_filename("x" * 500, ".epub")), 100)


if __name__ == "__main__":
    unittest.main()
