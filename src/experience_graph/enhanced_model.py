"""
增强版经验图谱模块
新增功能：
1. 多模态嵌入支持（代码、文本、结构化数据）
2. 图神经网络推理
3. 时序关系建模
4. 动态图结构
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union
from uuid import uuid4
from datetime import datetime
from enum import Enum
import hashlib
import numpy as np


class TaskIntent(BaseModel):
    """任务意图信息"""
    original_requirement: str
    user_instruction: str
    task_type: str
    # 新增：多模态任务描述
    code_snippet: Optional[str] = None
    error_trace: Optional[str] = None
    expected_output: Optional[str] = None


class ContextState(BaseModel):
    """上下文状态信息"""
    repo_snapshot: Optional[str] = None
    dependency_versions: Dict[str, str] = Field(default_factory=dict)
    environment_config: Dict[str, Any] = Field(default_factory=dict)
    history_context: List[Dict[str, Any]] = Field(default_factory=list)
    # 新增：代码结构信息
    file_structure: Optional[Dict[str, Any]] = None
    git_diff: Optional[str] = None


class OperationStep(BaseModel):
    """操作序列中的单步动作"""
    action_type: str
    input_params: Dict[str, Any] = Field(default_factory=dict)
    output_result: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    # 新增：动作元数据
    tool_name: Optional[str] = None
    duration_ms: Optional[float] = None
    tokens_consumed: Optional[int] = None


class ExecutionResult(BaseModel):
    """执行结果信息"""
    final_output: str
    is_success: bool
    error_info: Optional[str] = None
    user_feedback: Optional[str] = None
    execution_time: float
    resource_cost: Dict[str, float] = Field(default_factory=dict)
    # 新增：结果质量指标
    code_quality_score: Optional[float] = None
    test_pass_rate: Optional[float] = None
    security_scan_result: Optional[Dict[str, Any]] = None


class StaticMetaAttribute(BaseModel):
    """静态元属性"""
    source_credibility: float = Field(ge=0, le=1, default=0.5)
    domain_tags: List[str] = Field(default_factory=list)
    complexity: int = Field(ge=1, le=5, default=3)
    generalization: float = Field(ge=0, le=1, default=0.5)
    # 新增：扩展属性
    programming_language: Optional[str] = None
    framework_tags: List[str] = Field(default_factory=list)
    api_dependencies: List[str] = Field(default_factory=list)
    code_complexity_metrics: Optional[Dict[str, float]] = None


class DynamicMetaAttribute(BaseModel):
    """动态元属性"""
    success_rate: float = Field(ge=0, le=1, default=0.5)
    use_count: int = Field(ge=0, default=0)
    average_benefit: float = Field(ge=0, default=0.0)
    timeliness: float = Field(ge=0, le=1, default=1.0)
    conflict_score: float = Field(ge=0, le=1, default=0.0)
    # 新增：时序属性
    first_created_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    consecutive_failures: int = 0
    decay_factor: float = 0.95


class EmbeddingType(str, Enum):
    """嵌入类型枚举"""
    SEMANTIC = "semantic"           # 语义嵌入
    CODE = "code"                   # 代码嵌入
    STRUCTURAL = "structural"       # 结构嵌入
    TEMPORAL = "temporal"           # 时序嵌入
    HYBRID = "hybrid"               # 混合嵌入


class MultiModalEmbedding(BaseModel):
    """多模态嵌入表示"""
    experience_id: str
    embedding_type: EmbeddingType
    vector: List[float]
    dimension: int
    model_name: str
    created_at: datetime = Field(default_factory=datetime.now)


class ExperienceUnit(BaseModel):
    """经验单元核心结构（增强版）"""
    experience_id: str = Field(default_factory=lambda: str(uuid4()))
    task_intent: TaskIntent
    context_state: ContextState
    operation_sequence: List[OperationStep] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    execution_result: ExecutionResult
    static_meta: StaticMetaAttribute = Field(default_factory=StaticMetaAttribute)
    dynamic_meta: DynamicMetaAttribute = Field(default_factory=DynamicMetaAttribute)
    created_at: datetime = Field(default_factory=datetime.now)
    last_used_at: datetime = Field(default_factory=datetime.now)
    
    # 新增：版本控制
    version: str = "2.0"
    parent_experience_id: Optional[str] = None
    lineage: List[str] = Field(default_factory=list)
    
    # 新增：嵌入缓存
    embeddings: Dict[str, List[float]] = Field(default_factory=dict)
    
    def get_text_representation(self) -> str:
        """获取经验的文本表示（用于嵌入）"""
        parts = [
            self.task_intent.original_requirement,
            self.task_intent.user_instruction,
            self.task_intent.task_type,
            " ".join(self.static_meta.domain_tags),
            self.execution_result.final_output[:500] if self.execution_result.final_output else ""
        ]
        return " ".join(filter(None, parts))
    
    def get_code_representation(self) -> str:
        """获取经验的代码表示（用于代码嵌入）"""
        code_parts = []
        for op in self.operation_sequence:
            if op.action_type in ["code_generation", "code_edit", "code_refactor"]:
                code_parts.append(str(op.output_result.get("code", "")))
        return "\n".join(code_parts)
    
    def compute_content_hash(self) -> str:
        """计算内容哈希（用于去重）"""
        content = self.get_text_representation()
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class ExperienceEdge(BaseModel):
    """经验图谱边结构（增强版）"""
    edge_id: str = Field(default_factory=lambda: str(uuid4()))
    from_experience_id: str
    to_experience_id: str
    edge_type: str
    weight: float = Field(ge=0, le=1, default=0.5)
    confidence: float = Field(ge=0, le=1, default=1.0)  # 边置信度
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    # 新增：时序属性
    temporal_span_days: Optional[int] = None
    causality_strength: Optional[float] = None


class TemporalRelation(BaseModel):
    """时序关系"""
    relation_id: str = Field(default_factory=lambda: str(uuid4()))
    earlier_experience_id: str
    later_experience_id: str
    temporal_distance_hours: float
    evolution_type: str  # improvement, degradation, parallel


class ExperienceGraph(BaseModel):
    """经验图谱结构（增强版）"""
    graph_id: str = Field(default_factory=lambda: str(uuid4()))
    experience_nodes: Dict[str, ExperienceUnit] = Field(default_factory=dict)
    edges: Dict[str, ExperienceEdge] = Field(default_factory=dict)
    temporal_relations: List[TemporalRelation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # 新增：图统计信息
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        if not self.experience_nodes:
            return {"total_experiences": 0}
        
        success_count = sum(1 for e in self.experience_nodes.values() if e.execution_result.is_success)
        avg_use_count = sum(e.dynamic_meta.use_count for e in self.experience_nodes.values()) / len(self.experience_nodes)
        
        return {
            "total_experiences": len(self.experience_nodes),
            "total_edges": len(self.edges),
            "success_rate": success_count / len(self.experience_nodes),
            "average_use_count": avg_use_count,
            "temporal_relations_count": len(self.temporal_relations),
            "domain_distribution": self._get_domain_distribution()
        }
    
    def _get_domain_distribution(self) -> Dict[str, int]:
        """获取领域分布"""
        distribution = {}
        for exp in self.experience_nodes.values():
            for tag in exp.static_meta.domain_tags:
                distribution[tag] = distribution.get(tag, 0) + 1
        return distribution
