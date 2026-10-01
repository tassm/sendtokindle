"""Integration tests against the real Pandoc; run inside the Docker image (see README)."""

import base64
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from helpers import make_config
from sendtokindle.convert import markdown_to_epub

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQ"
    "AAAABJRU5ErkJggg=="
)

DOCUMENT = """\
---
title: Front Matter Title
author: Ada Lovelace
---

# First Heading

Unicode: café, 日本語, emoji 📚.

| Name | Value |
|------|-------|
| a    | 1     |

```python
print("hello")
```

A footnote.[^1]

![Local](img/pic.png)
![Remote](https://example.com/remote.png)
![Escape](../outside.png)
![Missing](nope.png)

[^1]: The note.
"""


@unittest.skipUnless(shutil.which("pandoc"), "pandoc not installed")
class MarkdownToEpubTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.data, self.out = root / "data", root / "out"
        (self.data / "img").mkdir(parents=True)
        self.out.mkdir()
        (self.data / "img" / "pic.png").write_bytes(PNG)
        (root / "outside.png").write_bytes(PNG)
        self.source = self.data / "notes.md"
        self.config = make_config(self.data)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def convert(self, markdown: str, **kwargs: str) -> tuple:
        self.source.write_text(markdown, encoding="utf-8")
        book = markdown_to_epub(self.source, self.out, self.config, **kwargs)
        return book, zipfile.ZipFile(book.path)

    def opf(self, epub: zipfile.ZipFile) -> str:
        return epub.read(next(n for n in epub.namelist() if n.endswith(".opf"))).decode()

    def test_full_document(self) -> None:
        book, epub = self.convert(DOCUMENT)
        names = epub.namelist()

        first = epub.infolist()[0]
        self.assertEqual((first.filename, first.compress_type), ("mimetype", zipfile.ZIP_STORED))
        self.assertEqual(epub.read("mimetype"), b"application/epub+zip")
        self.assertIn("META-INF/container.xml", names)

        self.assertEqual(book.title, "Front Matter Title")
        self.assertEqual(book.path.name, "Front Matter Title.epub")
        opf = self.opf(epub)
        self.assertIn("Front Matter Title", opf)
        self.assertIn("Ada Lovelace", opf)
        self.assertIn("urn:uuid:", opf)

        images = [n for n in names if n.endswith(".png")]
        self.assertEqual(len(images), 1, images)

        self.assertEqual(
            book.warnings,
            [
                "remote image skipped: https://example.com/remote.png",
                "image outside the mounted folder skipped: ../outside.png",
                "image not found, skipped: nope.png",
            ],
        )
        text = "".join(epub.read(n).decode() for n in names if n.endswith(".xhtml"))
        for expected in ("<table", "café", "日本語", "footnote", "First Heading", "Remote"):
            self.assertIn(expected, text)

    def test_title_and_author_resolution(self) -> None:
        book, epub = self.convert("# Only Heading\n\nText.\n")
        self.assertEqual(book.title, "Only Heading")
        self.assertIn("Unknown", self.opf(epub))

        book, _ = self.convert("No headings here.\n")
        self.assertEqual(book.title, "notes")

        book, epub = self.convert(DOCUMENT, title="Override", author="Grace Hopper")
        self.assertEqual(book.title, "Override")
        self.assertIn("Grace Hopper", self.opf(epub))
        self.assertNotIn("Ada Lovelace", self.opf(epub))


if __name__ == "__main__":
    unittest.main()
