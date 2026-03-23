import os
import tempfile
import unittest

from experiments.path_resolver import resolve_dataset_path, resolve_output_dir


class TestExperimentPathResolution(unittest.TestCase):
    def setUp(self):
        self.script_dir = os.path.abspath(os.path.join(os.getcwd(), "experiments"))

    def test_default_dataset_is_script_relative(self):
        default_dataset = "./benchmarks/g1_full_120_tasks.json"
        path = resolve_dataset_path(default_dataset, self.script_dir, default_dataset)
        expected = os.path.abspath(os.path.join(self.script_dir, default_dataset))
        self.assertEqual(path, expected)

    def test_custom_dataset_prefers_existing_cwd_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                os.makedirs("benchmarks", exist_ok=True)
                rel_path = os.path.join("benchmarks", "demo.json")
                with open(rel_path, "w", encoding="utf-8") as f:
                    f.write("[]")

                path = resolve_dataset_path(rel_path, self.script_dir, "./benchmarks/g1_full_120_tasks.json")
                self.assertEqual(path, os.path.abspath(rel_path))
            finally:
                os.chdir(original_cwd)

    def test_default_output_is_script_relative(self):
        default_output = "../results"
        path = resolve_output_dir(default_output, self.script_dir, default_output)
        expected = os.path.abspath(os.path.join(self.script_dir, default_output))
        self.assertEqual(path, expected)

    def test_custom_output_is_cwd_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                path = resolve_output_dir("experiments/results", self.script_dir, "../results")
                self.assertEqual(path, os.path.abspath("experiments/results"))
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
