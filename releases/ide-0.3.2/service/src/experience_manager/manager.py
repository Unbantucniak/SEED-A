from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta  # noqa: F401
import json
import logging
import os
from pathlib import Path
import tempfile
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


logger = logging.getLogger(__name__)

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
            "min_validation_score": float(merged_cfg.get("min_validation_score", 0.5)),
        }
        self.last_health_check = None

    def _compute_validation_metrics(self, raw_data: Dict[str, Any], experience: ExperienceUnit) -> Dict[str, Any]:
        """区分外部测试字段与人工报告；自述成功永远不是测试证据。"""
        import math
        import re

        exec_result = experience.execution_result
        final_output = (exec_result.final_output or "").strip()
        rate = raw_data.get("test_pass_rate")
        test_pass_rate = None
        invalid_evidence = False
        if rate is not None:
            if (isinstance(rate, (int, float)) and not isinstance(rate, bool)
                    and math.isfinite(rate) and 0 <= rate <= 1):
                test_pass_rate = float(rate)
            else:
                invalid_evidence = True
        if "tests_passed" in raw_data or "tests_total" in raw_data:
            passed, total = raw_data.get("tests_passed"), raw_data.get("tests_total")
            if (type(passed) is int and type(total) is int
                    and total > 0 and 0 <= passed <= total):
                measured_rate = passed / total
                if test_pass_rate is not None and not math.isclose(test_pass_rate, measured_rate):
                    invalid_evidence = True
                test_pass_rate = measured_rate
            else:
                invalid_evidence = True
        if invalid_evidence:
            test_pass_rate = None

        instruction = str(raw_data.get("user_instruction") or "")
        tags = set(raw_data.get("domain_tags") or [])
        manual_origin = ("origin:vs_code_manual" in tags
                         or "[origin:vs_code_manual]" in instruction)
        manual_mode = ("verification_mode:human_reported" in tags
                       or "[verification_mode:human_reported]" in instruction)
        evidence_match = re.search(r"验证依据[：:]\s*([^\r\n]+)", instruction)
        manual_evidence = bool(evidence_match and evidence_match.group(1).strip())
        human_reported = manual_origin and manual_mode and manual_evidence

        output_quality = 1.0 if len(final_output) >= 20 else 0.3 if final_output else 0.0
        objective_score = raw_data.get("objective_score")
        if (isinstance(objective_score, (int, float)) and not isinstance(objective_score, bool)
                and math.isfinite(objective_score) and 0 <= objective_score <= 1):
            output_quality = float(objective_score)

        success_signal = 1.0 if exec_result.is_success and not exec_result.error_info else 0.0
        test_signal = test_pass_rate if test_pass_rate is not None else 0.0

        validation_score = (
            success_signal * 0.4 +
            test_signal * 0.4 +
            output_quality * 0.2
        )
        validation_score = max(0.0, min(1.0, float(validation_score)))

        validated = (not manual_mode and not invalid_evidence and bool(success_signal)
                     and test_pass_rate == 1.0
                     and validation_score >= self.config["min_validation_score"])
        admissible = validated or (human_reported and not invalid_evidence and bool(success_signal)
                                  and test_pass_rate in (None, 1.0))
        notes = (
            f"{'human_reported' if human_reported else 'auto_verify'}(score={validation_score:.3f}, "
            f"success={success_signal:.2f}, test={test_signal:.2f}, output={output_quality:.2f})"
        )
        if human_reported:
            notes += f"; 验证依据：{evidence_match.group(1).strip()}"
            test_pass_rate = None
        elif invalid_evidence:
            notes += "; invalid_test_evidence"

        return {
            "result_quality_score": validation_score,
            "test_pass_rate": test_pass_rate,
            "solution_validated": validated,
            "validation_notes": notes,
            "admissible": admissible,
            "verification_mode": "human_reported" if human_reported else "objective_tests" if validated else "unverified",
        }
    
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
                resource_cost=raw_data.get("resource_cost", {}),
                result_quality_score=raw_data.get("result_quality_score"),
                test_pass_rate=raw_data.get("test_pass_rate"),
                solution_validated=bool(raw_data.get("solution_validated", False)),
                validation_notes=raw_data.get("validation_notes"),
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
            logger.error("经验抽取失败: %s", str(e))
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
            integrity * 0.05 +
            float(experience.execution_result.result_quality_score or 0.5) * 0.05
        )
        return max(0.0, min(1.0, score))
    
    def add_candidate_experience(self, raw_data: Dict[str, Any], auto_verify: bool = True) -> Optional[str]:
        """添加候选经验，经过质量评估后自动入库"""
        experience = self.extract_experience_from_raw_data(raw_data)
        if not experience:
            return None

        if auto_verify:
            metrics = self._compute_validation_metrics(raw_data, experience)
            experience.execution_result.result_quality_score = metrics["result_quality_score"]
            experience.execution_result.test_pass_rate = metrics["test_pass_rate"]
            experience.execution_result.solution_validated = metrics["solution_validated"]
            experience.execution_result.validation_notes = metrics["validation_notes"]

            if not metrics["admissible"]:
                logger.info(
                    "经验自动验证未通过(score=%.2f，阈值=%.2f)，不予入库",
                    experience.execution_result.result_quality_score or 0.0,
                    self.config["min_validation_score"],
                )
                return None
        else:
            # Explicit storage bypass must not let a caller forge automatic eligibility.
            experience.execution_result.solution_validated = False
            experience.execution_result.validation_notes = "unverified: auto_verify disabled"

        # Quality must be calculated after objective validation so the score
        # reflects measured result quality instead of the legacy 0.5 default.
        quality_score = self.calculate_quality_score(experience)
        if quality_score < self.config["min_quality_score"]:
            logger.info("经验质量分%.2f低于阈值%.2f，不予入库", quality_score, self.config["min_quality_score"])
            return None
        
        # 正式入库
        exp_id = self.graph_ops.add_experience(experience)
        logger.info("经验%s入库成功，质量分: %.2f", exp_id, quality_score)
        return exp_id
    
    def batch_process_raw_data(self, raw_data_list: List[Dict[str, Any]]) -> List[str]:
        """批量处理原始交互数据，抽取经验入库"""
        accepted_experiences: List[ExperienceUnit] = []
        accepted_scores: List[float] = []

        for raw_data in raw_data_list:
            experience = self.extract_experience_from_raw_data(raw_data)
            if not experience:
                continue

            metrics = self._compute_validation_metrics(raw_data, experience)
            experience.execution_result.result_quality_score = metrics["result_quality_score"]
            experience.execution_result.test_pass_rate = metrics["test_pass_rate"]
            experience.execution_result.solution_validated = metrics["solution_validated"]
            experience.execution_result.validation_notes = metrics["validation_notes"]
            if not metrics["admissible"]:
                logger.info("经验自动验证未通过(score=%.2f)，不予入库", metrics["result_quality_score"])
                continue

            quality_score = self.calculate_quality_score(experience)
            if quality_score < self.config["min_quality_score"]:
                logger.info("经验质量分%.2f低于阈值%.2f，不予入库", quality_score, self.config["min_quality_score"])
                continue

            accepted_experiences.append(experience)
            accepted_scores.append(quality_score)

        success_ids = self.graph_ops.add_experiences_batch(accepted_experiences)

        scores_by_id = {exp.experience_id: score for exp, score in zip(accepted_experiences, accepted_scores)}
        for exp_id in success_ids:
            quality_score = scores_by_id[exp_id]
            logger.info("经验%s入库成功，质量分: %.2f", exp_id, quality_score)

        return success_ids
    
    def update_experience_after_use(self, experience_id: str, is_success: bool, benefit: float) -> bool:
        """经验被调用后更新动态属性"""
        return self.graph_ops.update_experience_dynamic_meta(experience_id, is_success, benefit)
    
    def get_outdated_experiences(self) -> List[str]:
        """识别需要淘汰的过期经验"""
        outdated_ids = []
        current_time = datetime.now()
        
        for exp_id, exp in self.graph_ops.graph.experience_nodes.items():
            from .lifecycle_policy import is_active
            if not is_active(exp):
                continue
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
            from .lifecycle_policy import archive
            deleted_ids = []
            for exp_id in outdated_ids:
                experience=self.graph_ops.get_experience(exp_id)
                if experience is not None:
                    archive(experience,reason="Outdated policy soft archive; source retained",decision_id="outdated-policy-v1")
                    deleted_ids.append(exp_id)
            logger.info("已软归档%s条过期经验（物理节点保留）", len(deleted_ids))
            return deleted_ids
        else:
            logger.info("识别到%s条待清理过期经验，需确认后删除", len(outdated_ids))
            return outdated_ids
    
    def calculate_health_score(self) -> Dict[str, Any]:
        """计算经验库健康度得分"""
        from .lifecycle_policy import counts, is_active
        inventory=counts(self.graph_ops.graph)
        active={identifier:exp for identifier,exp in self.graph_ops.graph.experience_nodes.items() if is_active(exp)}
        total_count = len(active)
        if total_count == 0:
            return {
                "total_experiences": inventory["physical_nodes"],
                **inventory,
                "health_scope":"active_nodes_only; success_rate may remain an unmeasured default",
                "health_score": 0.0,
                "metrics": {}
            }
        
        # 计算各项指标
        avg_success_rate = sum(exp.dynamic_meta.success_rate for exp in active.values()) / total_count
        avg_timeliness = sum(exp.dynamic_meta.timeliness for exp in active.values()) / total_count
        
        # 冗余率：参与高相似边(weight>=0.9)的节点比例。相比“全部节点
        # 两两组合中的边比例”，该定义在稀疏图上可解释且不会天然趋近于0。
        redundant_node_ids = set()
        for edge in self.graph_ops.graph.edges.values():
            if edge.edge_type == "similarity" and float(edge.weight) >= 0.9 and edge.from_experience_id in active and edge.to_experience_id in active:
                redundant_node_ids.add(edge.from_experience_id)
                redundant_node_ids.add(edge.to_experience_id)
        redundancy_rate = len(redundant_node_ids) / total_count
        
        # 计算冲突率
        conflict_rate = sum(exp.dynamic_meta.conflict_score for exp in active.values()) / total_count
        
        # 计算调用覆盖率
        used_count = sum(1 for exp in active.values() if exp.dynamic_meta.use_count > 0)
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
            "total_experiences": inventory["physical_nodes"],
            **inventory,
            "health_scope":"active_nodes_only; success_rate may remain an unmeasured default",
            "health_score": round(health_score, 3),
            "metrics": {
                "average_success_rate": round(avg_success_rate, 3),
                "average_timeliness": round(avg_timeliness, 3),
                "redundancy_rate": round(redundancy_rate, 3),
                "redundant_node_count": len(redundant_node_ids),
                "conflict_rate": round(conflict_rate, 3),
                "call_coverage_rate": round(coverage_rate, 3)
            }
        }
    
    def run_health_check(
        self,
        *,
        resolve_conflicts: bool = True,
        generalize_experiences: bool = False,
    ) -> Dict[str, Any]:
        """执行健康检查。

        - 时效性更新：所有节点的 timeliness 重新计算。
        - 冲突消解：相似度高且语义矛盾的经验自动降权 / 下线。
        - 经验泛化（可选，开销较大）：相似簇抽取通用模板写回图。
        """
        self.last_health_check = datetime.now()
        self.graph_ops.update_timeliness()

        conflict_summary: Optional[Dict[str, Any]] = None
        if resolve_conflicts:
            try:
                from .conflict_resolver import detect_and_resolve

                report = detect_and_resolve(self.graph_ops)
                conflict_summary = {
                    "candidate_pairs": len(report.pairs),
                    "cluster_count": report.cluster_count,
                    "retired": report.retired,
                    "downweighted": report.downweighted,
                    "review_count": report.review_count,
                    "already_processed": report.already_processed,
                    "retirement_mode":"soft_archive_preserves_source_nodes",
                }
                if report.actions:
                    logger.info(
                        "ConflictResolver: 处理 %s 个簇，下线 %s 条，降权 %s 条",
                        report.cluster_count, report.retired, report.downweighted,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("冲突消解阶段失败: %s", exc)

        generalization_summary: Optional[Dict[str, Any]] = None
        if generalize_experiences:
            try:
                from .generalizer import generalize

                gen_report = generalize(self.graph_ops)
                generalization_summary = {
                    "cluster_count": len(gen_report.clusters),
                    "template_count": gen_report.template_count,
                    "skipped": gen_report.skipped,
                    "reused": gen_report.reused,
                }
                if gen_report.template_count:
                    logger.info(
                        "ExperienceGeneralizer: 生成 %s 条通用模板（%s 个簇）",
                        gen_report.template_count, len(gen_report.clusters),
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("经验泛化阶段失败: %s", exc)

        health_info = self.calculate_health_score()
        outdated = self.get_outdated_experiences()
        health_info["outdated_experiences_count"] = len(outdated)
        health_info["outdated_experience_ids"] = outdated
        if conflict_summary is not None:
            health_info["conflict_resolution"] = conflict_summary
        if generalization_summary is not None:
            health_info["generalization"] = generalization_summary
        return health_info
    
    def export_experience_library(self, output_path: str) -> bool:
        """Atomically replace a UTF-8 snapshot; failed writes preserve the old file."""
        temporary = None
        try:
            data = self.graph_ops.graph.model_dump_json(indent=2, exclude_none=True)
            destination = Path(output_path).resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n",
                dir=destination.parent, prefix=f".{destination.name}.",
                suffix=".tmp", delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
            logger.info("经验库已导出到: %s", output_path)
            return True
        except Exception as e:
            logger.error("导出经验库失败: %s", str(e))
            return False
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    
    def import_experience_library(self, input_path: str) -> bool:
        """Validate and restore a graph and its search index as one operation."""
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            graph = ExperienceGraph(**data)
            if any(key != node.experience_id for key, node in graph.experience_nodes.items()):
                raise ValueError("snapshot node key/ID mismatch")
            if any(
                key != edge.edge_id
                or edge.from_experience_id not in graph.experience_nodes
                or edge.to_experience_id not in graph.experience_nodes
                for key, edge in graph.edges.items()
            ):
                raise ValueError("snapshot contains invalid edge references")
            for node in graph.experience_nodes.values():
                if "template" in node.constraints and "lifecycle" not in node.context_state.environment_config:
                    # Historical synthesized templates carried unearned success
                    # flags. Migrate live state, preserving the original snapshot.
                    node.context_state.environment_config["lifecycle"]={"state":"pending","migration":"legacy_unexecuted_template"}
                    node.execution_result.is_success=False
                    node.execution_result.solution_validated=False
                    node.execution_result.test_pass_rate=None
                if (
                    "verification_mode:human_reported" in (node.static_meta.domain_tags or [])
                    or "[verification_mode:human_reported]" in (node.task_intent.user_instruction or "")
                    or "human_reported" in (node.execution_result.validation_notes or "")
                ):
                    # Earlier versions promoted manual reports to automatic
                    # validation. Preserve the source snapshot on disk but
                    # restore the honest verification state in the live graph.
                    node.execution_result.solution_validated = False
                    node.execution_result.test_pass_rate = None
                    note = node.execution_result.validation_notes or ""
                    if "restored_human_reported" not in note:
                        node.execution_result.validation_notes = f"restored_human_reported; {note}"
            # Rebuild before swapping: otherwise an imported nonempty library
            # can retain an unfitted or stale TF-IDF vocabulary.
            from sklearn.base import clone
            vectorizer = clone(self.graph_ops.vectorizer)
            if graph.experience_nodes:
                vectorizer.fit([
                    self.graph_ops._exp_text(node)
                    for node in graph.experience_nodes.values()
                ])
            self.graph_ops.graph = graph
            self.graph_ops.vectorizer = vectorizer
            logger.info("经验库导入成功，共%s条经验", len(self.graph_ops.graph.experience_nodes))
            return True
        except Exception as e:
            logger.error("导入经验库失败: %s", str(e))
            return False
