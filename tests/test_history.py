import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rich.console import Console
from cbc_scraper.cli import main
from cbc_scraper.history import browse, ordered, page_table, payload


class HistoryTests(unittest.TestCase):
    def test_order_and_page_cap(self):
        rows = [
            {
                "at": f"2026-01-01T00:{i//60:02}:{i%60:02}Z",
                "hexdata": "6869",
                "response": "ok",
            }
            for i in range(101)
        ]
        entries = ordered(list(reversed(rows)))
        self.assertEqual(entries, rows)
        self.assertEqual(len(page_table("task0", entries, 1).rows), 20)
        self.assertEqual(len(page_table("task0", entries, 6).rows), 1)

    def test_payload_and_literal_preview(self):
        self.assertEqual(payload({"hexdata": "68656c6c6f"}), "hello")
        self.assertEqual(payload({"hexdata": "not hex"}), "not hex")
        self.assertEqual(payload({"hexdata": "ff00"}), "ff00")
        stream = io.StringIO()
        Console(file=stream, width=120).print(
            page_table("task0", [{"response": "[red]" + "x" * 1000}], 1)
        )
        self.assertIn("[red]", stream.getvalue())
        self.assertIn("open entry", stream.getvalue())
        self.assertNotIn("x" * 1000, stream.getvalue())

    def test_task_selection_navigation_and_full_entry(self):
        stream = io.StringIO()
        rows = [
            {
                "task": "task0",
                "at": i + 1,
                "hexdata": "6869",
                "response": "response-" + str(i),
            }
            for i in range(21)
        ]
        args = SimpleNamespace(task=None, page=1)
        with patch("sys.stdin.isatty", return_value=True), patch(
            "cbc_scraper.history.Prompt.ask",
            side_effect=["0", "n", "21", "", "p", "t", "q"],
        ):
            browse(rows, args, Console(file=stream, width=120))
        self.assertIn("page 2/2", stream.getvalue())
        self.assertIn("Submission #21", stream.getvalue())
        self.assertIn("response-20", stream.getvalue())

    def test_actual_task_number_with_gaps(self):
        stream = io.StringIO()
        rows = [{"task": "task0", "at": 1}, {"task": "task8", "at": 2}]
        with patch("sys.stdin.isatty", return_value=True), patch(
            "cbc_scraper.history.Prompt.ask", side_effect=["8", "q"]
        ) as prompt:
            browse(
                rows,
                SimpleNamespace(task=None, page=1),
                Console(file=stream, width=120),
            )
        self.assertIn("task8 — 1 submissions", stream.getvalue())
        self.assertEqual(prompt.call_args_list[0].kwargs["choices"], ["0", "8", "q"])
        self.assertNotIn("Next page", stream.getvalue())
        self.assertNotIn("Previous page", stream.getvalue())
        self.assertNotIn("UTF-8", stream.getvalue())

    def test_offline_reads_all_caches_and_never_connects(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            for year in (2025, 2026):
                (directory / f"leaderboard_stats_{year}.json").write_text(
                    json.dumps({"raw_data": {"Participants": []}})
                )
            (directory / "submission_stats.json").write_text(
                json.dumps({"all_submissions": []})
            )
            stream = io.StringIO()
            with patch("cbc_scraper.cli.Client") as client, patch(
                "cbc_scraper.cli.Console", return_value=Console(file=stream)
            ):
                self.assertEqual(main(["offline", "--data-dir", folder]), 0)
            client.assert_not_called()
            self.assertIn("2025", stream.getvalue())
            self.assertIn("2026", stream.getvalue())
            self.assertIn("Saved submission statistics", stream.getvalue())

    def test_offline_with_only_submissions(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "submission_stats.json").write_text(
                json.dumps({"all_submissions": []})
            )
            with patch("cbc_scraper.cli.Client") as client, patch(
                "cbc_scraper.cli.Console"
            ):
                self.assertEqual(main(["offline", "--data-dir", folder]), 0)
            client.assert_not_called()
