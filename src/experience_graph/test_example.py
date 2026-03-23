#!/usr/bin/env python3
"""经验图谱模块使用示例与测试脚本"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.experience_graph.model import TaskIntent, ContextState, ExecutionResult, ExperienceUnit
from src.experience_graph.operations import GraphOperations

def test_experience_graph():
    # 1. 初始化经验图谱
    graph_ops = GraphOperations()
    print("✅ 经验图谱初始化成功")
    
    # 2. 创建测试经验单元1：Python代码生成任务
    intent1 = TaskIntent(
        original_requirement="需要写一个Python函数实现快速排序",
        user_instruction="写一个高效的快速排序实现，支持整数列表排序",
        task_type="代码生成"
    )
    context1 = ContextState(
        dependency_versions={"python": "3.10"},
        environment_config={"os": "Linux"}
    )
    result1 = ExecutionResult(
        final_output="def quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr)//2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)",
        is_success=True,
        execution_time=1.2,
        user_feedback="代码正确，符合要求"
    )
    exp1 = ExperienceUnit(
        task_intent=intent1,
        context_state=context1,
        execution_result=result1,
        constraints=["Python >= 3.8"]
    )
    exp1_id = graph_ops.add_experience(exp1)
    print(f"✅ 添加经验1成功，ID: {exp1_id}")
    
    # 3. 创建测试经验单元2：Python排序优化任务
    intent2 = TaskIntent(
        original_requirement="优化现有的排序函数，提升大数据量下的性能",
        user_instruction="优化快速排序函数，处理10万条以上数据时性能提升30%",
        task_type="代码优化"
    )
    context2 = ContextState(
        dependency_versions={"python": "3.10"},
        environment_config={"os": "Linux"}
    )
    result2 = ExecutionResult(
        final_output="优化后的快速排序代码，引入尾递归优化和插入排序 fallback",
        is_success=True,
        execution_time=3.5,
        user_feedback="性能提升符合预期"
    )
    exp2 = ExperienceUnit(
        task_intent=intent2,
        context_state=context2,
        execution_result=result2,
        constraints=["Python >= 3.8"]
    )
    exp2_id = graph_ops.add_experience(exp2)
    print(f"✅ 添加经验2成功，ID: {exp2_id}")
    
    # 4. 添加依赖关系边：经验2依赖经验1
    edge_id = graph_ops.add_edge(exp1_id, exp2_id, "dependency", 0.9)
    print(f"✅ 添加依赖边成功，ID: {edge_id}")
    
    # 5. 测试语义搜索
    query = "如何实现Python快速排序"
    results = graph_ops.semantic_search(query, top_k=2)
    print(f"\n🔍 语义搜索结果（查询：'{query}'）：")
    for res in results:
        print(f"经验ID: {res['experience_id']}, 综合得分: {res['composite_score']:.3f}, 任务类型: {res['experience'].task_intent.task_type}")
    
    # 6. 测试更新动态元属性
    update_success = graph_ops.update_experience_dynamic_meta(exp1_id, is_success=True, benefit=2.5)
    print(f"\n✅ 更新经验1动态属性成功: {update_success}")
    exp1_updated = graph_ops.get_experience(exp1_id)
    print(f"经验1更新后: 成功率={exp1_updated.dynamic_meta.success_rate}, 使用次数={exp1_updated.dynamic_meta.use_count}, 平均收益={exp1_updated.dynamic_meta.average_benefit}")
    
    # 7. 测试获取关联经验
    related = graph_ops.get_related_experiences(exp1_id, edge_types=["dependency"])
    print(f"\n🔗 经验1的关联经验: {related}")
    
    # 8. 测试时效性更新
    graph_ops.update_timeliness()
    print("\n✅ 批量更新时效性完成")
    
    print("\n🎉 所有测试用例执行成功！")

if __name__ == "__main__":
    test_experience_graph()
