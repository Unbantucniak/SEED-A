# API Reference
# 自学习自演化智能体经验管理系统 - 编程接口文档

---

## 1. 经验图谱模块 (experience_graph)

### 1.1 数据模型

#### TaskIntent
任务意图信息
```python
task_intent = TaskIntent(
    original_requirement: str,  # 原始需求
    user_instruction: str,       # 用户指令
    task_type: str               # 任务类型
)
```

#### ContextState
上下文状态信息
```python
context_state = ContextState(
    repo_snapshot: Optional[str],           # 仓库快照
    dependency_versions: Dict[str, str],    # 依赖版本
    environment_config: Dict[str, Any],      # 环境配置
    history_context: List[Dict[str, Any]]   # 历史上下文
)
```

#### ExecutionResult
执行结果信息
```python
execution_result = ExecutionResult(
    final_output: str,              # 最终输出
    is_success: bool,               # 是否成功
    error_info: Optional[str],      # 错误信息
    user_feedback: Optional[str],   # 用户反馈
    execution_time: float           # 执行耗时(秒)
)
```

#### ExperienceUnit
经验单元核心结构
```python
experience = ExperienceUnit(
    experience_id: str,             # 经验ID (自动生成)
    task_intent: TaskIntent,       # 任务意图
    context_state: ContextState,   # 上下文状态
    operation_sequence: List[OperationStep],  # 操作序列
    constraints: List[str],        # 环境约束
    execution_result: ExecutionResult,  # 执行结果
    static_meta: StaticMetaAttribute,   # 静态元属性
    dynamic_meta: DynamicMetaAttribute, # 动态元属性
    created_at: datetime,          # 创建时间
    last_used_at: datetime         # 最后使用时间
)
```

---

### 1.2 GraphOperations - 图谱操作类

#### 初始化
```python
from src.experience_graph.operations import GraphOperations

graph_ops = GraphOperations()
# 或传入已有图谱
graph_ops = GraphOperations(existing_graph)
```

#### 核心方法

##### add_experience
添加经验节点
```python
exp_id = graph_ops.add_experience(experience: ExperienceUnit) -> str
```

##### get_experience
获取经验节点
```python
exp = graph_ops.get_experience(experience_id: str) -> Optional[ExperienceUnit]
```

##### semantic_search
语义搜索相关经验
```python
results = graph_ops.semantic_search(
    query: str,        # 查询文本
    top_k: int = 5     # 返回结果数量
) -> List[Dict]       # 返回结果列表
```

##### update_experience_dynamic_meta
更新经验动态元属性
```python
success = graph_ops.update_experience_dynamic_meta(
    experience_id: str,
    is_success: bool,
    benefit: float
) -> bool
```

##### delete_experience
删除经验节点
```python
success = graph_ops.delete_experience(experience_id: str) -> bool
```

##### add_edge
添加边
```python
edge_id = graph_ops.add_edge(
    from_id: str,
    to_id: str,
    edge_type: str,    # dependency/similarity/causality/derivation
    weight: float = 0.5
) -> Optional[str]
```

##### get_related_experiences
获取关联经验
```python
related = graph_ops.get_related_experiences(
    experience_id: str,
    edge_types: Optional[List[str]] = None
) -> List[Dict]
```

---

## 2. 经验管理模块 (experience_manager)

### 2.1 ExperienceManager - 经验全生命周期管理类

#### 初始化
```python
from src.experience_manager.manager import ExperienceManager

manager = ExperienceManager()
# 或传入已有的graph_ops
manager = ExperienceManager(graph_ops)
```

#### 核心方法

##### add_candidate_experience
添加候选经验（带质量评估）
```python
exp_id = manager.add_candidate_experience(
    raw_data: Dict[str, Any],
    auto_verify: bool = True
) -> Optional[str]
```

##### batch_process_raw_data
批量处理原始数据
```python
success_ids = manager.batch_process_raw_data(
    raw_data_list: List[Dict[str, Any]]
) -> List[str]
```

##### update_experience_after_use
经验调用后更新动态属性
```python
success = manager.update_experience_after_use(
    experience_id: str,
    is_success: bool,
    benefit: float
) -> bool
```

##### get_outdated_experiences
获取过期经验列表
```python
outdated_ids = manager.get_outdated_experiences() -> List[str]
```

##### clean_outdated_experiences
清理过期经验
```python
deleted_ids = manager.clean_outdated_experiences(
    auto_delete: bool = False
) -> List[str]
```

