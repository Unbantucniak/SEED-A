#!/usr/bin/env python3
"""
演示脚本 - 展示自学习自演化智能体经验管理系统的核心功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.experience_graph.model import ExperienceUnit, TaskIntent, ContextState, ExecutionResult
from src.experience_graph.operations import GraphOperations
from src.experience_manager.manager import ExperienceManager
from src.routing_engine.routing import RoutingEngine, StrategyType
from datetime import datetime

def demo_basic_usage():
    """演示基础使用方法"""
    print("=" * 60)
    print("🎓 自学习自演化智能体经验管理系统 - 功能演示")
    print("=" * 60)
    
    # 1. 初始化管理器
    print("\n📦 第一步：初始化经验管理器...")
    manager = ExperienceManager()
    print("✅ 经验管理器初始化完成")
    
    # 2. 添加经验示例
    print("\n📝 第二步：添加经验示例...")
    
    sample_experiences = [
        {
            "original_requirement": "实现Python快速排序算法",
            "user_instruction": "写一个快速排序函数",
            "task_type": "代码生成",
            "final_output": "def quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)",
            "is_success": True,
            "execution_time": 0.5,
            "source_credibility": 1.0,
            "domain_tags": ["Python", "算法", "排序"],
            "complexity": 2,
            "generalization": 0.8
        },
        {
            "original_requirement": "修复空列表排序崩溃的bug",
            "user_instruction": "修复排序函数处理空列表时的IndexError",
            "task_type": "bug修复",
            "final_output": "def quicksort(arr):\n    if not arr:  # 添加空列表检查\n        return []\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)",
            "is_success": True,
            "execution_time": 0.3,
            "source_credibility": 1.0,
            "domain_tags": ["Python", "bug修复", "排序"],
            "complexity": 2,
            "generalization": 0.7
        },
        {
            "original_requirement": "实现二分查找算法",
            "user_instruction": "写一个二分查找函数",
            "task_type": "代码生成",
            "final_output": "def binary_search(arr, target):\n    left, right = 0, len(arr) - 1\n    while left <= right:\n        mid = (left + right) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            left = mid + 1\n        else:\n            right = mid - 1\n    return -1",
            "is_success": True,
            "execution_time": 0.4,
            "source_credibility": 0.8,
            "domain_tags": ["Python", "算法", "查找"],
            "complexity": 2,
            "generalization": 0.9
        }
    ]
    
    # 批量添加经验
    exp_ids = manager.batch_process_raw_data(sample_experiences)
    print(f"✅ 成功添加 {len(exp_ids)} 条经验")
    
    # 3. 搜索相关经验
    print("\n🔍 第三步：搜索相关经验...")
    query = "Python排序"
    results = manager.graph_ops.semantic_search(query, top_k=3)
    print(f"查询: '{query}'")
    print(f"找到 {len(results)} 条相关经验:")
    for i, r in enumerate(results, 1):
        exp = r["experience"]
        print(f"  {i}. {exp.task_intent.original_requirement}")
        print(f"     相似度: {r['similarity']:.3f}, 成功率: {exp.dynamic_meta.success_rate:.2f}")
    
    # 4. 经验调用与动态属性更新
    print("\n📈 第四步：模拟经验调用与属性更新...")
    if results:
        exp_id = results[0]["experience_id"]
        # 模拟调用成功
        manager.update_experience_after_use(exp_id, is_success=True, benefit=0.8)
        print(f"✅ 经验 {exp_id} 调用成功，动态属性已更新")
        
        # 再次查询查看更新后的属性
        updated_results = manager.graph_ops.semantic_search(query, top_k=3)
        updated_exp = manager.graph_ops.get_experience(exp_id)
        print(f"   更新后 - 使用次数: {updated_exp.dynamic_meta.use_count}, 成功率: {updated_exp.dynamic_meta.success_rate:.2f}")
    
    # 5. 动态路由演示
    print("\n🎯 第五步：动态路由引擎演示...")
    routing_engine = RoutingEngine(manager.graph_ops)
    
    test_task = {
        "original_requirement": "实现归并排序",
        "user_instruction": "写一个归并排序函数",
        "task_type": "代码生成",
        "complexity": 3,
        "historical_frequency": 5,
        "expected_benefit": 1.0,
        "urgency": 0.5,
        "domain_tags": ["Python", "算法", "排序"]
    }
    
    routing_result = routing_engine.route(test_task)
    print(f"任务: {test_task['original_requirement']}")
    print(f"✅ 推荐策略: {routing_result['selected_strategy']}")
    print("\n各策略得分:")
    for strategy, score in routing_result["strategy_scores"].items():
        print(f"  - {strategy}: {score:.3f}")
    
    # 6. 健康检查
    print("\n🏥 第六步：经验库健康检查...")
    health = manager.run_health_check()
    print(f"经验库总经验数: {health['total_experiences']}")
    print(f"健康度得分: {health['health_score']:.3f}")
    print(f"平均成功率: {health['metrics']['average_success_rate']:.2%}")
    print(f"平均时效性: {health['metrics']['average_timeliness']:.2%}")
    
    print("\n" + "=" * 60)
    print("🎉 演示完成！系统的各项功能均正常运行")
    print("=" * 60)

def demo_advanced_features():
    """演示高级功能"""
    print("\n" + "=" * 60)
    print("🚀 高级功能演示")
    print("=" * 60)
    
    # 1. 增强版经验管理（带LLM-as-Judge）
    print("\n✨ 增强版经验管理 - LLM-as-Judge质量评估")
    try:
        from src.experience_manager.enhanced_manager import EnhancedExperienceManager, LLMasJudge
        
        # 模拟LLM评估器
        def mock_llm_provider(prompt):
            # 实际使用时替换为真实LLM调用
            return '{"correctness": 0.85, "completeness": 0.7, "reusability": 0.8, "safety": 0.95, "efficiency": 0.75, "overall": 0.8, "reasoning": "代码结构良好"}'
        
        judge = LLMasJudge(mock_llm_provider)
        test_exp = {
            "task_intent": {
                "original_requirement": "测试任务",
                "user_instruction": "测试指令",
                "task_type": "代码生成"
            },
            "execution_result": {
                "final_output": "def test(): pass",
                "is_success": True,
                "error_info": None,
                "execution_time": 1.0
            }
        }
        
        result = judge.evaluate(test_exp)
        print(f"LLM评估结果: 综合得分 {result['overall_score']:.2f}")
        print(f"评估来源: {result['source']}")
    except ImportError as e:
        print(f"⚠️ 高级模块暂不可用: {e}")
    
    # 2. 向量嵌入增强
    print("\n🔬 向量嵌入增强 - BGE语义搜索")
    try:
        from src.experience_graph.vector_embedding import VectorEmbedder, HybridVectorStore
        
        graph_ops = GraphOperations()
        manager = ExperienceManager(graph_ops)
        
        # 尝试初始化向量嵌入器
        embedder = VectorEmbedder()
        if embedder.model:
            print(f"✅ BGE向量嵌入模型加载成功: {embedder.model_name}")
            print(f"   向量维度: {embedder.dimension}")
            
            # 演示语义相似度计算
            sim = embedder.compute_similarity("Python排序算法", "实现快速排序")
            print(f"   语义相似度: 'Python排序算法' vs '实现快速排序' = {sim:.3f}")
        else:
            print("⚠️ 向量嵌入模型未安装，使用TF-IDF回退方案")
    except ImportError as e:
        print(f"⚠️ 向量嵌入模块暂不可用: {e}")
    
    # 3. 强化学习路由优化
    print("\n🎓 强化学习路由优化")
    try:
        from src.routing_engine.enhanced_routing import EnhancedRoutingEngine, ReinforcementLearningOptimizer
        
        rl_optimizer = ReinforcementLearningOptimizer()
        print("✅ 强化学习优化器初始化成功")
        
        # 模拟训练步骤
        state = {"complexity": 3, "historical_frequency": 5, "expected_benefit": 1.0, "urgency": 0.5}
        reward = rl_optimizer.train_step(state, 0, True, 1.0, 0.8, 5.0)
        print(f"   模拟训练: 奖励 = {reward:.3f}")
    except ImportError as e:
        print(f"⚠️ 强化学习模块暂不可用: {e}")
    
    print("\n" + "=" * 60)

def main():
    """主函数"""
    print("\n🫧 自学习自演化智能体的经验积累与演化方法研究")
    print("   大学生创新训练项目 - 中山大学\n")
    
    # 基础功能演示
    demo_basic_usage()
    
    # 高级功能演示
    demo_advanced_features()
    
    print("\n📚 更多信息请参阅:")
    print("   - README.md: 项目概述")
    print("   - docs/: 技术设计文档")
    print("   - src/: 核心代码")

if __name__ == "__main__":
    main()
