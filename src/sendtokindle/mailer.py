"""Email construction and SMTP delivery (SPEC §8)."""

import smtplib
import ssl
from collections.abc import Iterator
from contextlib import contextmanager
from email.message import EmailMessage
from pathlib import Path

from .config import Config, KindleError, mask_email

SMTP_TIMEOUT_SECONDS = 30
LOGIN_HINT = "For Gmail, use a Google App Password, not your account password."
MIME_TYPES = {".epub": ("application", "epub+zip"), ".pdf": ("application", "pdf")}


def build_message(config: Config, subject: str, attachment: Path, filename: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = config.sender_email
    message["To"] = config.kindle_email
    message["Subject"] = subject
    message.set_content("Sent by sendtokindle.\n")
    maintype, subtype = MIME_TYPES[Path(filename).suffix.lower()]
    message.add_attachment(
        attachment.read_bytes(), maintype=maintype, subtype=subtype, filename=filename
    )
    return message


@contextmanager
def _session(config: Config) -> Iterator[smtplib.SMTP]:
    """A logged-in SMTP connection; SMTP failures are mapped to `KindleError`."""
    host = f"{config.smtp_host}:{config.smtp_port}"
    try:
        context = ssl.create_default_context()
        if config.smtp_security == "ssl":
            smtp = smtplib.SMTP_SSL(
                config.smtp_host, config.smtp_port, timeout=SMTP_TIMEOUT_SECONDS, context=context
            )
        else:
            smtp = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=SMTP_TIMEOUT_SECONDS)
        with smtp:
            if config.smtp_security == "starttls":
                smtp.starttls(context=context)
            try:
                smtp.login(config.smtp_username, config.smtp_password)
            except smtplib.SMTPServerDisconnected:  # Gmail may hang up instead of replying 535
                raise KindleError(
                    f"{host} closed the connection during login. {LOGIN_HINT}"
                ) from None
            yield smtp
    except smtplib.SMTPAuthenticationError as error:
        raise KindleError(f"{host} rejected the login ({error.smtp_code}). {LOGIN_HINT}") from None
    except smtplib.SMTPRecipientsRefused:
        raise KindleError(
            f"{host} refused the Kindle address {mask_email(config.kindle_email)}."
        ) from None
    except smtplib.SMTPSenderRefused as error:
        raise KindleError(
            f"{host} refused the sender address {config.sender_email} ({error.smtp_code})."
        ) from None
    except smtplib.SMTPDataError as error:
        reason = (
            "the message is too large" if error.smtp_code == 552 else "it rejected the message"
        )
        raise KindleError(
            f"{host} did not accept the email: {reason} ({error.smtp_code})."
        ) from None
    except smtplib.SMTPException as error:
        raise KindleError(f"SMTP error from {host}: {error}") from None
    except OSError as error:  # DNS, refused connection, TLS failure, timeout
        raise KindleError(
            f"Could not connect to {host}: {error.strerror or type(error).__name__}."
        ) from None


def send(config: Config, subject: str, attachment: Path, filename: str) -> None:
    message = build_message(config, subject, attachment, filename)
    with _session(config) as smtp:
        smtp.send_message(message)


def check_login(config: Config) -> None:
    with _session(config):
        pass