##### calculate_health_score
计算经验库健康度
```python
health = manager.calculate_health_score() -> Dict[str, Any]
```

##### run_health_check
执行健康检查
```python
health_info = manager.run_health_check() -> Dict[str, Any]
```

##### export_experience_library
导出经验库
```python
success = manager.export_experience_library(
    output_path: str
) -> bool
```

##### import_experience_library
导入经验库
```python
success = manager.import_experience_library(
    input_path: str
) -> bool
```

---

## 3. 路由引擎模块 (routing_engine)

### 3.1 RoutingEngine - 动态路由引擎类

#### 初始化
```python
from src.routing_engine.routing import RoutingEngine

routing_engine = RoutingEngine()
# 或传入已有的graph_ops
routing_engine = RoutingEngine(graph_ops)
```

#### 核心方法

##### route
路由决策
```python
result = routing_engine.route(
    task_info: Dict[str, Any],
    system_status: Optional[Dict[str, Any]] = None,
    top_k_experiences: int = 5
) -> Dict[str, Any]
```

##### get_matched_experiences
获取匹配经验
```python
matches = routing_engine.get_matched_experiences(
    task_info: Dict[str, Any],
    top_k: int = 10
) -> List[Dict]
```

##### get_internalization_candidates
获取适合内化的经验候选
```python
candidates = routing_engine.get_internalization_candidates(
    min_use_count: int = 10,
    min_success_rate: float = 0.8
) -> List[str]
```

---

## 4. 增强模块 (enhanced_*)

### 4.1 VectorEmbedder - 向量嵌入器

```python
from src.experience_graph.vector_embedding import VectorEmbedder

embedder = VectorEmbedder(model_name="BAAI/bge-base-zh-v1.5")

# 编码文本
embeddings = embedder.encode(texts: List[str]) -> np.ndarray

# 计算相似度
similarity = embedder.compute_similarity(text1: str, text2: str) -> float
```

### 4.2 LLMasJudge - LLM质量评估器

```python
from src.experience_manager.enhanced_manager import LLMasJudge

# 定义LLM提供者
def llm_provider(prompt: str) -> str:
    # 调用LLM并返回JSON字符串
    return response

judge = LLMasJudge(llm_provider=llm_provider)
result = judge.evaluate(experience_data: Dict) -> Dict
```

### 4.3 EnhancedExperienceManager - 增强版经验管理器

```python
from src.experience_manager.enhanced_manager import EnhancedExperienceManager

enhanced_manager = EnhancedExperienceManager(
    use_llm_judge=True,
    llm_provider=llm_provider,
    redis_url="redis://localhost:6379/0"
)

# 添加经验（带验证）
exp_id = enhanced_manager.add_experience_with_validation(raw_data)
```

### 4.4 EnhancedRoutingEngine - 增强版路由引擎

```python
from src.routing_engine.enhanced_routing import EnhancedRoutingEngine

enhanced_routing = EnhancedRoutingEngine(use_rl=True)

# 路由决策
result = enhanced_routing.route(task_info, use_rl=True)

# 根据结果更新模型
enhanced_routing.update_with_outcome(
    routing_result=result,
    actual_success=True,
    actual_benefit=0.8,
    response_time=5.0
)
```

---

## 5. 实验模块 (experiments)

### 5.1 TaskDataset - 评测数据集

```python
from experiments.benchmarks.task_dataset import TaskDataset

dataset = TaskDataset()
dataset.load_sample_tasks()
tasks = dataset.get_all_tasks()
```

### 5.2 ExperimentRunner - 实验运行器

```python
from experiments.experiment_runner import ExperimentRunner

runner = ExperimentRunner(dataset, baselines)
results = runner.run_all_experiments(rounds=1)
runner.export_results(output_dir="./results")
```

---

## 数据格式参考

### 原始经验数据格式
```python
raw_data = {
    "original_requirement": "实现快速排序",
    "user_instruction": "写一个快速排序函数",
    "task_type": "代码生成",
    "final_output": "def quicksort(arr): ...",
    "is_success": True,
    "execution_time": 0.5,
    "source_credibility": 0.8,
    "domain_tags": ["Python", "算法"],
    "complexity": 2,
    "generalization": 0.8
}
```

### 任务信息格式
```python
task_info = {
    "original_requirement": "实现归并排序",
    "user_instruction": "写归并排序代码",
    "task_type": "代码生成",
    "domain_tags": ["Python", "算法"],
    "complexity": 3,
    "historical_frequency": 5,
    "expected_benefit": 1.0,
    "urgency": 0.5
}
```
