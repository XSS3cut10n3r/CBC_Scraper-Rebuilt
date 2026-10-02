import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cbc_scraper.auth import find_request
from cbc_scraper.client import ScraperError
from cbc_scraper.cli import main


class AuthTests(unittest.TestCase):
    def test_explicit_path_has_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "browser.txt"
            path.write_text("placeholder")
            with patch.dict(os.environ, {"CBC_COOKIE": "cookie=value"}):
                self.assertEqual(find_request(str(path)), path)

    def test_missing_explicit_does_not_use_other_credentials(self):
        with self.assertRaisesRegex(ScraperError, "setup"):
            find_request("/no-such-cbc-request-file")

    def test_setup_saves_private_request_and_discovers_it(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "browser.txt"
            source.write_text(
                "curl https://nsa-codebreaker.org -H 'Cookie: cbweb_session=fake'"
            )
            data = Path(directory) / "data"
            self.assertEqual(
                main(["setup", "--request-file", str(source), "--data-dir", str(data)]),
                0,
            )
            target = data / "request.txt"
            self.assertEqual(target.read_text(), source.read_text())
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            with patch.dict(os.environ, {}, clear=True), patch(
                "cbc_scraper.auth.Path.is_file",
                autospec=True,
                side_effect=lambda candidate: candidate == target,
            ):
                self.assertEqual(find_request(data_dir=data), target)

    def test_missing_login_has_actionable_instructions(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "cbc_scraper.auth.Path.is_file", return_value=False
        ):
            with self.assertRaisesRegex(ScraperError, "cbc-scraper setup"):
                find_request()

    def test_bare_command_opens_menu(self):
        with patch("sys.stdin.isatty", return_value=True), patch(
            "cbc_scraper.cli.menu", return_value=0
        ) as menu:
            self.assertEqual(main([]), 0)
            menu.assert_called_once()
