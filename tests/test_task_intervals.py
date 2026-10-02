import unittest
from cbc_scraper.stats import submissions


class TaskIntervalTests(unittest.TestCase):
    def test_baseline_and_time_before_single_submission(self):
        rows = [
            {"task": "task0", "at": "2026-01-01T00:00:00Z"},
            {"task": "task0", "at": "2026-01-01T00:03:07Z"},
            {"task": "task1", "at": "2026-01-01T01:05:10Z"},
            {"task": "task2", "at": "2026-01-01T03:10:20Z"},
        ]
        stats = submissions(list(reversed(rows)))
        self.assertEqual(stats["task0"]["task_interval"], "0h 03m 07s")
        self.assertEqual(stats["task1"]["task_interval"], "1h 02m 03s")
        self.assertEqual(stats["task2"]["task_interval"], "2h 05m 10s")
        self.assertEqual(stats["task2"]["since_task0"], "3h 10m 20s")
        self.assertEqual(
            sum(task_stats["task_interval_seconds"] for task_stats in stats.values()),
            stats["task2"]["since_task0_seconds"],
        )

    def test_missing_and_reversed_boundaries(self):
        stats = submissions(
            [
                {"task": "task0", "at": "2026-01-01T02:00:00Z"},
                {"task": "task1", "at": "2026-01-01T01:00:00Z"},
                {"task": "task3", "at": "2026-01-01T04:00:00Z"},
            ]
        )
        self.assertEqual(stats["task1"]["task_interval"], "N/A")
        self.assertEqual(stats["task1"]["since_task0"], "N/A")
        self.assertEqual(stats["task3"]["task_interval"], "N/A")
        self.assertEqual(stats["task3"]["since_task0"], "2h 00m 00s")

    def test_natural_task_order_and_absent_baseline(self):
        stats = submissions(
            [
                {"task": "task10", "at": "2026-01-01T02:00:00Z"},
                {"task": "task9", "at": "2026-01-01T01:00:00Z"},
            ]
        )
        self.assertEqual(list(stats), ["task9", "task10"])
        self.assertEqual(stats["task10"]["task_interval"], "1h 00m 00s")
        self.assertEqual(stats["task10"]["since_task0"], "N/A")
