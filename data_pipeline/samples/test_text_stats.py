"""Sentiment score is positive probability minus negative probability."""

import unittest

from .text_stats import aggregate_sentiment, extra_text_features


class DailyTextStatsTests(unittest.TestCase):
    def test_counts_ratio_and_sentiment(self):
        stats = aggregate_sentiment([[0.8, 0.1, 0.1], [0.1, 0.1, 0.8]])
        self.assertEqual((stats["news_count"], stats["positive_count"], stats["negative_count"]), (2, 1, 1))
        self.assertEqual(stats["negative_ratio"], 0.5)
        self.assertAlmostEqual(stats["avg_sentiment"], 0.0, places=6)
        self.assertAlmostEqual(stats["min_sentiment"], -0.7, places=6)
        self.assertEqual(extra_text_features(stats).shape, (5,))

    def test_no_text_is_explicitly_zero(self):
        stats = aggregate_sentiment([])
        self.assertEqual(stats["news_count"], 0)
        self.assertTrue((extra_text_features(stats) == 0).all())


if __name__ == "__main__":
    unittest.main()
