# 自学习自演化智能体的经验积累与演化方法研究
## 中山大学大学生创新训练项目

### 项目概述
针对大模型驱动软件智能体存在的经验遗忘、利用效率低、知识陈旧等问题，研究动态演化的经验积累方法，探索跨模态联合嵌入技术，提升智能体在长周期、跨仓库研发任务中的决策精度与自主性，为构建自学习自演化自主软件智能体提供技术支撑。

### 项目周期：2026年1月 - 2026年11月

### 核心研究内容
1. **智能体经验表示与经验图谱构建**：定义经验单元结构，构建多维元属性评价体系，实现可演化经验图谱
2. **经验获取、利用与自演化机制设计**：实现"生成-筛选-利用-更新"经验闭环，设计动态路由策略，完成经验库自维护机制
3. **原型系统构建与实验验证**：开发VS Code可运行的智能体原型，搭建评测基准，完成多基线对比验证

### 目录结构
```
├── docs/               # 项目文档（文献、技术报告、会议记录）
├── data/               # 数据集（开发交互数据集、标注数据集）
├── src/                # 核心代码
│   ├── experience_graph/   # 经验图谱模块（含向量嵌入）
│   ├── experience_manager/ # 经验全生命周期管理模块（含LLM-as-Judge）
│   ├── routing_engine/     # 动态路由与内化协同模块（含在线学习）
│   ├── monitoring/         # 监控模块（日志、指标、健康检查）
│   └── prototype/          # IDE插件原型系统
├── experiments/        # 实验代码与结果
│   ├── baselines/          # 基线方案实现（含LangChain、AutoGen）
│   ├── benchmarks/         # 评测基准数据集（50+任务）
│   └── results/            # 实验结果记录
└── README.md           # 项目说明文档
```

### 核心创新点

#### 1. 多维元属性评价体系
- 静态属性：来源可信度、领域标签、复杂度、通用性
- 动态属性：成功率、使用次数、平均收益、时效性、冲突度
- 定时更新机制：7天时效性更新、15天冲突度检测

#### 2. 渐进式经验内化机制
- 冷启动：RAG检索
- 验证：高频高成功率经验加入微调候选池
- 训练：定期微调小模型
- 替换：微调模型优先处理同类任务
- 淘汰：RAG库下线已完成内化的经验

#### 3. 动态路由策略
- 4种策略：RAG检索、模板复用、提示工程、小模型微调
- 加权打分模型：预期收益×0.4 + 成功概率×0.3 + 资源开销×0.2 + 响应速度×0.1
- 强化学习优化：DQN/PPO离线训练+在线微调

### 技术增强（2026年3月）

| 模块 | 增强功能 | 文件 |
|------|----------|------|
| 经验图谱 | 向量嵌入 (BGE) | `vector_embedding.py` |
| 路由引擎 | 在线学习、多模态支持 | `enhanced_routing.py` |
| 经验管理 | LLM-as-Judge、分布式支持 | `enhanced_manager.py` |
| 监控系统 | 结构化日志、指标收集、健康检查 | `monitoring/` |
| 实验数据 | 50+评测任务 | `expanded_tasks.json` |
| 新基线 | LangChain Agent、AutoGen | `langchain_agent.py`, `autogen_agent.py` |

### 实验结果

| 方案 | 任务数 | 成功率 | 平均Token消耗 |
|------|--------|--------|---------------|
| 无经验基线 | 4 | 0% | 1410 |
| 仅RAG | 4 | 50% | 638 |
| 周期微调 | 4 | 75% | 539 |
| **本方案** | 4 | **100%** | 1029 |

### 当前进度
✅ 完成项目申请书核心信息提取
✅ 完成项目目录结构搭建
✅ 完成经验单元与元属性体系定义
✅ 完成经验图谱模块开发（测试验证通过）
✅ 完成经验管理闭环模块开发（核心功能验证通过）
✅ 完成动态路由引擎模块开发（测试验证通过）
✅ 完成实验验证体系搭建（含数据集、基线实现、实验框架、结果导出功能）
✅ 完成VS Code IDE原型系统开发（含前后端完整实现）
✅ 完成技术研究报告初稿撰写
✅ 完成技术增强（向量嵌入、在线学习、监控系统）
✅ 完成答辩PPT制作
⬜ 完成结题材料准备

---

### 🎉 项目主体工作已完成！
已完成所有核心交付物：
1. 核心算法模块（经验图谱、经验管理、路由引擎）
2. 完整的实验验证框架（50+任务、4种基线）
3. VS Code插件原型系统
4. 技术研究报告初稿
5. 监控系统模块
6. 答辩PPT

### 演示视频
详见 `docs/` 目录

