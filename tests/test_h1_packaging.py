import tempfile
import unittest
from pathlib import Path

from experiments.run_h1_packaging import read_json


class TestH1Packaging(unittest.TestCase):
    def test_read_json_lenient_collects_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{invalid", encoding="utf-8")
            warnings = []
            data = read_json(bad, strict=False, label="g2", warnings=warnings)
            self.assertEqual(data, {})
            self.assertTrue(warnings)
            self.assertIn("g2", warnings[0])

    def test_read_json_strict_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{invalid", encoding="utf-8")
            warnings = []
            with self.assertRaises(RuntimeError):
                read_json(bad, strict=True, label="g2", warnings=warnings)


if __name__ == "__main__":
    unittest.main()
