import unittest

from src.experience_manager.enhanced_manager import AdversarialValidator, EnhancedExperienceManager


class TestEnhancedManager(unittest.TestCase):
    def test_evaluation_payload_alignment(self):
        manager = EnhancedExperienceManager(use_llm_judge=False)
        raw = {
            "original_requirement": "实现排序函数",
            "user_instruction": "写一个快速排序",
            "task_type": "code_generation",
            "final_output": "def sort_nums(nums): return sorted(nums)",
            "is_success": True,
            "execution_time": 0.2,
        }
        exp = manager.base_manager.extract_experience_from_raw_data(raw)
        payload = manager._to_evaluation_payload(raw, exp)

        self.assertIn("task_intent", payload)
        self.assertIn("execution_result", payload)
        self.assertEqual(payload["execution_result"]["is_success"], True)
        self.assertIn("final_output", payload["execution_result"])

    def test_counterfactual_robustness_rule(self):
        validator = AdversarialValidator()
        exp = {
            "task_intent": {
                "original_requirement": "请实现排序算法",
                "user_instruction": "输出可运行代码",
                "task_type": "code_generation",
            },
            "execution_result": {
                "final_output": "print('hello world')"
            },
        }
        result = validator._check_counterfactual_robustness(exp, [])
        self.assertFalse(result["passed"])
        self.assertEqual(result["type"], "counterfactual_robustness")


if __name__ == "__main__":
    unittest.main()
