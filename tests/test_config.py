import unittest

from helpers import ENV, make_config
from sendtokindle.config import load_config, mask_email


class LoadConfigTest(unittest.TestCase):
    def test_defaults(self) -> None:
        config = make_config()
        self.assertEqual(config.problems, ())
        self.assertEqual(
            (config.smtp_host, config.smtp_port, config.smtp_security),
            ("smtp.gmail.com", 587, "starttls"),
        )
        self.assertEqual(config.sender_email, "me@gmail.com")
        self.assertEqual(config.max_attachment_mb, 50)

    def test_missing_required(self) -> None:
        problems = load_config({}).problems
        for name in ENV:
            self.assertTrue(any(name in problem for problem in problems), name)

    def test_invalid_values(self) -> None:
        config = make_config(
            SMTP_PORT="abc", SMTP_SECURITY="none", MAX_ATTACHMENT_MB="0", LOG_LEVEL="loud"
        )
        self.assertEqual(len(config.problems), 4)
        self.assertEqual(config.smtp_port, 587)

    def test_host_data_dir_trailing_slash(self) -> None:
        self.assertEqual(
            make_config(HOST_DATA_DIR="/Users/me/Documents/").host_data_dir, "/Users/me/Documents"
        )

    def test_problems_never_include_password(self) -> None:
        config = make_config(SMTP_PORT="x")
        self.assertNotIn("app-password", " ".join(config.problems))


class MaskEmailTest(unittest.TestCase):
    def test_mask(self) -> None:
        self.assertEqual(mask_email("reader_1234@kindle.com"), "r***1234@kindle.com")
        self.assertEqual(mask_email("abc@kindle.com"), "a***@kindle.com")


if __name__ == "__main__":
    unittest.main()
