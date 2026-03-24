import json
import tempfile
import unittest
from pathlib import Path

from src.routing_engine.enhanced_routing import EnhancedRoutingEngine


class TestEnhancedRoutingPrior(unittest.TestCase):
    def test_load_priors_from_ablation(self):
        sample = {
            "metrics": {
                "full": {"11": {"success_rate": 0.9}},
                "no_rag": {"11": {"success_rate": 0.7}},
                "no_template": {"11": {"success_rate": 0.8}},
                "no_prompt": {"11": {"success_rate": 0.85}},
                "no_finetune": {"11": {"success_rate": 0.88}},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "g3.json"
            path.write_text(json.dumps(sample), encoding="utf-8")

            engine = EnhancedRoutingEngine(use_rl=False)
            ok = engine.load_priors_from_ablation(str(path))

            self.assertTrue(ok)
            self.assertTrue(engine.strategy_priors)
            self.assertGreater(engine.strategy_priors.get("rag_retrieval", 0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
