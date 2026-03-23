"""
基线方案基类
所有对比基线都需要继承该类并实现核心接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple

class BaseBaseline(ABC):
    """基线方案抽象基类"""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        # 统计指标
        self.total_tasks = 0
        self.success_tasks = 0
        self.total_interaction_rounds = 0
        self.total_time_cost = 0.0
        self.total_token_cost = 0
    
    @abstractmethod
    def solve_task(self, task: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        解决单个任务，返回结果和详细信息
        Args:
            task: 评测任务信息
        Returns:
            result: 任务结果（代码/分解结果等）
            info: 详细信息，包含耗时、token消耗、交互轮次等
        """
        pass
    
    def reset_stats(self) -> None:
        """重置统计指标"""
        self.total_tasks = 0
        self.success_tasks = 0
        self.total_interaction_rounds = 0
        self.total_time_cost = 0.0
        self.total_token_cost = 0
    
    def update_stats(self, success: bool, interaction_rounds: int, time_cost: float, token_cost: int) -> None:
        """更新统计指标"""
        self.total_tasks += 1
        if success:
            self.success_tasks += 1
        self.total_interaction_rounds += interaction_rounds
        self.total_time_cost += time_cost
        self.total_token_cost += token_cost
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取当前统计指标"""
        if self.total_tasks == 0:
            return {
                "name": self.name,
                "total_tasks": 0,
                "success_rate": 0.0,
                "avg_interaction_rounds": 0.0,
                "avg_time_cost": 0.0,
                "avg_token_cost": 0.0
            }
        
        return {
            "name": self.name,
            "total_tasks": self.total_tasks,
            "success_rate": self.success_tasks / self.total_tasks,
            "avg_interaction_rounds": self.total_interaction_rounds / self.total_tasks,
            "avg_time_cost": self.total_time_cost / self.total_tasks,
            "avg_token_cost": self.total_token_cost / self.total_tasks
        }
