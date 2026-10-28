"""Check announcement timing and chronological split boundaries."""

import unittest
from datetime import date, datetime

from data_pipeline.samples.build_daily_samples import assigned_day, split_for


class DailySampleTimingTests(unittest.TestCase):
    def test_announcement_availability(self):
        days = [date(2025, 3, 28), date(2025, 3, 31), date(2025, 4, 1)]
        self.assertEqual(assigned_day(datetime(2025, 3, 28, 14, 59), days), days[0])
        self.assertEqual(assigned_day(datetime(2025, 3, 28, 15), days), days[1])
        self.assertEqual(assigned_day(datetime(2025, 3, 28), days), days[1])
        self.assertEqual(assigned_day(datetime(2025, 3, 29, 12), days), days[1])

    def test_split_cutoffs(self):
        self.assertEqual(split_for(date(2024, 12, 31))[0], "train")
        self.assertEqual(split_for(date(2025, 1, 1))[0], "validation")
        self.assertEqual(split_for(date(2025, 6, 30))[0], "validation")
        self.assertEqual(split_for(date(2025, 7, 1))[0], "test")


if __name__ == "__main__":
    unittest.main()
