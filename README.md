# sendtokindle

An MCP server, run as a Docker container, that lets Claude Code and Claude Desktop send documents to your Kindle by email:

- `send_markdown` converts a Markdown file to EPUB (with Pandoc) and sends it.
- `send_pdf` sends a PDF unchanged.
- `check_config` reports what is configured and can test the SMTP login.

See [SPEC.md](SPEC.md) for the full specification and [docs/](docs/README.md) for UML component and activity diagrams.

## Setup

1. **Create a Google App Password.** This needs 2-Step Verification on your Google account. Go to <https://myaccount.google.com/apppasswords>.
2. **Approve your Gmail address with Amazon.** Go to Amazon → *Manage Your Content and Devices* → *Preferences* → *Personal Document Settings* → *Approved Personal Document E-mail List*.
3. **Find your Kindle email address** on the same page (`name_XXXX@kindle.com`).
4. **Write an env file** outside this repo, e.g. `~/.config/sendtokindle/env`, and restrict its permissions with `chmod 600`:
   ```
   KINDLE_EMAIL=name_1234@kindle.com
   SMTP_USERNAME=you@gmail.com
   SMTP_PASSWORD=abcd efgh ijkl mnop
   ```
   Optional settings and their defaults are listed in SPEC §6. They include `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SENDER_EMAIL`, `DEFAULT_AUTHOR`, `DEFAULT_LANGUAGE` and `MAX_ATTACHMENT_MB`.
5. **Build the image:**
   ```bash
   docker build -t sendtokindle .
   ```
6. **Add the server to your client.** The folder you mount is the only place the server can read files from. Mount it read-only and pass the same path as `HOST_DATA_DIR`, so the server can accept the host paths Claude sees.

   **Claude Code:**
   ```bash
   claude mcp add sendtokindle -- docker run -i --rm \
     --env-file "$HOME/.config/sendtokindle/env" \
     -v "$HOME/Documents:/data:ro" -e "HOST_DATA_DIR=$HOME/Documents" \
     sendtokindle:latest
   ```

   **Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`). Use absolute paths, since `~` and `$HOME` are not expanded here:
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
7. **Check it works.** Ask Claude to run `check_config` with `test_smtp` set to true.

## Development

```bash
# Run all tests inside the image (uses the real Pandoc)
docker build -t sendtokindle . && \
  docker run --rm -v "$PWD/tests:/app/tests:ro" -w /app --entrypoint python \
  sendtokindle -m unittest discover -s tests

# Unit tests locally (the Pandoc tests are skipped without Pandoc; the server tests need `pip install -r requirements.txt`)
PYTHONPATH=src:tests python -m unittest discover -s tests
```

The tests never send real email.
