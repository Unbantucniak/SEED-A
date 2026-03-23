from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime
from src.experience_graph.operations import GraphOperations
from src.experience_graph.model import ExperienceUnit
from src.common.config import get_config_section

class StrategyType(Enum):
    """经验利用策略类型"""
    RAG_RETRIEVAL = "rag_retrieval"    # RAG即时检索
    TEMPLATE_REUSE = "template_reuse"  # 模板复用
    PROMPT_ENGINEERING = "prompt_engineering"  # 提示工程
    FINE_TUNING = "fine_tuning"        # 小模型微调

class RoutingEngine:
    """动态路由引擎类"""
    def __init__(self, graph_ops: Optional[GraphOperations] = None, config: Optional[Dict[str, Any]] = None):
        routing_cfg = get_config_section("routing_engine")
        merged_cfg = {**routing_cfg, **(config or {})}
        self.graph_ops = graph_ops or GraphOperations()
        # 策略权重配置，可通过强化学习动态调整
        self.strategy_weights = {
            "expected_benefit": float(merged_cfg.get("expected_benefit_weight", 0.4)),
            "success_probability": float(merged_cfg.get("success_probability_weight", 0.3)),
            "resource_cost": float(merged_cfg.get("resource_cost_weight", 0.2)),
            "response_speed": float(merged_cfg.get("response_speed_weight", 0.1)),
        }
        # 策略基础配置
        self.strategy_config = {
            StrategyType.RAG_RETRIEVAL: {
                "base_cost": 1.0,
                "base_latency": 0.5,  # 秒
                "min_success_rate": 0.6
            },
            StrategyType.TEMPLATE_REUSE: {
                "base_cost": 0.2,
                "base_latency": 0.1,
                "min_success_rate": 0.9
            },
            StrategyType.PROMPT_ENGINEERING: {
                "base_cost": 2.0,
                "base_latency": 1.0,
                "min_success_rate": 0.7
            },
            StrategyType.FINE_TUNING: {
                "base_cost": 10.0,
                "base_latency": 300.0,  # 5分钟
                "min_success_rate": 0.85
            }
        }
        disabled = merged_cfg.get("disabled_strategies", [])
        if isinstance(disabled, str):
            disabled = [item.strip() for item in disabled.split(",") if item.strip()]
        self.disabled_strategies = {str(item).strip().lower() for item in disabled if str(item).strip()}
        # 路由历史记录，用于强化学习训练
        self.routing_history = []

    def _is_strategy_disabled(self, strategy: StrategyType) -> bool:
        strategy_key = strategy.value.lower()
        strategy_name = strategy.name.lower()
        return strategy_key in self.disabled_strategies or strategy_name in self.disabled_strategies
    
    def extract_task_features(self, task_info: Dict[str, Any]) -> Dict[str, Any]:
        """提取任务特征"""
        return {
            "task_type": task_info.get("task_type", "unknown"),
            "domain_tags": task_info.get("domain_tags", []),
            "complexity": task_info.get("complexity", 3),
            "historical_frequency": task_info.get("historical_frequency", 0),
            "expected_benefit": task_info.get("expected_benefit", 1.0),
            "urgency": task_info.get("urgency", 0.5)  # 0=低，1=高
        }
    
    def get_matched_experiences(self, task_info: Dict[str, Any], top_k: int = 10) -> List[Dict]:
        """获取匹配的经验列表"""
        query = f"{task_info.get('original_requirement', '')} {task_info.get('user_instruction', '')}"
        return self.graph_ops.semantic_search(query, top_k=top_k)
    
    def calculate_strategy_score(self, 
                               strategy: StrategyType, 
                               task_features: Dict[str, Any],
                               matched_experiences: List[Dict],
                               system_status: Optional[Dict[str, Any]] = None) -> float:
        """计算单个策略的综合得分"""
        if self._is_strategy_disabled(strategy):
            return -1.0

        config = self.strategy_config[strategy]
        system_status = system_status or {"load": 0.5, "available_compute": 1.0}
        
        # 1. 计算成功概率
        if not matched_experiences:
            success_prob = 0.3  # 无匹配经验时的基础成功率
        else:
            avg_success = sum(exp["experience"].dynamic_meta.success_rate for exp in matched_experiences) / len(matched_experiences)
            avg_similarity = sum(exp["similarity"] for exp in matched_experiences) / len(matched_experiences)
            success_prob = min(1.0, avg_success * 0.7 + avg_similarity * 0.3)
        success_prob = max(success_prob, config["min_success_rate"])
        
        # 2. 计算预期收益
        base_benefit = task_features["expected_benefit"]
        if strategy == StrategyType.RAG_RETRIEVAL:
            benefit_multiplier = 1.0 + min(0.5, len(matched_experiences) * 0.1)
        elif strategy == StrategyType.TEMPLATE_REUSE:
            # 模板复用需要高度匹配的经验
            high_similarity_count = sum(1 for exp in matched_experiences if exp["similarity"] > 0.9)
            benefit_multiplier = 1.2 if high_similarity_count > 0 else 0.5
        elif strategy == StrategyType.PROMPT_ENGINEERING:
            benefit_multiplier = 1.1 + min(0.4, len(matched_experiences) * 0.05)
        elif strategy == StrategyType.FINE_TUNING:
            # 微调适合高频高价值任务
            benefit_multiplier = 0.5 if task_features["historical_frequency"] < 10 else 2.0
        expected_benefit = base_benefit * benefit_multiplier
        
        # 3. 计算资源开销评分（越低越好）
        base_cost = config["base_cost"]
        load_factor = 1 + system_status["load"] * 0.5  # 系统负载越高，开销评分越低
        cost_score = 1 / (1 + base_cost * load_factor)
        
        # 4. 计算响应速度评分（越快越好）
        base_latency = config["base_latency"]
        urgency_factor = 1 + task_features["urgency"] * 2  # 任务越紧急，延迟的惩罚越大
        speed_score = 1 / (1 + base_latency * urgency_factor / 10)
        
        # 综合得分
        total_score = (
            expected_benefit * self.strategy_weights["expected_benefit"] +
            success_prob * self.strategy_weights["success_probability"] +
            cost_score * self.strategy_weights["resource_cost"] +
            speed_score * self.strategy_weights["response_speed"]
        )
        
        return max(0.0, min(1.0, total_score))
    
    def route(self, 
             task_info: Dict[str, Any],
             system_status: Optional[Dict[str, Any]] = None,
             top_k_experiences: int = 5) -> Dict[str, Any]:
        """路由决策，选择最优策略"""
        # 提取特征
        task_features = self.extract_task_features(task_info)
        # 获取匹配经验
        matched_experiences = self.get_matched_experiences(task_info, top_k=10)
        # 计算所有策略的得分
        strategy_scores = {}
        enabled_scores = {}
        for strategy in StrategyType:
            score = self.calculate_strategy_score(strategy, task_features, matched_experiences, system_status)
            strategy_scores[strategy] = score
            if score >= 0:
                enabled_scores[strategy] = score

        if not enabled_scores:
            # 极端情况下全部被禁用，回退到RAG，保证系统可用。
            enabled_scores[StrategyType.RAG_RETRIEVAL] = 0.0
            strategy_scores[StrategyType.RAG_RETRIEVAL] = 0.0
        
        # 选择得分最高的策略
        best_strategy = max(enabled_scores.items(), key=lambda x: x[1])[0]
        
        # 准备返回结果
        result = {
            "selected_strategy": best_strategy.value,
            "selected_score": round(enabled_scores[best_strategy], 3),
            "strategy_scores": {s.value: round(sc, 3) for s, sc in strategy_scores.items()},
            "matched_experiences": [
                {
                    "experience_id": exp["experience_id"],
                    "similarity": round(exp["similarity"], 3),
                    "success_rate": round(exp["experience"].dynamic_meta.success_rate, 3),
                    "composite_score": round(exp["composite_score"], 3)
                } for exp in matched_experiences[:top_k_experiences]
            ],
            "task_features": task_features,
            "timestamp": datetime.now().isoformat()
        }
        
        # 记录路由历史
        self.routing_history.append({
            "task_info": task_info,
            "result": result,
            "actual_outcome": None  # 后续可以回填实际结果用于强化学习
        })
        
        return result
    
    def update_routing_outcome(self, routing_timestamp: str, actual_success: bool, actual_benefit: float) -> bool:
        """回填路由结果，用于强化学习优化"""
        for record in self.routing_history:
            if record["result"]["timestamp"] == routing_timestamp:
                record["actual_outcome"] = {
                    "success": actual_success,
                    "benefit": actual_benefit
                }
                return True
        return False
    
    def get_internalization_candidates(self, min_use_count: int = 10, min_success_rate: float = 0.8) -> List[str]:
        """获取适合模型内化的经验候选列表"""
        candidates = []
        for exp_id, exp in self.graph_ops.graph.experience_nodes.items():
            if (exp.dynamic_meta.use_count >= min_use_count and 
                exp.dynamic_meta.success_rate >= min_success_rate and
                exp.static_meta.generalization >= 0.6):
                candidates.append(exp_id)
        return candidates
    
    def optimize_strategy_weights(self) -> Dict[str, float]:
        """基于历史路由数据优化策略权重（简化版）"""
        # 实际场景可替换为强化学习训练逻辑
        # 这里返回当前权重作为示例
        return self.strategy_weights

    def get_strategy_usage_stats(self) -> Dict[str, Any]:
        """统计各策略路由使用分布，供监控模块直接消费。"""
        usage = {strategy.value: 0 for strategy in StrategyType}
        total = len(self.routing_history)

        for record in self.routing_history:
            selected = record.get("result", {}).get("selected_strategy")
            if selected in usage:
                usage[selected] += 1

        distribution = {
            key: (count / total if total else 0.0)
            for key, count in usage.items()
        }

        return {
            "total": total,
            "counts": usage,
            "distribution": distribution,
        }
