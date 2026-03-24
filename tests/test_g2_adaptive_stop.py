import unittest

from experiments.run_g2_analysis import ci_half_width


class TestG2AdaptiveStop(unittest.TestCase):
    def test_ci_half_width_single_is_inf(self):
        self.assertEqual(ci_half_width([0.9]), float("inf"))

    def test_ci_half_width_zero_variance(self):
        self.assertEqual(ci_half_width([0.9, 0.9]), 0.0)


if __name__ == "__main__":
    unittest.main()
