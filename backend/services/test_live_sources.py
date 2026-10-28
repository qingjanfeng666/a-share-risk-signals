import unittest

import pandas as pd

from backend.services.live_sources import fetch_prices


class FetchPricesTests(unittest.TestCase):
    def test_uses_tencent_directly_and_normalizes_columns(self):
        class FakeAK:
            def stock_zh_a_hist(self, **kwargs):
                raise AssertionError("Eastmoney must not be requested")

            def stock_zh_a_hist_tx(self, **kwargs):
                self.tencent_kwargs = kwargs
                return pd.DataFrame([{
                    "date": "2026-10-16", "open": 1, "close": 2,
                    "high": 3, "low": 1, "volume": 100,
                }])

        ak = FakeAK()
        frame, source = fetch_prices(ak, "600036", "20260622", "20261016")

        self.assertEqual(source, "Tencent qfq via AKShare")
        self.assertEqual(frame.loc[0, "收盘"], 2)
        self.assertEqual(ak.tencent_kwargs, {
            "symbol": "600036", "start_date": "20260622",
            "end_date": "20261016", "adjust": "qfq", "timeout": 15,
        })


if __name__ == "__main__":
    unittest.main()
