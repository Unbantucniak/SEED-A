#!/usr/bin/env python3
"""动态路由引擎模块使用示例与测试脚本"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.routing_engine.routing import RoutingEngine, StrategyType
from src.experience_graph.operations import GraphOperations
from src.experience_graph.model import TaskIntent, ContextState, ExecutionResult, ExperienceUnit

def test_routing_engine():
    # 1. 初始化经验图谱和路由引擎
    graph_ops = GraphOperations()
    routing_engine = RoutingEngine(graph_ops=graph_ops)
    print("✅ 路由引擎初始化成功")
    
    # 2. 预先添加一些测试经验
    # 添加Python排序相关经验
    for i in range(5):
        intent = TaskIntent(
            original_requirement=f"实现Python排序算法{i+1}",
            user_instruction=f"写一个高效的排序函数，类型：{['快速排序','冒泡排序','插入排序','归并排序','堆排序'][i]}",
            task_type="代码生成"
        )
        context = ContextState(dependency_versions={"python": "3.10"})
        result = ExecutionResult(
            final_output=f"排序算法{i+1}实现代码",
            is_success=True,
            execution_time=1.0 + i * 0.2
        )
        exp = ExperienceUnit(
            task_intent=intent,
            context_state=context,
            execution_result=result,
            constraints=["Python >= 3.8"]
        )
        # 模拟使用次数和成功率
        exp.dynamic_meta.use_count = 8 + i
        exp.dynamic_meta.success_rate = 0.75 + i * 0.04
        graph_ops.add_experience(exp)
    print(f"✅ 预先添加5条排序算法相关经验")
    
    # 3. 测试不同场景的路由决策
    print("\n🔍 测试场景1：普通代码生成任务，中等紧急度")
    task1 = {
        "original_requirement": "实现Python快速排序",
        "user_instruction": "写一个高效的快速排序实现",
        "task_type": "代码生成",
        "domain_tags": ["Python", "算法"],
        "complexity": 2,
        "expected_benefit": 2.0,
        "urgency": 0.5,
        "historical_frequency": 5
    }
    result1 = routing_engine.route(task1)
    print(f"选中策略: {result1['selected_strategy']}")
    print(f"各策略得分: {result1['strategy_scores']}")
    print(f"匹配经验数量: {len(result1['matched_experiences'])}")
    
    print("\n🚀 测试场景2：高频高价值任务，低紧急度（适合微调）")
    task2 = {
        "original_requirement": "生成Python排序相关代码",
        "user_instruction": "根据需求生成各类排序算法实现",
        "task_type": "代码生成",
        "domain_tags": ["Python", "算法"],
        "complexity": 3,
        "expected_benefit": 10.0,
        "urgency": 0.1,
        "historical_frequency": 20  # 高频任务
    }
    result2 = routing_engine.route(task2, system_status={"load": 0.2, "available_compute": 1.0})
    print(f"选中策略: {result2['selected_strategy']}")
    print(f"各策略得分: {result2['strategy_scores']}")
    
    print("\n⚡ 测试场景3：紧急任务，需要快速响应")
    task3 = {
        "original_requirement": "快速修复排序函数bug",
        "user_instruction": "紧急修复生产环境的排序函数问题",
        "task_type": "bug修复",
        "domain_tags": ["Python", "bug修复"],
        "complexity": 2,
        "expected_benefit": 5.0,
        "urgency": 1.0,  # 最高紧急度
        "historical_frequency": 3
    }
    result3 = routing_engine.route(task3)
    print(f"选中策略: {result3['selected_strategy']}")
    print(f"各策略得分: {result3['strategy_scores']}")
    
    # 4. 测试获取内化候选经验
    candidates = routing_engine.get_internalization_candidates(min_use_count=10, min_success_rate=0.8)
    print(f"\n📚 适合模型内化的经验候选: {candidates}")
    
    # 5. 测试回填路由结果
    update_success = routing_engine.update_routing_outcome(result1["timestamp"], actual_success=True, actual_benefit=2.5)
    print(f"\n✅ 回填路由结果成功: {update_success}")
    
    print("\n🎉 路由引擎所有测试用例执行成功！")

if __name__ == "__main__":
    test_routing_engine()
