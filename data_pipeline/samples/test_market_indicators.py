"""Check indicator formulas and absence of future-price leakage."""

import math
import statistics
import unittest

from .market_indicators import indicators_at, market_window


class MarketIndicatorTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"日期": f"day-{index}", "收盘": 100 + index, "开盘": 100 + index,
             "最高": 101 + index, "最低": 99 + index, "成交量": 1000 + 10 * index}
            for index in range(45)
        ]

    def test_explicit_risk_indicators(self):
        values = indicators_at(self.rows, 39)
        returns = [math.log((100 + index) / (99 + index)) for index in range(20, 40)]
        self.assertAlmostEqual(values[0], statistics.stdev(returns[-5:]), places=6)
        self.assertAlmostEqual(values[1], statistics.stdev(returns[-10:]), places=6)
        self.assertAlmostEqual(values[2], statistics.stdev(returns), places=6)
        self.assertAlmostEqual(values[3], 0.0)
        average = statistics.mean(1000 + 10 * index for index in range(19, 39))
        self.assertAlmostEqual(values[4], (1390 - average) / average, places=6)

    def test_market_window_ignores_future_rows(self):
        expected = market_window(self.rows, 39)
        self.rows[40]["收盘"] = 10000
        self.rows[40]["成交量"] = 100000
        self.assertEqual(expected.shape, (20, 10))
        self.assertTrue((expected == market_window(self.rows, 39)).all())
        with self.assertRaises(ValueError):
            market_window(self.rows, 38)

    def test_drawdown_uses_running_peak(self):
        rows = [dict(row) for row in self.rows]
        rows[35]["收盘"] = 160
        rows[39]["收盘"] = 120
        self.assertAlmostEqual(indicators_at(rows, 39)[3], 0.25)


if __name__ == "__main__":
    unittest.main()
