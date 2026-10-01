# sendtokindle MCP Server — Specification

**Status:** v0.3 (2026-10-01). Implemented; this version records implementation details.
**Owner:** Tasman Mayers

---

## 1. Overview

`sendtokindle` is a Model Context Protocol (MCP) server, packaged as a Docker image, that lets Claude Code and Claude Desktop deliver documents to a Kindle using Amazon's **Send to Kindle by email** service.

It does two things:

1. **Markdown → EPUB → Kindle.** It converts a Markdown file to a valid EPUB 3 file and emails it to the user's Kindle address.
2. **PDF → Kindle.** It emails a PDF to the Kindle unchanged.

## 2. Goals and non-goals

### Goals
- G1. Run as a self-contained Docker container. The image includes every conversion dependency, so the host needs only Docker.
- G2. Work with both Claude Code and Claude Desktop through the standard MCP stdio configuration.
- G3. Python implementation that follows the library policy in §4: prefer the standard library, use an established third-party library where one is the accepted standard, and never hand-roll a protocol.
- G4. Produce EPUBs that Amazon's Send to Kindle accepts and that look clean on a Kindle: headings, lists, code blocks, tables, footnotes, links, and local images.
- G5. Configure entirely through environment variables. No credentials in the image or in tool arguments.

### Non-goals (v1)
- Sending through any route other than SMTP email.
- Input formats other than Markdown and PDF.
- Managing Amazon's "Approved Personal Document E-mail List". The user does this manually.
- Multi-user or hosted deployment, and network (HTTP) MCP transport.
- Changing PDFs in any way.
- The features listed in §13 (Future features).

## 3. Background: Send to Kindle by email

- Each Kindle account has an address like `name_XXXX@kindle.com`.
- Amazon only accepts mail from senders on the account's **Approved Personal Document E-mail List**. The user's Gmail address must be added there.
- Accepted formats include EPUB and PDF. MOBI is no longer accepted.
- Size limit: 50 MB per email.
- Amazon sends a confirmation or failure notice to the sender asynchronously. The server cannot see that notice, so "sent" means "accepted by Gmail's SMTP server", not "arrived on the Kindle".

## 4. Technology and dependencies

| Concern | Choice | Type |
|---|---|---|
| Language | Python 3.12+ | — |
| MCP protocol | Official `mcp` Python SDK 2.x (`mcp.server.MCPServer`, formerly `FastMCP`), stdio transport, version pinned in `requirements.txt` | Third-party (accepted standard for MCP) |
| Markdown → EPUB | **Pandoc** binary installed in the image, called through `subprocess` | System binary |
| Email | `smtplib`, `email.message.EmailMessage`, `ssl` | stdlib |
| Paths / temp files | `pathlib`, `os.path.realpath`, `tempfile` | stdlib |
| Config | `os.environ` | stdlib |
| Logging | `logging`, to **stderr** only (stdout carries the protocol) | stdlib |
| Tests | `unittest` | stdlib |

**Pandoc version:** pin a specific upstream release (`.deb` from GitHub releases, chosen per architecture during the build) instead of Debian's older package. This gives a recent EPUB 3 writer and reproducible output.

**Library policy:**
1. Prefer the standard library where it covers the need well.
2. Use a third-party library when it is the commonly accepted standard for a protocol or format and is well maintained (recent releases, active issue tracking, wide adoption). Pin its version in `requirements.txt`.
3. **Never implement a protocol ourselves**, whether that is MCP/JSON-RPC, SMTP, MIME, or anything similar. Use the standard library's implementation (e.g. `smtplib`, `email`) or the accepted third-party one (e.g. the `mcp` SDK).
4. Each third-party dependency gets a line in the table above saying what it is for and why it is the standard choice.

## 5. Architecture

```
Claude Code / Desktop
        │  stdio (MCP over JSON-RPC 2.0)
        ▼
docker run -i --rm  sendtokindle
  src/sendtokindle/
  ├── __main__.py      entry point → server.run()
  ├── server.py        FastMCP app, tool registration
  ├── config.py        env-var loading + validation
  ├── paths.py         host↔container path mapping, confinement checks
  ├── convert.py       Markdown → EPUB (pandoc wrapper, metadata, CSS)
  ├── mailer.py        MIME message construction + SMTP send
  └── assets/
      ├── kindle.css       EPUB stylesheet
      ├── inspect.lua      Pandoc writer: title, author, first heading, image sources as JSON
      └── drop_images.lua  Pandoc filter: replaces blocked images with their alt text
```