### 技术栈
- **语言**: Python, TypeScript
- **嵌入模型**: BAAI/bge-base-zh-v1.5
- **LLM**: GPT-4, Claude, MiniMax
- **框架**: LangChain, AutoGen, LangGraph
- **IDE**: VS Code Extension

---

## 🚀 快速开始

### 1. 安装依赖

```bash
# 克隆项目后，进入项目目录
cd 自学习自演化智能体经验管理系统

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 运行演示

```bash
# 运行完整功能演示
python demo.py
```

### 3. 运行测试

```bash
# 运行所有单元测试
python -m pytest tests/ -v

# 或使用 unittest
python -m unittest discover -s tests -v
```

### 4. 运行实验

```bash
cd experiments
python run_experiment.py --rounds 3 --seed 42

# 指定外部数据集JSON
python run_experiment.py --dataset-json ./benchmarks/expanded_tasks.json --rounds 3 --seed 42

# 如需模拟网络/模型延迟，可显式开启
python run_experiment.py --rounds 1 --simulate-latency
```

当 `--rounds > 1` 时，实验报告会自动追加稳定性统计（按轮次成功率均值、标准差、95%置信区间）。

### 5. 查看项目申报书（PDF）文本

```bash
python tools/extract_proposal_pdf.py
# 或限制输出字符数
python tools/extract_proposal_pdf.py --max-chars 6000
```

---

## 📁 项目结构详解

```
├── src/                    # 核心源代码
│   ├── experience_graph/   # 经验图谱模块
│   │   ├── model.py       # 数据模型定义
│   │   ├── operations.py  # 图谱操作接口
│   │   └── vector_embedding.py  # BGE向量嵌入
│   ├── experience_manager/ # 经验管理模块
│   │   ├── manager.py     # 基础管理器
│   │   └── enhanced_manager.py  # 增强版(LLM-as-Judge)
│   ├── routing_engine/    # 动态路由模块
│   │   ├── routing.py     # 基础路由
│   │   └── enhanced_routing.py  # 增强版(RL)
│   ├── monitoring/        # 监控模块
│   │   ├── logger.py     # 日志
│   │   ├── metrics.py    # 指标收集
│   │   └── health_check.py  # 健康检查
│   └── prototype/        # VS Code插件原型
│       ├── backend/      # 后端服务
│       └── src/         # 前端代码
├── experiments/          # 实验验证
│   ├── benchmarks/       # 评测数据集
│   ├── baselines/        # 基线方案
│   └── results/         # 实验结果
├── tests/               # 单元测试
├── docs/                # 技术文档
├── config.toml          # 配置文件（TOML）
├── requirements.txt     # Python依赖
└── demo.py             # 功能演示脚本
```

---

## 🔧 配置说明

项目配置文件为 `config.toml`（TOML 语法）。
核心模块会自动读取以下配置项：

- **经验图谱**: 最大经验数、相似度阈值、嵌入模型选择
- **经验管理**: 质量阈值、淘汰策略、健康检查间隔
- **路由引擎**: 策略权重、强化学习参数、内化条件
- **LLM**: API配置、模型选择
- **缓存**: Redis配置（可选）

### 实验参数模板

项目提供结题推荐参数模板：

- `experiments/experiment_params.template.toml`

可参考模板中的参数运行：

```bash
cd experiments
python run_experiment.py --rounds 5 --seed 42 --dataset-json ./benchmarks/expanded_tasks.json --output-dir ../results
```

---

## 📊 实验结果示例

### 小规模实验（4任务）

| 方案 | 成功率 | 交互轮次 | Token消耗 |
|------|--------|----------|-----------|
| 无经验基线 | 0% | 2.25 | 1410 |
| 仅RAG | 50% | 2.00 | 638 |
| 周期微调 | 75% | 2.25 | 539 |
| **本方案** | **100%** | **2.00** | **1029** |

### 性能提升
- 相比无经验基线：成功率 +100%
- 相比仅RAG：成功率 +100%
- Token消耗相比基线降低：27%

---

## 📖 文档索引

- [技术研究报告](技术研究报告初稿.md)
- [项目交付总览](项目最终交付总览.md)
- [API接口文档](docs/API文档.md)
- [经验单元设计](docs/1-经验单元与元属性体系设计.md)
- [经验管理设计](docs/2-经验管理闭环模块设计.md)
- [路由引擎设计](docs/3-动态路由引擎模块设计.md)
- [实验方案设计](docs/4-实验验证方案设计.md)

---

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

---

**项目负责人**: 中山大学大学生创新训练项目组
**指导教师**: [待填写]
**项目周期**: 2026年1月 - 2026年11月
