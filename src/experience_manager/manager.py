from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import json
from src.experience_graph.model import (
    ExperienceUnit,
    TaskIntent,
    ContextState,
    ExecutionResult,
    OperationStep,
    ExperienceGraph,
)
from src.experience_graph.operations import GraphOperations
from src.common.config import get_config_section

class ExperienceManager:
    """经验全生命周期管理类"""
    def __init__(self, graph_ops: Optional[GraphOperations] = None, config: Optional[Dict[str, Any]] = None):
        manager_cfg = get_config_section("experience_manager")
        merged_cfg = {**manager_cfg, **(config or {})}
        self.graph_ops = graph_ops or GraphOperations()
        # 配置参数
        self.config = {
            "min_quality_score": float(merged_cfg.get("min_quality_score", 0.5)),
            "timeliness_threshold": float(merged_cfg.get("timeliness_threshold", 0.2)),
            "success_rate_threshold": float(merged_cfg.get("success_rate_threshold", 0.3)),
            "unused_days_threshold": int(merged_cfg.get("unused_days_threshold", 365)),
            "health_check_interval_days": int(merged_cfg.get("health_check_interval_days", 7)),
        }
        self.last_health_check = None
    
    def extract_experience_from_raw_data(self, raw_data: Dict[str, Any]) -> Optional[ExperienceUnit]:
        """从原始交互数据中抽取经验单元"""
        try:
            # 解析原始数据字段
            task_intent = TaskIntent(
                original_requirement=raw_data["original_requirement"],
                user_instruction=raw_data["user_instruction"],
                task_type=raw_data["task_type"]
            )
            
            context_state = ContextState(
                repo_snapshot=raw_data.get("repo_snapshot"),
                dependency_versions=raw_data.get("dependency_versions", {}),
                environment_config=raw_data.get("environment_config", {}),
                history_context=raw_data.get("history_context", [])
            )
            
            operation_sequence = [
                OperationStep(**step) for step in raw_data.get("operation_sequence", [])
            ]
            
            execution_result = ExecutionResult(
                final_output=raw_data["final_output"],
                is_success=raw_data["is_success"],
                error_info=raw_data.get("error_info"),
                user_feedback=raw_data.get("user_feedback"),
                execution_time=raw_data["execution_time"],
                resource_cost=raw_data.get("resource_cost", {})
            )
            
            experience = ExperienceUnit(
                task_intent=task_intent,
                context_state=context_state,
                operation_sequence=operation_sequence,
                constraints=raw_data.get("constraints", []),
                execution_result=execution_result
            )
            
            # 设置初始元属性
            if "source_credibility" in raw_data:
                experience.static_meta.source_credibility = raw_data["source_credibility"]
            if "domain_tags" in raw_data:
                experience.static_meta.domain_tags = raw_data["domain_tags"]
            if "complexity" in raw_data:
                experience.static_meta.complexity = raw_data["complexity"]
            if "generalization" in raw_data:
                experience.static_meta.generalization = raw_data["generalization"]
            
            return experience
        except Exception as e:
            print(f"经验抽取失败: {str(e)}")
            return None
    
    def calculate_quality_score(self, experience: ExperienceUnit) -> float:
        """计算经验质量得分，判断是否可以入库"""
        # 完整性检查：必填字段是否齐全
        integrity = 1.0
        required_fields = ["task_intent", "context_state", "execution_result", "operation_sequence"]
        for field in required_fields:
            if not getattr(experience, field):
                integrity -= 0.25
        integrity = max(0.0, integrity)
        
        score = (
            experience.static_meta.source_credibility * 0.3 +
            experience.dynamic_meta.success_rate * 0.4 +
            experience.static_meta.generalization * 0.2 +
            integrity * 0.1
        )
        return max(0.0, min(1.0, score))
    
    def add_candidate_experience(self, raw_data: Dict[str, Any], auto_verify: bool = True) -> Optional[str]:
        """添加候选经验，经过质量评估后自动入库"""
        experience = self.extract_experience_from_raw_data(raw_data)
        if not experience:
            return None
        
        quality_score = self.calculate_quality_score(experience)
        if quality_score < self.config["min_quality_score"]:
            print(f"经验质量分{quality_score:.2f}低于阈值{self.config['min_quality_score']}，不予入库")
            return None
        
        if auto_verify:
            # 自动验证：简单验证执行结果是否符合预期，复杂场景可扩展为自动化测试
            pass
        
        # 正式入库
        exp_id = self.graph_ops.add_experience(experience)
        print(f"经验{exp_id}入库成功，质量分: {quality_score:.2f}")
        return exp_id
    
    def batch_process_raw_data(self, raw_data_list: List[Dict[str, Any]]) -> List[str]:
        """批量处理原始交互数据，抽取经验入库"""
        success_ids = []
        for raw_data in raw_data_list:
            exp_id = self.add_candidate_experience(raw_data)
            if exp_id:
                success_ids.append(exp_id)
        return success_ids
    
    def update_experience_after_use(self, experience_id: str, is_success: bool, benefit: float) -> bool:
        """经验被调用后更新动态属性"""
        return self.graph_ops.update_experience_dynamic_meta(experience_id, is_success, benefit)
    
    def get_outdated_experiences(self) -> List[str]:
        """识别需要淘汰的过期经验"""
        outdated_ids = []
        current_time = datetime.now()
        
        for exp_id, exp in self.graph_ops.graph.experience_nodes.items():
            # 检查时效性
            if exp.dynamic_meta.timeliness < self.config["timeliness_threshold"]:
                outdated_ids.append(exp_id)
                continue
            # 检查成功率
            if exp.dynamic_meta.success_rate < self.config["success_rate_threshold"] and exp.dynamic_meta.use_count >= 5:
                outdated_ids.append(exp_id)
                continue
            # 检查未使用时间
            unused_days = (current_time - exp.last_used_at).days
            if unused_days > self.config["unused_days_threshold"]:
                outdated_ids.append(exp_id)
                continue
        
        return list(set(outdated_ids))
    
    def clean_outdated_experiences(self, auto_delete: bool = False) -> List[str]:
        """清理过期经验"""
        outdated_ids = self.get_outdated_experiences()
        if not outdated_ids:
            return []
        
        if auto_delete:
            deleted_ids = []
            for exp_id in outdated_ids:
                if self.graph_ops.delete_experience(exp_id):
                    deleted_ids.append(exp_id)
            print(f"已清理{len(deleted_ids)}条过期经验")
            return deleted_ids
        else:
            print(f"识别到{len(outdated_ids)}条待清理过期经验，需确认后删除")
            return outdated_ids
    
    def calculate_health_score(self) -> Dict[str, Any]:
        """计算经验库健康度得分"""
        total_count = len(self.graph_ops.graph.experience_nodes)
        if total_count == 0:
            return {
                "total_experiences": 0,
                "health_score": 0.0,
                "metrics": {}
            }
        
        # 计算各项指标
        avg_success_rate = sum(exp.dynamic_meta.success_rate for exp in self.graph_ops.graph.experience_nodes.values()) / total_count
        avg_timeliness = sum(exp.dynamic_meta.timeliness for exp in self.graph_ops.graph.experience_nodes.values()) / total_count
        
        # 计算冗余率：相似度>0.9的经验对占比
        redundant_count = 0
        # 简化计算，实际场景可优化
        redundancy_rate = 0.1  # 模拟值
        
        # 计算冲突率
        conflict_rate = sum(exp.dynamic_meta.conflict_score for exp in self.graph_ops.graph.experience_nodes.values()) / total_count
        
        # 计算调用覆盖率
        used_count = sum(1 for exp in self.graph_ops.graph.experience_nodes.values() if exp.dynamic_meta.use_count > 0)
        coverage_rate = used_count / total_count
        
        # 计算总健康度
        health_score = (
            avg_success_rate * 0.4 +
            avg_timeliness * 0.2 +
            (1 - redundancy_rate) * 0.2 +
            (1 - conflict_rate) * 0.1 +
            coverage_rate * 0.1
        )
        
        return {
            "total_experiences": total_count,
            "health_score": round(health_score, 3),
            "metrics": {
                "average_success_rate": round(avg_success_rate, 3),
                "average_timeliness": round(avg_timeliness, 3),
                "redundancy_rate": round(redundancy_rate, 3),
                "conflict_rate": round(conflict_rate, 3),
                "call_coverage_rate": round(coverage_rate, 3)
            }
        }
    
    def run_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        self.last_health_check = datetime.now()
        # 更新所有经验的时效性
        self.graph_ops.update_timeliness()
        # 计算健康度
        health_info = self.calculate_health_score()
        # 识别过期经验
        outdated = self.get_outdated_experiences()
        health_info["outdated_experiences_count"] = len(outdated)
        health_info["outdated_experience_ids"] = outdated
        return health_info
    
    def export_experience_library(self, output_path: str) -> bool:
        """导出经验库为JSON文件"""
        try:
            data = self.graph_ops.graph.model_dump_json(indent=2, exclude_none=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(data)
            print(f"经验库已导出到: {output_path}")
            return True
        except Exception as e:
            print(f"导出经验库失败: {str(e)}")
            return False
    
    def import_experience_library(self, input_path: str) -> bool:
        """从JSON文件导入经验库"""
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.graph_ops.graph = ExperienceGraph(**data)
            print(f"经验库导入成功，共{len(self.graph_ops.graph.experience_nodes)}条经验")
            return True
        except Exception as e:
            print(f"导入经验库失败: {str(e)}")
            return False