- **Transport:** stdio only. The MCP client starts the container with `docker run -i --rm ...`, so the container lives for one client session.
- **Processing:** each tool call is synchronous. Pandoc writes into a per-call `tempfile.TemporaryDirectory()` inside the container, which is deleted after sending.
- **Statelessness:** nothing persists between calls, and nothing is written to the mounted folder.

## 6. Configuration (environment variables)

Provided with `docker run --env-file <file>`. The env file lives on the host, outside the repo, e.g. `~/.config/sendtokindle/env`, with permissions `600`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `KINDLE_EMAIL` | yes | — | Destination `@kindle.com` address |
| `SMTP_USERNAME` | yes | — | Gmail address |
| `SMTP_PASSWORD` | yes | — | Google **App Password** (needs 2-Step Verification on the account) |
| `SMTP_HOST` | no | `smtp.gmail.com` | |
| `SMTP_PORT` | no | `587` | |
| `SMTP_SECURITY` | no | `starttls` | `starttls` \| `ssl` |
| `SENDER_EMAIL` | no | `SMTP_USERNAME` | Must be on Amazon's approved list |
| `DEFAULT_AUTHOR` | no | `Unknown` | EPUB author when none is given or found |
| `DEFAULT_LANGUAGE` | no | `en` | EPUB `dc:language` |
| `DATA_DIR` | no | `/data` | Mount point for input files inside the container |
| `HOST_DATA_DIR` | no | — | The host folder mounted at `DATA_DIR`, used to translate host paths (§7.1) |
| `MAX_ATTACHMENT_MB` | no | `50` | Files larger than this are rejected before sending |
| `LOG_LEVEL` | no | `INFO` | |

Defaults target Gmail, but any SMTP server with username/password authentication works through the overrides.

**Startup behaviour:** missing or invalid configuration doesn't stop the server from starting. Every tool call (except `check_config`) returns a clear error naming the missing variable(s), so the problem shows up inside Claude rather than as a container that silently exits.

**Secrets:** `SMTP_PASSWORD` never appears in logs, tool results, or exception text. `KINDLE_EMAIL` is partly masked in results (`n***_1234@kindle.com`).

## 7. MCP tools

### 7.1 File input: mounted paths only

The only way files reach the server is through a host folder mounted into the container, normally read-only:

```
-v /Users/you/Documents:/data:ro   -e HOST_DATA_DIR=/Users/you/Documents
```

Path handling (`paths.py`):
1. Claude normally passes **host** paths (e.g. `/Users/you/Documents/notes/todo.md`). If the path starts with `HOST_DATA_DIR`, that prefix is replaced with `DATA_DIR`.
2. Container paths (`/data/notes/todo.md`) and paths relative to `DATA_DIR` (`notes/todo.md`) are also accepted.
3. `~` is not expanded. Inside the container it would mean the wrong home directory.
4. The resolved path (`os.path.realpath`) must be inside `DATA_DIR`. `..` and symlinks that lead outside it are rejected.
5. If a path isn't under the mount, the error explains this and shows the host folder that *is* mounted, so Claude can tell the user to move the file or change the mount.

The tool descriptions given to the model state which host folder is mounted (taken from `HOST_DATA_DIR` at startup), so Claude knows which files it can send.

### 7.2 Tool: `send_markdown`

Converts a Markdown file to EPUB and emails it to the Kindle.

| Argument | Type | Required | Notes |
|---|---|---|---|
| `path` | string | yes | `.md` / `.markdown` file under the mount |
| `title` | string | no | Overrides the detected title |
| `author` | string | no | Overrides front matter / `DEFAULT_AUTHOR` |
| `toc` | boolean | no, default `true` | Generate a table of contents |

**Title resolution:** `title` argument → YAML front-matter `title` → first level-1 heading → filename stem.
**Author resolution:** `author` argument → front-matter `author` → `DEFAULT_AUTHOR`.

**Steps:**
1. Check config, resolve and confine the path, check the extension, and check the size (Markdown ≤ 5 MB).
2. **Inspect** the document with Pandoc, using the `inspect.lua` custom writer. This gets the effective title and author (front matter merged with the defaults and arguments), the first level-1 heading, and every image source. Pandoc parses the YAML and Markdown, so neither is parsed by hand.
   - `DEFAULT_AUTHOR` and `DEFAULT_LANGUAGE` are passed with `--metadata-file`, so front matter overrides them.
   - The `author` argument is passed with `--metadata`, so it overrides front matter.
3. **Classify images.** Each image source is checked in Python:
   - `data:` URIs are kept.
   - Any URL scheme (`http(s)://`, `file://`, …) means the image is skipped as **remote** and never fetched.
   - A local path is resolved relative to the Markdown file and embedded only if it resolves inside `DATA_DIR` and exists. Otherwise it is skipped.
