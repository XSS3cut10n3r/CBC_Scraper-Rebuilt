import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from rich.console import Console

from cbc_scraper.cli import load_graph_data, parser
from cbc_scraper.graphs import (
    bar,
    graph_menu,
    overall_graph,
    personal_graph,
    school_entries,
    school_graph,
    select_school,
)


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.raw = {
            "Participants": [["Alpha", 10], ["Beta", 30], ["Empty", 0]],
            "Task 0": [["Alpha", 2, 2, 100], ["Beta", 10, 10, 100]],
            "Task 1": [["Alpha", 0, 0, None], ["Beta", 1, 1, 200]],
            "Task 2": [["Beta", 1, 1, 300]],
        }
        self.stream = io.StringIO()
        self.console = Console(file=self.stream, width=90, color_system=None)

    def test_percentage_denominators_and_missing_rows(self):
        registered, rows = school_entries(self.raw, 2026, "Alpha")
        self.assertEqual(registered, 10)
        self.assertEqual(rows[0], ("Task 0", 2, 20, 30))
        self.assertEqual(rows[1][1:3], (0, 0))
        self.assertEqual(rows[2][1:3], (None, None))
        self.assertIsNone(school_entries(self.raw, 2026, "Empty")[1][0][2])

    def test_bar_zero_tiny_missing_and_full(self):
        self.assertEqual(bar(0, 100, 20), " " * 20)
        self.assertEqual(bar(1, 100, 20), "." + " " * 19)
        self.assertEqual(bar(None, 100, 20), "?" + " " * 19)
        self.assertEqual(bar(100, 100, 20), "#" * 20)
        self.assertEqual(bar(120, 100, 20), "#" * 20)

    def test_school_and_overall_render_correct_counts(self):
        overall_graph(self.raw, 2026, self.console)
        school_graph(self.raw, 2026, "Alpha", self.console)
        output = self.stream.getvalue()
        self.assertIn("40 participants", output)
        self.assertIn("30.00%", output)
        self.assertIn("20.00%", output)
        self.assertIn("2/10 solvers", output)
        self.assertIn("0/10 solvers", output)
        self.assertIn("N/A", output)

    def test_personal_graph_uses_existing_intervals(self):
        personal_graph(
            [
                {"task": "task0", "at": "2026-01-01T00:00:00Z"},
                {"task": "task1", "at": "2026-01-01T01:02:03Z"},
                {"task": "task2", "at": "2026-01-01T03:04:05Z"},
            ],
            self.console,
        )
        output = self.stream.getvalue()
        self.assertIn("1h 02m 03s", output)
        self.assertIn("2h 02m 02s", output)
        self.assertIn("3h 04m 05s", output)

    def test_search_and_choice(self):
        with patch("cbc_scraper.graphs.Prompt.ask", side_effect=["", "2"]):
            self.assertEqual(select_school(self.raw, self.console), "Beta")

    def test_graph_session_reuses_fetched_boards(self):
        load_data = Mock(return_value=(self.raw, "Saved data"))
        with patch(
            "cbc_scraper.graphs.Prompt.ask",
            side_effect=["1", "", "3", "Alpha", "", "0"],
        ):
            self.assertEqual(graph_menu(load_data, 2026, self.console), 0)
        load_data.assert_called_once_with("leaderboard")

    def test_logarithmic_scale_keeps_zero_and_expands_short_durations(self):
        self.assertEqual(bar(0, 10000, 20, "logarithmic"), " " * 20)
        self.assertEqual(bar(10000, 10000, 20, "logarithmic"), "#" * 20)
        self.assertGreater(
            bar(10, 10000, 20, "logarithmic").count("#"), bar(10, 10000, 20).count("#")
        )

    def test_personal_scale_toggle(self):
        rows = [
            {"task": "task0", "at": "2026-01-01T00:00:00Z"},
            {"task": "task1", "at": "2026-01-01T01:02:03Z"},
        ]
        with patch("cbc_scraper.graphs.Prompt.ask", side_effect=["2", "s", "", "0"]):
            graph_menu(Mock(return_value=(rows, "Saved data")), 2026, self.console)
        output = self.stream.getvalue()
        self.assertIn("Scale: linear", output)
        self.assertIn("Scale: logarithmic", output)
        self.assertEqual(output.count("1h 02m 03s"), 8)

    def test_school_search_paginates_and_can_cancel(self):
        raw = {"Participants": [[f"School {index:02}", 1] for index in range(25)]}
        with patch("cbc_scraper.graphs.Prompt.ask", side_effect=["School", "n", "25"]):
            self.assertEqual(select_school(raw, self.console), "School 24")
        with patch("cbc_scraper.graphs.Prompt.ask", return_value="q"):
            self.assertIsNone(select_school(raw, self.console))

    def test_historical_solver_column(self):
        raw = {"Participants": [["Alpha", 10]], "Task 1": [["Alpha", 10, 3, 100]]}
        self.assertEqual(
            school_entries(raw, 2020, "Alpha")[1][0], ("Task 1", 3, 30, 30)
        )

    def test_empty_graphs_and_zero_denominator(self):
        overall_graph({"Participants": [], "Task 0": []}, 2026, self.console)
        personal_graph([], self.console)
        self.assertIn("N/A", self.stream.getvalue())
        self.assertIn("No submissions yet.", self.stream.getvalue())

    def test_offline_loader_never_connects(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "leaderboard_stats_2026.json").write_text(
                json.dumps({"raw_data": self.raw})
            )
            args = parser().parse_args(["graphs", "--display", "--data-dir", directory])
            with patch("cbc_scraper.cli.Client") as client:
                raw, source = load_graph_data(args, "leaderboard", 2026)
            client.assert_not_called()
            self.assertEqual(raw, self.raw)
            self.assertIn("Saved data", source)
