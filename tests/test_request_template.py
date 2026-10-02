import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cbc_scraper.auth import REQUEST_TEMPLATE, find_request
from cbc_scraper.client import Client, ScraperError, request_headers
from cbc_scraper.cli import main


class RequestTemplateTests(unittest.TestCase):
    def test_comments_and_cookie_header(self):
        text = REQUEST_TEMPLATE.replace('PASTE_COOKIE_VALUE_HERE', 'cbweb_session=fake; remember_token=example')
        self.assertEqual(request_headers(text)['cookie'], 'cbweb_session=fake; remember_token=example')

    def test_comments_and_curl(self):
        self.assertEqual(request_headers('# browser\'s request\n# ignored\ncurl https://nsa-codebreaker.org -b "cbweb_session=fake"')['cookie'], 'cbweb_session=fake')

    def test_placeholder_stops_before_request(self):
        with self.assertRaisesRegex(ScraperError, 'not filled in'):
            request_headers(REQUEST_TEMPLATE)

    def test_fresh_setup_discovery_and_no_overwrite(self):
        previous = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
                os.chdir(directory)
                self.assertEqual(main(['setup', '--template']), 0)
                path = Path('edit_this_request.txt')
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(find_request(), path)
                with self.assertRaises(ScraperError): Client(find_request())
                path.write_text(REQUEST_TEMPLATE.replace('PASTE_COOKIE_VALUE_HERE', 'cbweb_session=fake; remember_token=example'))
                self.assertEqual(Client(find_request()).session.cookies.get('cbweb_session'), 'fake')
                before = path.read_text()
                self.assertEqual(main(['setup', '--template']), 0)
                self.assertEqual(path.read_text(), before)
        finally:
            os.chdir(previous)
