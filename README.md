# sendtokindle

An MCP server, run as a Docker container, that lets Claude Code and Claude Desktop send documents to your Kindle by email:

- `send_markdown` converts a Markdown file to EPUB (with Pandoc) and sends it.
- `send_pdf` sends a PDF unchanged.
- `check_config` reports what is configured and can test the SMTP login.

See [SPEC.md](SPEC.md) for the full specification and [docs/](docs/README.md) for UML component and activity diagrams.

## Setup

1. **Create a Google App Password.** This needs 2-Step Verification on your Google account. Go to <https://myaccount.google.com/apppasswords>. To send from Proton Mail instead, see [Using Proton Mail with a custom domain](#using-proton-mail-with-a-custom-domain).
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
6. **Create a shared folder** for documents to send:
   ```bash
   mkdir -p ~/KindleSharedDocs
   ```
   This is the only folder the server can read. You, Claude Desktop and Claude Code put files here, with any images alongside them (e.g. `~/KindleSharedDocs/img/diagram.png`). Keep it outside iCloud-synced folders, and never put the env file in it. The server never deletes anything, so clear the folder out from time to time.
7. **Add the server to your client.** Mount the shared folder read-only and pass the same path as `HOST_DATA_DIR`, so the server can accept the host paths Claude sees.

   **Claude Code:**
   ```bash
   claude mcp add sendtokindle -- docker run -i --rm \
     --env-file "$HOME/.config/sendtokindle/env" \
     -v "$HOME/KindleSharedDocs:/data:ro" -e "HOST_DATA_DIR=$HOME/KindleSharedDocs" \
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
                  "-v", "/Users/you/KindleSharedDocs:/data:ro",
                  "-e", "HOST_DATA_DIR=/Users/you/KindleSharedDocs",
                  "sendtokindle:latest"]
       }
     }
   }
   ```
8. **Let Claude write into the shared folder.** The server only reads files, so Claude needs separate permission to create them:
   - **Claude Desktop:** turn on the Filesystem extension (*Settings* → *Extensions*) and add `/Users/you/KindleSharedDocs` as an allowed directory.
   - **Claude Code:** run `/add-dir ~/KindleSharedDocs` for a single session. To make it permanent, add the folder to `permissions.additionalDirectories` in `~/.claude/settings.json`:
     ```json
     { "permissions": { "additionalDirectories": ["~/KindleSharedDocs"] } }
     ```
9. **Check it works.** Ask Claude to run `check_config` with `test_smtp` set to true. Then try a request such as "write a summary of X to ~/KindleSharedDocs/x.md and send it to my Kindle".

### Using Proton Mail with a custom domain

Proton SMTP tokens let you send from an address on your own domain. They need a paid Proton plan and a verified custom domain, and they do not work for `@proton.me` or `@protonmail.com` addresses.

1. **Create an SMTP token.** In Proton Mail, go to *Settings* → *IMAP/SMTP* → *SMTP tokens*. Choose your custom-domain address and copy the token, which is shown only once.
2. **Approve that address with Amazon**, as in step 2 above.
3. **Use these settings in your env file** instead of the Gmail ones:
   ```
   KINDLE_EMAIL=name_1234@kindle.com
   SMTP_HOST=smtp.protonmail.ch
   SMTP_PORT=587
   SMTP_USERNAME=you@yourdomain.com
   SMTP_PASSWORD=<your SMTP token>
   ```
   Leave `SENDER_EMAIL` unset. It defaults to `SMTP_USERNAME`, and the token can only send as that address. If the login fails, ignore the App Password hint in the error and check the token and username.

Proton Mail Bridge is not supported. The container cannot reach it on the host's `127.0.0.1`, and the server rejects its self-signed certificate.

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
