import unittest
from unittest.mock import call, patch

from cbc_scraper.cli import menu


class MenuTests(unittest.TestCase):
    def test_choices_dispatch_without_changing_order(self):
        with patch(
            "rich.prompt.Prompt.ask", side_effect=["1", "2", "3", "4", "5", "0"]
        ), patch("cbc_scraper.cli.main") as run_command, patch(
            "cbc_scraper.cli.Console"
        ), patch(
            "cbc_scraper.cli.print_banner"
        ):
            self.assertEqual(menu(), 0)
        self.assertEqual(
            run_command.call_args_list,
            [
                call(["submissions"]),
                call(["history"]),
                call(["leaderboard"]),
                call(["offline"]),
                call(["setup", "--template"]),
            ],
        )
