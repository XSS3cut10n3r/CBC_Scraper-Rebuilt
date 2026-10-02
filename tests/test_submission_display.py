import csv
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from rich.console import Console
from cbc_scraper.cli import render, export
from cbc_scraper.stats import submissions, format_duration


class SubmissionDisplayTests(unittest.TestCase):
    def test_seconds_are_not_reconstructed_from_rounded_hours(self):
        stats = submissions(
            [
                {"task": "task0", "at": "2026-01-01T00:00:00Z"},
                {"task": "task0", "at": "2026-01-02T07:52:13Z"},
            ]
        )
        self.assertEqual(stats["task0"]["attempt_span"], "31h 52m 13s")
        self.assertEqual(stats["task0"]["attempt_span_seconds"], 114733)
        self.assertEqual(format_duration(59.9), "0h 00m 59s")
        self.assertEqual(format_duration(60), "0h 01m 00s")
        self.assertEqual(format_duration(None), "N/A")

    def test_missing_time_is_not_zero(self):
        stats = submissions(
            [{"task": "missing"}, {"task": "single", "at": "2026-01-01T00:00:00Z"}]
        )
        self.assertEqual(stats["missing"]["attempt_span"], "N/A")
        self.assertEqual(stats["single"]["attempt_span"], "0h 00m 00s")

    def test_hide_unavailable_status_and_keep_exports_aligned(self):
        report = {
            "kind": "submissions",
            "stats": submissions([{"task": "task0", "at": "2026-01-01T00:00:00Z"}]),
        }
        stream = io.StringIO()
        with patch(
            "cbc_scraper.cli.Console", return_value=Console(file=stream, width=120)
        ):
            render(report, SimpleNamespace(no_banner=True))
        self.assertNotIn("Unknown", stream.getvalue())
        self.assertNotIn("Status", stream.getvalue())
        self.assertIn("0h 00m 00s", stream.getvalue())
        rows = list(csv.DictReader(io.StringIO(export(report, "csv"))))
        self.assertEqual(rows[0]["attempt_span"], "0h 00m 00s")
        self.assertEqual(rows[0]["status"], "Unknown")

    def test_explicit_success_remains_visible(self):
        report = {
            "kind": "submissions",
            "stats": submissions([{"task": "task0", "success": True}]),
        }
        stream = io.StringIO()
        with patch(
            "cbc_scraper.cli.Console", return_value=Console(file=stream, width=120)
        ):
            render(report, SimpleNamespace(no_banner=True))
        self.assertIn("Passed", stream.getvalue())