4. **Convert** with Pandoc (list arguments, no shell, 60 s timeout):
   ```
   pandoc <file> -f gfm+yaml_metadata_block+footnotes -t epub3 -o <tmp>/<safe-title>.epub
          --metadata-file <defaults.json> [--metadata author=<a>] --metadata title=<t>
          --resource-path <dir of file> --css assets/kindle.css
          --lua-filter assets/drop_images.lua --syntax-highlighting monochrome [--toc]
   ```
   The skipped images are passed to `drop_images.lua` (as JSON in an environment variable). The filter replaces each one with its alt text. The result lists every skipped image and the reason.
5. Check that the EPUB was created and is ≤ `MAX_ATTACHMENT_MB`. Send it (§8).

### 7.3 Tool: `send_pdf`

Emails a PDF unchanged.

| Argument | Type | Required | Notes |
|---|---|---|---|
| `path` | string | yes | `.pdf` file under the mount |
| `filename` | string | no | Attachment name; defaults to the source file's name |

**Validation:** the file starts with the `%PDF-` magic bytes and is ≤ `MAX_ATTACHMENT_MB`. The subject is never `Convert`, so Amazon keeps the original layout.

### 7.4 Tool: `check_config`

| Argument | Type | Required | Notes |
|---|---|---|---|
| `test_smtp` | boolean | no, default `false` | Connect and log in to SMTP without sending anything |

Reports:
- which required variables are set (values hidden)
- the Pandoc version
- the `DATA_DIR` / `HOST_DATA_DIR` mapping and whether `DATA_DIR` is readable
- the SMTP login result, if `test_smtp` is set

### 7.5 Results and errors

On success, a tool returns a short text summary:

```
Sent "My Notes.epub" (184 KB) to n***_1234@kindle.com.
Amazon will email a delivery confirmation to you@gmail.com; this usually takes 1–5 minutes.
Warnings: 1 remote image skipped (https://example.com/x.png).
```

On failure, a tool returns an MCP tool error (`isError: true`) with a message that says what went wrong and how to fix it. Examples:
- `Missing configuration: SMTP_PASSWORD. Add it to your env file.`
- `Gmail rejected the login (535). Use a Google App Password, not your account password.`
- `/Users/you/Desktop/a.md is outside the mounted folder /Users/you/Documents.`
- `File is 63 MB; Send to Kindle limit is 50 MB.`
- `Pandoc failed: <first lines of stderr>`

## 8. Email construction

- `EmailMessage` with `From: SENDER_EMAIL` and `To: KINDLE_EMAIL`. The recipient is always `KINDLE_EMAIL`; no tool accepts a recipient argument.
- Subject: the document title (the resolved title for Markdown, the attachment filename stem for PDFs).
- Body: a one-line plain-text note (Amazon ignores it).
- One attachment: `application/epub+zip` or `application/pdf`. The filename is made safe: path separators and control characters are removed, it is limited to 100 characters, it gets the right extension, and non-ASCII names use RFC 2231 encoding (handled by `email`).
- Connection: `smtplib.SMTP` + `starttls(context=ssl.create_default_context())`, or `SMTP_SSL`. Timeout is 30 s. No retries in v1.
- SMTP exceptions are mapped to clear messages (authentication, connection or timeout, recipient refused, message too large).

## 9. EPUB output requirements

- EPUB 3 with a navigation document plus an NCX (Pandoc default).
- Metadata: title, author, language, date (time of conversion), and a UUID identifier.
- **No cover image.** The Kindle shows its generic placeholder.
- Bundled `kindle.css`:
  - modest margins
  - no absolute font sizes on body text
  - `pre`/`code` in monospace, wrapping long lines
  - simple bordered tables
  - `img { max-width: 100%; height: auto; }`
- Syntax highlighting uses Pandoc's `monochrome` style, which reads well in greyscale.

## 10. Docker image

```dockerfile
FROM python:3.12-slim
ARG PANDOC_VERSION=<pinned>
ARG TARGETARCH
# Install the pinned upstream pandoc .deb for ${TARGETARCH} (amd64 | arm64)
RUN ... && rm -rf /var/lib/apt/lists/*
RUN useradd -r -u 10001 app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ /app/
USER app
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "sendtokindle"]
```

- Runs as a non-root user. The data mount is read-only, and nothing is written outside `/tmp`.
- Built locally with `docker build -t sendtokindle .`. Works on `linux/amd64` and `linux/arm64` (Apple Silicon). There is no registry publishing in v1.

