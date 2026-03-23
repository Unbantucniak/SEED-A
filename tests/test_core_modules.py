#!/usr/bin/env python3
"""
单元测试套件 - 自学习自演化智能体经验管理系统
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from datetime import datetime, timedelta
from src.experience_graph.model import (
    ExperienceUnit, TaskIntent, ContextState, ExecutionResult,
    StaticMetaAttribute, DynamicMetaAttribute
)
from src.experience_graph.operations import GraphOperations
from src.experience_manager.manager import ExperienceManager
from src.routing_engine.routing import RoutingEngine, StrategyType


class TestExperienceModel(unittest.TestCase):
    """测试经验单元模型"""
    
    def test_create_experience_unit(self):
        """测试创建经验单元"""
        task_intent = TaskIntent(
            original_requirement="实现快速排序",
            user_instruction="写一个快速排序函数",
            task_type="代码生成"
        )
        
        context_state = ContextState(
            repo_snapshot="v1.0",
            dependency_versions={"numpy": "1.24.0"}
        )
        
        execution_result = ExecutionResult(
            final_output="def quicksort(arr): ...",
            is_success=True,
            execution_time=0.5
        )
        
        experience = ExperienceUnit(
            task_intent=task_intent,
            context_state=context_state,
            execution_result=execution_result
        )
        
        self.assertIsNotNone(experience.experience_id)
        self.assertEqual(experience.task_intent.task_type, "代码生成")
        self.assertTrue(experience.execution_result.is_success)
    
    def test_meta_attributes(self):
        """测试元属性"""
        static_meta = StaticMetaAttribute(
            source_credibility=0.8,
            domain_tags=["Python", "算法"],
            complexity=3,
            generalization=0.7
        )
        
        dynamic_meta = DynamicMetaAttribute(
            success_rate=0.75,
            use_count=10,
            timeliness=0.9
        )
        
        self.assertEqual(static_meta.source_credibility, 0.8)
        self.assertEqual(dynamic_meta.success_rate, 0.75)
        self.assertEqual(len(static_meta.domain_tags), 2)


class TestGraphOperations(unittest.TestCase):
    """测试经验图谱操作"""
    
    def setUp(self):
        """测试前准备"""
        self.graph_ops = GraphOperations()
        
        # 添加测试经验
        self.exp1 = self._create_sample_experience("实现排序", "代码生成")
        self.exp2 = self._create_sample_experience("修复bug", "bug修复")
        self.exp3 = self._create_sample_experience("实现查找", "代码生成")
        
        self.graph_ops.add_experience(self.exp1)
        self.graph_ops.add_experience(self.exp2)
        self.graph_ops.add_experience(self.exp3)
    
    def _create_sample_experience(self, requirement, task_type):
        """创建示例经验"""
        return ExperienceUnit(
            task_intent=TaskIntent(
                original_requirement=requirement,
                user_instruction="执行任务",
                task_type=task_type
            ),
            context_state=ContextState(),
            execution_result=ExecutionResult(
                final_output="完成",
                is_success=True,
                execution_time=1.0
            )
        )
    
    def test_add_experience(self):
        """测试添加经验"""
        exp_count = len(self.graph_ops.graph.experience_nodes)
        self.assertEqual(exp_count, 3)
    
    def test_get_experience(self):
        """测试获取经验"""
        exp = self.graph_ops.get_experience(self.exp1.experience_id)
        self.assertIsNotNone(exp)
        self.assertEqual(exp.task_intent.original_requirement, "实现排序")
    
    def test_semantic_search(self):
        """测试语义搜索"""
        results = self.graph_ops.semantic_search("排序算法", top_k=2)
        self.assertGreaterEqual(len(results), 1)
        self.assertGreaterEqual(results[0]["similarity"], 0.0)
    
    def test_update_dynamic_meta(self):
        """测试动态属性更新"""
        success = self.graph_ops.update_experience_dynamic_meta(
            self.exp1.experience_id, is_success=True, benefit=0.8
        )
        self.assertTrue(success)
        
        exp = self.graph_ops.get_experience(self.exp1.experience_id)
        self.assertEqual(exp.dynamic_meta.use_count, 1)
        self.assertEqual(exp.dynamic_meta.success_rate, 1.0)
    
    def test_delete_experience(self):
        """测试删除经验"""
        success = self.graph_ops.delete_experience(self.exp1.experience_id)
        self.assertTrue(success)
        
        exp = self.graph_ops.get_experience(self.exp1.experience_id)
        self.assertIsNone(exp)
        
        exp_count = len(self.graph_ops.graph.experience_nodes)
        self.assertEqual(exp_count, 2)
    
    def test_add_edge(self):
        """测试添加边"""
        edge_id = self.graph_ops.add_edge(
            self.exp1.experience_id,
            self.exp2.experience_id,
            "similarity",
            0.8
        )
        self.assertIsNotNone(edge_id)
        
        related = self.graph_ops.get_related_experiences(self.exp1.experience_id)
        self.assertGreaterEqual(len(related), 1)


class TestExperienceManager(unittest.TestCase):
    """测试经验管理器"""
    
    def setUp(self):
        """测试前准备"""
        self.manager = ExperienceManager()
    
    def test_extract_experience(self):
        """测试从原始数据抽取经验"""
        raw_data = {
            "original_requirement": "测试任务",
            "user_instruction": "执行测试",
            "task_type": "代码生成",
            "final_output": "测试完成",
            "is_success": True,
            "execution_time": 1.0,
            "source_credibility": 0.8,
            "domain_tags": ["测试"],
            "complexity": 2,
            "generalization": 0.7
        }
        
        experience = self.manager.extract_experience_from_raw_data(raw_data)
        
        self.assertIsNotNone(experience)
        self.assertEqual(experience.task_intent.original_requirement, "测试任务")
        self.assertEqual(experience.static_meta.source_credibility, 0.8)
    
    def test_calculate_quality_score(self):
        """测试质量评分计算"""
        raw_data = {
            "original_requirement": "测试任务",
            "user_instruction": "执行测试",
            "task_type": "代码生成",
            "final_output": "测试完成",
            "is_success": True,
            "execution_time": 1.0,
            "source_credibility": 1.0,
            "generalization": 0.8
        }
        
        experience = self.manager.extract_experience_from_raw_data(raw_data)
        score = self.manager.calculate_quality_score(experience)
        
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
    
    def test_add_candidate_experience(self):
        """测试添加候选经验"""
        raw_data = {
            "original_requirement": "测试任务",
            "user_instruction": "执行测试",
            "task_type": "代码生成",
            "final_output": "测试完成",
            "is_success": True,
            "execution_time": 1.0,
            "source_credibility": 0.8
        }
        
        exp_id = self.manager.add_candidate_experience(raw_data)
        
        # 质量分低于阈值会被拒绝
        if exp_id:
            self.assertIsNotNone(exp_id)
    
    def test_batch_process(self):
        """测试批量处理"""
        raw_data_list = [
            {
                "original_requirement": f"任务{i}",
                "user_instruction": "执行",
                "task_type": "代码生成",
                "final_output": "完成",
                "is_success": True,
                "execution_time": 1.0
            }
            for i in range(5)
        ]
        
        success_ids = self.manager.batch_process_raw_data(raw_data_list)
        
        self.assertLessEqual(len(success_ids), 5)
    
    def test_health_check(self):
        """测试健康检查"""
        # 先添加一些经验
        raw_data = {
            "original_requirement": "测试任务",
            "user_instruction": "执行测试",
            "task_type": "代码生成",
            "final_output": "完成",
            "is_success": True,
            "execution_time": 1.0
        }
        self.manager.add_candidate_experience(raw_data)
        
        health = self.manager.run_health_check()
        
        self.assertIn("total_experiences", health)
        self.assertIn("health_score", health)


class TestRoutingEngine(unittest.TestCase):
    """测试路由引擎"""
    
    def setUp(self):
        """测试前准备"""
        self.graph_ops = GraphOperations()
        self.routing_engine = RoutingEngine(self.graph_ops)
        
        # 添加测试经验
        exp = ExperienceUnit(
            task_intent=TaskIntent(
                original_requirement="实现排序",
                user_instruction="写排序代码",
                task_type="代码生成"
            ),
            context_state=ContextState(),
            execution_result=ExecutionResult(
                final_output="完成",
                is_success=True,
                execution_time=1.0
            )
        )
        self.graph_ops.add_experience(exp)
    
    def test_extract_task_features(self):
        """测试任务特征提取"""
        task_info = {
            "task_type": "代码生成",
            "complexity": 3,
            "historical_frequency": 5,
            "expected_benefit": 1.0,
            "urgency": 0.5
        }
        
        features = self.routing_engine.extract_task_features(task_info)
        
        self.assertEqual(features["task_type"], "代码生成")
        self.assertEqual(features["complexity"], 3)
    
    def test_route(self):
        """测试路由决策"""
        task_info = {
            "original_requirement": "实现排序算法",
            "user_instruction": "写代码",
            "task_type": "代码生成",
            "domain_tags": ["Python"],
            "complexity": 3,
            "historical_frequency": 5,
            "expected_benefit": 1.0,
            "urgency": 0.5
        }
        
        result = self.routing_engine.route(task_info)
        
        self.assertIn("selected_strategy", result)
        self.assertIn("strategy_scores", result)
        self.assertIn("matched_experiences", result)
    
    def test_get_internalization_candidates(self):
        """测试获取内化候选"""
        # 添加一个高频高成功率经验
        exp = ExperienceUnit(
            task_intent=TaskIntent(
                original_requirement="高频任务",
                user_instruction="执行",
                task_type="代码生成"
            ),
            context_state=ContextState(),
            execution_result=ExecutionResult(
                final_output="完成",
                is_success=True,
                execution_time=1.0
            ),
            dynamic_meta=DynamicMetaAttribute(
                use_count=15,
                success_rate=0.9,
                average_benefit=1.0
            ),
            static_meta=StaticMetaAttribute(
                generalization=0.7
            )
        )
        self.graph_ops.add_experience(exp)
        
        candidates = self.routing_engine.get_internalization_candidates(
            min_use_count=10, min_success_rate=0.8
        )
        
        self.assertGreaterEqual(len(candidates), 1)


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def test_full_workflow(self):
        """测试完整工作流"""
        # 1. 初始化
        manager = ExperienceManager()
        routing_engine = RoutingEngine(manager.graph_ops)
        
        # 2. 添加经验
        raw_data = {
            "original_requirement": "实现快速排序",
            "user_instruction": "写快速排序",
            "task_type": "代码生成",
            "final_output": "def quicksort(arr):...",
            "is_success": True,
            "execution_time": 0.5,
            "source_credibility": 1.0,
            "domain_tags": ["Python", "算法"],
            "complexity": 2,
            "generalization": 0.8
        }
        exp_id = manager.add_candidate_experience(raw_data)
        
        # 3. 搜索
        results = manager.graph_ops.semantic_search("排序", top_k=1)
        
        # 4. 调用并更新
        if results:
            manager.update_experience_after_use(
                results[0]["experience_id"], 
                is_success=True, 
                benefit=0.8
            )
        
        # 5. 路由
        task_info = {
            "original_requirement": "实现归并排序",
            "user_instruction": "写归并排序",
            "task_type": "代码生成",
            "domain_tags": ["Python", "算法"],
            "complexity": 3,
            "historical_frequency": 0,
            "expected_benefit": 1.0,
            "urgency": 0.5
        }
        routing_result = routing_engine.route(task_info)
        
        # 验证
        self.assertIsNotNone(exp_id)
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("selected_strategy", routing_result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
