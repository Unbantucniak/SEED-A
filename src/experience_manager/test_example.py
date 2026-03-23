#!/usr/bin/env python3
"""经验管理模块使用示例与测试脚本"""
import sys
import os
import tempfile
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.experience_manager.manager import ExperienceManager

def test_experience_manager():
    # 1. 初始化经验管理器
    manager = ExperienceManager()
    print("✅ 经验管理器初始化成功")
    
    # 2. 准备测试原始交互数据
    raw_data1 = {
        "original_requirement": "需要写一个Python函数实现冒泡排序",
        "user_instruction": "写一个冒泡排序函数，支持升序和降序",
        "task_type": "代码生成",
        "dependency_versions": {"python": "3.10"},
        "environment_config": {"os": "Linux"},
        "operation_sequence": [
            {
                "action_type": "代码生成",
                "input_params": {"language": "Python", "algorithm": "冒泡排序"},
                "output_result": {"code": "def bubble_sort(arr, reverse=False):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n-i-1):\n            if reverse:\n                if arr[j] < arr[j+1]:\n                    arr[j], arr[j+1] = arr[j+1], arr[j]\n            else:\n                if arr[j] > arr[j+1]:\n                    arr[j], arr[j+1] = arr[j+1], arr[j]\n    return arr"}
            }
        ],
        "final_output": "def bubble_sort(arr, reverse=False):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n-i-1):\n            if reverse:\n                if arr[j] < arr[j+1]:\n                    arr[j], arr[j+1] = arr[j+1], arr[j]\n            else:\n                if arr[j] > arr[j+1]:\n                    arr[j], arr[j+1] = arr[j+1], arr[j]\n    return arr",
        "is_success": True,
        "execution_time": 0.8,
        "user_feedback": "代码正确，支持升降序",
        "source_credibility": 0.9,
        "domain_tags": ["Python", "算法", "排序"],
        "generalization": 0.8
    }
    
    raw_data2 = {
        "original_requirement": "修复冒泡排序函数的边界问题",
        "user_instruction": "修复空列表和单元素列表的处理",
        "task_type": "bug修复",
        "dependency_versions": {"python": "3.10"},
        "execution_result": {"is_success": True},
        "final_output": "修复后的冒泡排序代码，增加边界判断",
        "is_success": True,
        "execution_time": 1.2,
        "source_credibility": 0.8,
        "domain_tags": ["Python", "bug修复", "排序"],
        "generalization": 0.6
    }
    
    # 3. 测试批量添加经验
    exp_ids = manager.batch_process_raw_data([raw_data1, raw_data2])
    print(f"✅ 批量添加经验成功，共入库{len(exp_ids)}条: {exp_ids}")
    
    # 4. 测试经验调用后更新
    if exp_ids:
        update_success = manager.update_experience_after_use(exp_ids[0], is_success=True, benefit=1.8)
        print(f"✅ 更新经验调用结果成功: {update_success}")
    
    # 5. 测试健康检查
    health_info = manager.run_health_check()
    print(f"\n🏥 经验库健康检查结果:")
    print(f"总经验数: {health_info['total_experiences']}")
    print(f"健康度得分: {health_info['health_score']}")
    print(f"各项指标: {health_info['metrics']}")
    print(f"过期经验数: {health_info['outdated_experiences_count']}")
    
    # 6. 测试经验库导出导入
    export_path = os.path.join(tempfile.gettempdir(), "test_experience_library.json")
    export_success = manager.export_experience_library(export_path)
    print(f"\n✅ 经验库导出成功: {export_success}, 路径: {export_path}")
    
    # 新建管理器导入
    new_manager = ExperienceManager()
    import_success = new_manager.import_experience_library(export_path)
    print(f"✅ 经验库导入成功: {import_success}, 导入经验数: {len(new_manager.graph_ops.graph.experience_nodes)}")
    
    # 7. 测试过期经验清理
    outdated = manager.clean_outdated_experiences(auto_delete=False)
    print(f"\n🗑️ 待清理过期经验: {outdated}")
    
    print("\n🎉 所有测试用例执行成功！")

if __name__ == "__main__":
    test_experience_manager()
