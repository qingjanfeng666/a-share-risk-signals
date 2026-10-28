"""A trend begins with the first fresh result and fills later gaps only."""

import unittest
from datetime import date, timedelta

from backend.services.daily_plan import dates_to_score


class DailyRefreshPlanTests(unittest.TestCase):
    def setUp(self):
        self.prices = [{"日期": f"2026-10-{day:02d}"} for day in range(1, 32)]

    def test_first_refresh_only_scores_latest_day(self):
        self.assertEqual(dates_to_score(self.prices, None, {}), [(30, "2026-10-31")])

    def test_missing_days_are_filled_but_ready_days_are_not_repeated(self):
        targets = dates_to_score(self.prices, "2026-10-27", {
            "2026-10-27": "ready", "2026-10-28": "missing", "2026-10-29": "ready",
        })
        self.assertEqual([day for _, day in targets], ["2026-10-28", "2026-10-30", "2026-10-31"])

    def test_old_dates_are_outside_the_rolling_window(self):
        prices = [{"日期": (date(2026, 8, 1) + timedelta(days=index)).isoformat()} for index in range(60)]
        targets = dates_to_score(prices, "2026-08-01", {})
        self.assertEqual(targets[0], (30, prices[30]["日期"]))
        self.assertEqual(targets[-1], (59, prices[59]["日期"]))
        self.assertEqual(len(targets), 30)


if __name__ == "__main__":
    unittest.main()
