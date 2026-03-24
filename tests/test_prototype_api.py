import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from src.prototype.backend.app import app
    _HAS_FASTAPI = True
except ModuleNotFoundError:
    _HAS_FASTAPI = False


class _DummyGraphOps:
    def semantic_search(self, query, top_k=5):
        return []


class _DummyManager:
    def __init__(self):
        self.graph_ops = _DummyGraphOps()

    def add_candidate_experience(self, raw_data, auto_verify=True):
        return None


@unittest.skipUnless(_HAS_FASTAPI, "fastapi is not installed in current environment")
class TestPrototypeApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_search_top_k_validation(self):
        response = self.client.post("/api/experience/search", json={"query": "abc", "top_k": 0})
        self.assertEqual(response.status_code, 422)

    def test_recommend_top_k_validation(self):
        response = self.client.post(
            "/api/experience/recommend",
            json={"query": "abc", "current_code": "x=1", "top_k": 100},
        )
        self.assertEqual(response.status_code, 422)

    def test_add_quality_insufficient_returns_400(self):
        with patch("src.prototype.backend.app.experience_manager", _DummyManager()):
            response = self.client.post(
                "/api/experience/add",
                json={
                    "original_requirement": "r",
                    "user_instruction": "u",
                    "task_type": "code_generation",
                    "final_output": "o",
                    "is_success": True,
                    "execution_time": 0.1,
                },
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("经验质量不足", response.json().get("detail", ""))


if __name__ == "__main__":
    unittest.main()
