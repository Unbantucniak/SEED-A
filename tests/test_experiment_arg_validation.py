import unittest
from argparse import Namespace
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXPERIMENTS_DIR = os.path.join(PROJECT_ROOT, "experiments")
if EXPERIMENTS_DIR not in sys.path:
    sys.path.insert(0, EXPERIMENTS_DIR)

from run_g1_experiment import _validate_args as validate_g1_args
from run_g2_analysis import _validate_args as validate_g2_args


class TestExperimentArgValidation(unittest.TestCase):
    def test_g1_rounds_must_be_positive(self):
        with self.assertRaises(ValueError):
            validate_g1_args(Namespace(rounds=0, target_count=120))

    def test_g1_target_count_must_be_positive(self):
        with self.assertRaises(ValueError):
            validate_g1_args(Namespace(rounds=1, target_count=0))

    def test_g2_rounds_must_be_positive(self):
        with self.assertRaises(ValueError):
            validate_g2_args(Namespace(rounds=0, target_count=120))

    def test_g2_target_count_must_be_positive(self):
        with self.assertRaises(ValueError):
            validate_g2_args(Namespace(rounds=1, target_count=0))


if __name__ == "__main__":
    unittest.main()
