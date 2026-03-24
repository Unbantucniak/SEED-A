import os
import tempfile
import unittest

from experiments.run_logger import append_run_log


class TestRunLogger(unittest.TestCase):
    def test_append_run_log_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = append_run_log(
                log_dir=tmp,
                title="unit_test",
                params={"a": 1},
                outputs={"b": 2},
            )
            self.assertTrue(os.path.exists(log_path))
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("unit_test", content)
            self.assertIn('"a": 1', content)

    def test_rotate_when_oversized(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "experiment_run_log.md")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("x" * 2048)

            append_run_log(
                log_dir=tmp,
                title="rotate_case",
                params={"r": 1},
                outputs={"o": 1},
                max_file_size_mb=1,
                backup_count=5,
            )

            # 1MB threshold won't rotate a 2KB file
            archives = [n for n in os.listdir(tmp) if n.startswith("experiment_run_log_")]
            self.assertEqual(len(archives), 0)

            append_run_log(
                log_dir=tmp,
                title="force_rotate_case",
                params={"r": 2},
                outputs={"o": 2},
                max_file_size_mb=0,
                backup_count=5,
            )

            # max_file_size_mb=0 disables rotation
            archives = [n for n in os.listdir(tmp) if n.startswith("experiment_run_log_")]
            self.assertEqual(len(archives), 0)

            append_run_log(
                log_dir=tmp,
                title="actual_rotate_case",
                params={"r": 3},
                outputs={"o": 3},
                max_file_size_mb=1,
                backup_count=5,
            )

            # Still no rotation expected at 2KB threshold; enforce by writing larger file.
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("y" * (2 * 1024 * 1024))

            append_run_log(
                log_dir=tmp,
                title="actual_rotate_case_2",
                params={"r": 4},
                outputs={"o": 4},
                max_file_size_mb=1,
                backup_count=5,
            )

            archives = [n for n in os.listdir(tmp) if n.startswith("experiment_run_log_")]
            self.assertGreaterEqual(len(archives), 1)
            self.assertTrue(os.path.exists(log_path))


if __name__ == "__main__":
    unittest.main()
