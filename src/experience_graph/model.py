from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from uuid import uuid4
from datetime import datetime

class TaskIntent(BaseModel):
    """任务意图信息"""
    original_requirement: str
    user_instruction: str
    task_type: str  # 需求澄清/代码生成/调试修复/评审优化等

class ContextState(BaseModel):
    """上下文状态信息"""
    repo_snapshot: Optional[str] = None
    dependency_versions: Dict[str, str] = Field(default_factory=dict)
    environment_config: Dict[str, Any] = Field(default_factory=dict)
    history_context: List[Dict[str, Any]] = Field(default_factory=list)

class OperationStep(BaseModel):
    """操作序列中的单步动作"""
    action_type: str  # 工具调用/代码修改/指令输出等
    input_params: Dict[str, Any] = Field(default_factory=dict)
    output_result: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

class ExecutionResult(BaseModel):
    """执行结果信息"""
    final_output: str
    is_success: bool
    error_info: Optional[str] = None
    user_feedback: Optional[str] = None
    execution_time: float  # 执行耗时，单位秒
    resource_cost: Dict[str, float] = Field(default_factory=dict)

class StaticMetaAttribute(BaseModel):
    """静态元属性"""
    source_credibility: float = Field(ge=0, le=1, default=0.5)
    domain_tags: List[str] = Field(default_factory=list)
    complexity: int = Field(ge=1, le=5, default=3)
    generalization: float = Field(ge=0, le=1, default=0.5)

class DynamicMetaAttribute(BaseModel):
    """动态元属性"""
    success_rate: float = Field(ge=0, le=1, default=0.5)
    use_count: int = Field(ge=0, default=0)
    average_benefit: float = Field(ge=0, default=0.0)
    timeliness: float = Field(ge=0, le=1, default=1.0)
    conflict_score: float = Field(ge=0, le=1, default=0.0)

class ExperienceUnit(BaseModel):
    """经验单元核心结构"""
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

class ExperienceEdge(BaseModel):
    """经验图谱边结构"""
    edge_id: str = Field(default_factory=lambda: str(uuid4()))
    from_experience_id: str
    to_experience_id: str
    edge_type: str  # dependency/similarity/causality/derivation
    weight: float = Field(ge=0, le=1, default=0.5)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class ExperienceGraph(BaseModel):
    """经验图谱结构"""
    graph_id: str = Field(default_factory=lambda: str(uuid4()))
    experience_nodes: Dict[str, ExperienceUnit] = Field(default_factory=dict)
    edges: Dict[str, ExperienceEdge] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