### 10.1 Client configuration

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "sendtokindle": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
               "--env-file", "/Users/you/.config/sendtokindle/env",
               "-v", "/Users/you/Documents:/data:ro",
               "-e", "HOST_DATA_DIR=/Users/you/Documents",
               "sendtokindle:latest"]
    }
  }
}
```

**Claude Code:**
```bash
claude mcp add sendtokindle -- docker run -i --rm \
  --env-file "$HOME/.config/sendtokindle/env" \
  -v "$HOME/Documents:/data:ro" -e "HOST_DATA_DIR=$HOME/Documents" \
  sendtokindle:latest
```

The README will include a one-time setup checklist:
1. Create a Google App Password.
2. Add the Gmail address to Amazon's approved sender list.
3. Find the Kindle email address.
4. Write the env file.
5. Build the image.
6. Add the server to the client.
7. Run `check_config(test_smtp=true)`.

## 11. Security

- Paths are confined to `DATA_DIR` (§7.1). Image references are confined the same way (§7.2).
- Pandoc runs with list arguments, no shell, and a timeout. Its input is a file path, never text spliced into a command. Metadata values are passed as separate arguments.
- Size limits: Markdown ≤ 5 MB, attachments ≤ `MAX_ATTACHMENT_MB`.
- Fixed recipient: the server can only ever email `KINDLE_EMAIL`, so it can't be used to send mail elsewhere.
- No secrets in logs or results. The env file stays outside the repo, and `.gitignore` / `.dockerignore` exclude `*.env` and `env`.
- The container needs outbound network access only to the SMTP host.

## 12. Testing and acceptance

**Unit tests (`unittest`):**
- config validation
- host↔container path mapping and confinement, including symlinks and `..`
- title and author resolution
- filename sanitisation
- MIME construction (attachment type, filename encoding)
- SMTP error mapping

**Integration tests:** run inside the image so the real Pandoc is used. They convert fixture Markdown files covering headings, tables, code, footnotes, local images, unicode, front matter, and remote images, then check the EPUB structure:
- `mimetype` is the first entry and stored uncompressed
- `META-INF/container.xml` exists
- the OPF contains the expected metadata
- local images are embedded

SMTP is tested with a `unittest.mock` test double for `smtplib.SMTP` / `SMTP_SSL`. The standard library has had no SMTP server since `smtpd` was removed in Python 3.12. Tests never send real email.

**Acceptance criteria (v1):**
1. Claude Desktop and Claude Code can both list and call all three tools using the §10.1 configurations.
2. A Markdown file with headings, a table, a code block, a footnote, and a local image arrives on a Kindle with all of them rendered.
3. A 20 MB PDF arrives unchanged.
4. Missing or invalid credentials, and paths outside the mount, produce clear errors in Claude, not crashes.
5. The image builds and runs on both an Apple Silicon Mac and amd64.

## 13. Future features (out of scope for v1)

The v1 design should not block these:

| Feature | Notes / design hooks |
|---|---|
| **Preview tool** `convert_markdown` | Convert without sending and write the EPUB to a writable output mount (e.g. `/out`). `convert.py` returns a path, so this is a thin wrapper. |
| **Book mode** | Combine several `.md` files, or a folder in filename order, into one EPUB with one chapter per file. Pandoc accepts multiple inputs, so `path` would become `path \| paths[]`. |
| **Fetch remote images** | Optional download of `http(s)` images with size and time limits. Needs general outbound network access. |
| **PDF "Convert"** | A `convert` flag on `send_pdf` that sets the subject to `Convert` so Amazon makes the PDF reflowable. |
| Cover images | User-supplied image, or one generated from the title. |
| Inline content input | Pass Markdown as a string so no mount is needed. |
| Other input formats | HTML, DOCX, TXT (Amazon accepts these directly). |
| Registry publishing | GitHub Actions multi-arch build pushed to GHCR. |
| HTTP transport | Run as a long-lived server instead of one container per session. |

## 14. Decisions log

| Topic | Decision |
|---|---|
| Markdown conversion | Pandoc binary in the image (pinned upstream release) |
| MCP layer | Official `mcp` Python SDK, stdio |
| File input | Mounted paths only, one host folder (`HOST_DATA_DIR` → `DATA_DIR`), with host-path translation |
| Email subject | Document title (Markdown) / filename stem (PDF) |
| Email provider | Gmail defaults (App Password), overridable |
| Local images | Embedded, confined to the mount |
| Remote images | Not fetched in v1 |
| Cover | None |
| Distribution | Local `docker build` only |
| v1 extras | None. Preview, book mode, remote images, and PDF Convert are future features |
