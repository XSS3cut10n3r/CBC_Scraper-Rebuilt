import unittest
from unittest.mock import Mock
from cbc_scraper.client import Client, ScraperError, request_headers
from cbc_scraper.stats import leaderboard, submissions


class Tests(unittest.TestCase):
    def test_cookie_names_and_no_execution(self):
        headers = request_headers(
            "curl https://example.invalid -H 'Cookie: cbweb_session=abc; remember_token=def' -H 'Authorization: ignored'"
        )
        self.assertEqual(headers, {"cookie": "cbweb_session=abc; remember_token=def"})

    def test_earliest_and_missing(self):
        raw = {
            "Participants": [["A", 10], ["B", 20]],
            "Task 0": [["A", 2, 2, 200], ["B", 1, 1, 100], ["C", 1, 1, None]],
        }
        stats = leaderboard(raw, 2026)
        self.assertEqual(
            [school["school"] for school in stats["tasks"]["Task 0"]["fastest"]],
            ["B", "A"],
        )
        self.assertEqual(stats["tasks"]["Task 0"]["schools"][0]["solve_rate"], 20)

    def test_old_solver_column(self):
        self.assertEqual(
            leaderboard({"Task 1": [["A", 99, 3, 100]]}, 2020)["tasks"]["Task 1"][
                "solvers"
            ],
            3,
        )

    def test_unknown_not_success(self):
        result = submissions(
            [
                {
                    "task": "task8",
                    "at": "2026-01-01T00:00:00Z",
                    "response": "something new",
                },
                {"task": "task8", "at": "2026-01-01T02:00:00Z"},
            ]
        )
        self.assertEqual(result["task8"]["status"], "Unknown")
        self.assertEqual(result["task8"]["attempt_span_hours"], 2)

    def test_full_board(self):
        client = Client()
        client.json = Mock(return_value={"data": [["A", 1]]})
        self.assertEqual(client.board(1, 0), [["A", 1]])

    def test_paginated_board(self):
        client = Client()
        client.json = Mock(
            side_effect=[
                {"data": [["A", 1]], "recordsTotal": 2},
                {"data": [["B", 2]], "recordsTotal": 2},
            ]
        )
        self.assertEqual(len(client.board(1, 0)), 2)

    def test_incomplete_submissions(self):
        client = Client()
        client.json = Mock(
            return_value={"submissions": [], "total_count": 2, "next": None}
        )
        with self.assertRaises(ScraperError):
            client.submissions()

    def test_redirect_not_followed(self):
        client = Client()
        client.session.request = Mock(return_value=Mock(status_code=302))
        with self.assertRaises(ScraperError):
            client.fetch("/leaderboard")
        self.assertFalse(client.session.request.call_args.kwargs["allow_redirects"])


if __name__ == "__main__":
    unittest.main()
