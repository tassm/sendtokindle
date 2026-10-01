import smtplib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import make_config
from sendtokindle import mailer
from sendtokindle.config import KindleError


class MailerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = Path(self.tmp.name) / "source.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 test")
        self.config = make_config()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_build_message(self) -> None:
        message = mailer.build_message(self.config, "Résumé", self.pdf, "Résumé.pdf")
        self.assertEqual(message["To"], "reader_1234@kindle.com")
        self.assertEqual(message["From"], "me@gmail.com")
        self.assertEqual(message["Subject"], "Résumé")
        [attachment] = list(message.iter_attachments())
        self.assertEqual(attachment.get_content_type(), "application/pdf")
        self.assertEqual(attachment.get_filename(), "Résumé.pdf")
        self.assertEqual(attachment.get_content(), b"%PDF-1.4 test")

    @mock.patch("smtplib.SMTP")
    def test_send_uses_starttls_and_login(self, smtp_class: mock.MagicMock) -> None:
        smtp = smtp_class.return_value
        mailer.send(self.config, "Doc", self.pdf, "doc.pdf")
        smtp_class.assert_called_once_with("smtp.gmail.com", 587, timeout=30)
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("me@gmail.com", "app-password")
        smtp.send_message.assert_called_once()

    @mock.patch("smtplib.SMTP_SSL")
    def test_ssl_mode(self, smtp_class: mock.MagicMock) -> None:
        mailer.check_login(make_config(SMTP_SECURITY="ssl", SMTP_PORT="465"))
        smtp_class.return_value.starttls.assert_not_called()
        smtp_class.return_value.login.assert_called_once()

    def test_error_mapping(self) -> None:
        cases = [
            (smtplib.SMTPAuthenticationError(535, b"bad"), "App Password"),
            (smtplib.SMTPRecipientsRefused({}), "refused the Kindle address r\\*\\*\\*1234"),
            (smtplib.SMTPDataError(552, b"big"), "too large"),
            (
                smtplib.SMTPServerDisconnected(),
                "closed the connection during login. .*App Password",
            ),
            (TimeoutError(), "Could not connect to smtp.gmail.com:587: TimeoutError"),
        ]
        for error, pattern in cases:
            with (
                self.subTest(error=type(error).__name__),
                mock.patch("smtplib.SMTP") as smtp_class,
            ):
                smtp_class.return_value.login.side_effect = error
                with self.assertRaisesRegex(KindleError, pattern) as raised:
                    mailer.check_login(self.config)
                self.assertNotIn("app-password", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
