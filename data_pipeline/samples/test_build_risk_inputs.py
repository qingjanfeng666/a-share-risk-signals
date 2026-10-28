"""Check that risk inputs stop at the prediction day."""

import unittest

import numpy as np

from .build_risk_inputs import price_window, text_vector


class RiskInputTimingTests(unittest.TestCase):
    def test_future_price_does_not_change_window(self):
        rows = [
            {"日期": f"day-{day}", "收盘": str(100 + day), "开盘": str(100 + day),
             "最高": str(101 + day), "最低": str(99 + day), "成交量": "1000"}
            for day in range(21)
        ]
        before = price_window(rows, end=19)
        rows[20].update({"收盘": "10000", "开盘": "10000", "最高": "10000",
                         "最低": "10000", "成交量": "1000000"})
        after = price_window(rows, end=19)
        self.assertEqual(before.shape, (20, 5))
        np.testing.assert_array_equal(before, after)

    def test_day_without_announcements_has_zero_text_features(self):
        sample = {"stock": "300750", "date": "2025-01-01", "announcement_ids": "",
                  "announcement_count": "0"}
        np.testing.assert_array_equal(text_vector(sample, {}), np.zeros(772, dtype=np.float32))


if __name__ == "__main__":
    unittest.main()
