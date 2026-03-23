"""
各基线方案的具体实现
"""
from typing import Dict, Any, Tuple
import time
import random
from .base_baseline import BaseBaseline
from src.experience_manager.manager import ExperienceManager
from src.routing_engine.routing import RoutingEngine


def _build_rng(config: Dict[str, Any], offset: int) -> random.Random:
    seed = int(config.get("seed", 42)) + offset
    return random.Random(seed)


def _sleep_if_enabled(config: Dict[str, Any], seconds: float) -> None:
    if not bool(config.get("simulate_latency", False)):
        return
    scale = float(config.get("latency_scale", 1.0))
    time.sleep(max(0.0, seconds * scale))

class Baseline1_NoExperience(BaseBaseline):
    """基线1：无经验积累，普通大模型调用（模拟实现）"""
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("baseline1_no_experience", config)
        self.rng = _build_rng(self.config, offset=1)
    
    def solve_task(self, task: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        start_time = time.time()
        # 模拟模型调用耗时
        _sleep_if_enabled(self.config, self.rng.uniform(0.5, 2.0))
        # 模拟成功率：60%左右
        success = self.rng.random() < 0.6
        # 模拟token消耗
        token_cost = self.rng.randint(500, 2000)
        # 交互轮次：平均3轮
        interaction_rounds = self.rng.randint(1, 5)
        
        result = "模拟生成的代码/结果" if success else "任务失败"
        time_cost = time.time() - start_time
        
        self.update_stats(success, interaction_rounds, time_cost, token_cost)
        
        info = {
            "success": success,
            "interaction_rounds": interaction_rounds,
            "time_cost": time_cost,
            "token_cost": token_cost
        }
        return result, info

class Baseline2_OnlyRAG(BaseBaseline):
    """基线2：仅向量检索RAG（模拟实现）"""
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("baseline2_only_rag", config)
        self.retrieved_count = 0
        self.rng = _build_rng(self.config, offset=2)
    
    def solve_task(self, task: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        start_time = time.time()
        # 模拟检索耗时
        _sleep_if_enabled(self.config, self.rng.uniform(0.1, 0.5))
        # 模拟检索到相关经验的概率：70%
        has_retrieved = self.rng.random() < 0.7
        if has_retrieved:
            self.retrieved_count += 1
            # 有检索结果时成功率更高，耗时更少
            success = self.rng.random() < 0.75
            token_cost = self.rng.randint(400, 1500)
            interaction_rounds = self.rng.randint(1, 4)
        else:
            success = self.rng.random() < 0.6
            token_cost = self.rng.randint(500, 2000)
            interaction_rounds = self.rng.randint(1, 5)
        
        time_cost = time.time() - start_time
        self.update_stats(success, interaction_rounds, time_cost, token_cost)
        
        result = "基于RAG生成的结果" if success else "任务失败"
        info = {
            "success": success,
            "has_retrieved": has_retrieved,
            "interaction_rounds": interaction_rounds,
            "time_cost": time_cost,
            "token_cost": token_cost
        }
        return result, info

class Baseline3_PeriodicFinetune(BaseBaseline):
    """基线3：周期性微调（模拟实现）"""
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("baseline3_periodic_finetune", config)
        self.task_count = 0
        self.finetune_count = 0
        self.rng = _build_rng(self.config, offset=3)
    
    def solve_task(self, task: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        start_time = time.time()
        self.task_count += 1
        
        # 每10个任务模拟一次微调效果提升
        if self.task_count % 10 == 0:
            self.finetune_count += 1
            _sleep_if_enabled(self.config, self.rng.uniform(10, 30))
        
        # 成功率随微调次数提升
        base_success = 0.6 + min(0.2, self.finetune_count * 0.03)
        success = self.rng.random() < base_success
        token_cost = self.rng.randint(300, 1200)
        interaction_rounds = self.rng.randint(1, 3)
        
        time_cost = time.time() - start_time
        self.update_stats(success, interaction_rounds, time_cost, token_cost)
        
        result = "基于微调模型生成的结果" if success else "任务失败"
        info = {
            "success": success,
            "finetune_count": self.finetune_count,
            "interaction_rounds": interaction_rounds,
            "time_cost": time_cost,
            "token_cost": token_cost
        }
        return result, info

class Ours_ProposedScheme(BaseBaseline):
    """本项目方案：完整的经验积累与演化系统（模拟实现）"""
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("ours_proposed_scheme", config)
        self.rng = _build_rng(self.config, offset=4)
        # 初始化真实的核心模块
        self.experience_manager = ExperienceManager(config=self.config)
        self.routing_engine = RoutingEngine(self.experience_manager.graph_ops, config=self.config)
        self.success_history = []
    
    def solve_task(self, task: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        start_time = time.time()
        
        # 真实调用路由引擎
        routing_result = self.routing_engine.route(task)
        selected_strategy = routing_result["selected_strategy"]
        matched_experiences = routing_result["matched_experiences"]
        
        # 根据策略模拟效果
        if matched_experiences:
            avg_success = sum(exp["success_rate"] for exp in matched_experiences) / len(matched_experiences)
            base_success = 0.7 + min(0.25, avg_success * 0.3)
        else:
            base_success = 0.65
        
        # 经验越多效果越好
        experience_count = len(self.experience_manager.graph_ops.graph.experience_nodes)
        experience_bonus = min(0.15, experience_count * 0.005)
        success = self.rng.random() < (base_success + experience_bonus)
        
        # 效率提升
        interaction_rounds = self.rng.randint(1, 3) if matched_experiences else self.rng.randint(2, 4)
        token_cost = self.rng.randint(300, 1200) if matched_experiences else self.rng.randint(400, 1600)
        
        # 任务成功则自动添加到经验库
        if success:
            # 构造经验原始数据
            raw_data = {
                "original_requirement": task["requirement"],
                "user_instruction": task.get("user_instruction", task["requirement"]),
                "task_type": task["task_type"].value if hasattr(task["task_type"], "value") else str(task["task_type"]),
                "is_success": True,
                "execution_time": time.time() - start_time,
                "final_output": "成功结果",
                "source_credibility": 0.8 if success else 0.3,
                "domain_tags": task.get("domain_tags", [])
            }
            self.experience_manager.add_candidate_experience(raw_data, auto_verify=True)
        
        time_cost = time.time() - start_time
        self.update_stats(success, interaction_rounds, time_cost, token_cost)
        
        result = "基于经验系统生成的结果" if success else "任务失败"
        info = {
            "success": success,
            "selected_strategy": selected_strategy,
            "matched_experience_count": len(matched_experiences),
            "total_experiences": experience_count + (1 if success else 0),
            "interaction_rounds": interaction_rounds,
            "time_cost": time_cost,
            "token_cost": token_cost
        }
        return result, info
