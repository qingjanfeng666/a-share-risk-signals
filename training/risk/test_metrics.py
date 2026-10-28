"""Check metrics for tied scores and a rare positive class."""

import unittest

import numpy as np
import torch

from .train_risk import MODEL_CLASSES, average_precision, roc_auc, threshold_metrics


class RiskMetricTests(unittest.TestCase):
    def test_tied_scores_have_base_rate_average_precision(self):
        labels = np.array([1, 0, 0, 0], dtype=np.int64)
        scores = np.array([0.2, 0.2, 0.2, 0.2])
        self.assertAlmostEqual(average_precision(labels, scores), 0.25)
        self.assertAlmostEqual(roc_auc(labels, scores), 0.5)

    def test_threshold_counts_high_risk_as_positive(self):
        labels = np.array([1, 0, 1, 0], dtype=np.int64)
        scores = np.array([0.8, 0.7, 0.3, 0.1])
        result = threshold_metrics(labels, scores, 0.5)
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (1, 1, 1))

    def test_three_models_have_distinct_inputs(self):
        price = torch.zeros(2, 20, 5)
        news = torch.zeros(2, 772)
        for mode, model_class in MODEL_CLASSES.items():
            model = model_class().eval()
            self.assertEqual(tuple(model(price, news).shape), (2,), mode)
            self.assertEqual(hasattr(model, "price_encoder"), mode != "text")
            self.assertEqual(hasattr(model, "text_encoder"), mode != "price")


if __name__ == "__main__":
    unittest.main()
