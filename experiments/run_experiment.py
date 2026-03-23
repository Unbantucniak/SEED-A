#!/usr/bin/env python3
"""
实验运行入口脚本
"""
import sys
import os
import argparse
import random
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchmarks.task_dataset import TaskDataset
from baselines.impl_baselines import (
    Baseline1_NoExperience,
    Baseline2_OnlyRAG,
    Baseline3_PeriodicFinetune,
    Ours_ProposedScheme
)
from experiment_runner import ExperimentRunner

def parse_args():
    parser = argparse.ArgumentParser(description="运行经验演化项目实验")
    parser.add_argument("--rounds", type=int, default=3, help="实验轮次")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--dataset-json", type=str, default="", help="外部数据集JSON路径")
    parser.add_argument("--simulate-latency", action="store_true", help="启用基线模拟耗时")
    parser.add_argument("--output-dir", type=str, default="./results", help="结果输出目录")
    return parser.parse_args()


def main():
    args = parse_args()
    random.seed(args.seed)

    # 1. 加载数据集
    print("🔧 加载评测数据集...")
    if args.dataset_json:
        dataset = TaskDataset.load_from_json(args.dataset_json)
    else:
        dataset = TaskDataset()
        dataset.load_sample_tasks()
    print(f"✅ 数据集加载完成，共{len(dataset.get_all_tasks())}个任务")
    
    # 2. 初始化所有基线方案
    print("\n🔧 初始化基线方案...")
    baseline_config = {
        "seed": args.seed,
        "simulate_latency": args.simulate_latency,
    }
    baselines = [
        Baseline1_NoExperience(config=baseline_config),
        Baseline2_OnlyRAG(config=baseline_config),
        Baseline3_PeriodicFinetune(config=baseline_config),
        Ours_ProposedScheme(config=baseline_config),
    ]
    print(f"✅ 初始化完成，共{len(baselines)}个对比方案")
    
    # 3. 初始化实验运行器
    runner = ExperimentRunner(dataset, baselines)
    
    # 4. 运行实验
    print("\n🚀 开始运行实验...")
    results = runner.run_all_experiments(rounds=args.rounds)
    
    # 5. 导出结果
    print("\n📊 导出实验结果...")
    result_path = runner.export_results(output_dir=args.output_dir)
    
    # 6. 打印汇总结果
    print("\n🎉 实验完成！结果汇总：")
    print("=" * 80)
    for baseline_name, result in results.items():
        metrics = result["metrics"]
        print(f"\n{baseline_name}:")
        print(f"  成功率: {metrics['success_rate']:.2%}")
        print(f"  平均交互轮次: {metrics['avg_interaction_rounds']:.2f}")
        print(f"  平均耗时: {metrics['avg_time_cost']:.2f}s")
        print(f"  平均Token消耗: {metrics['avg_token_cost']:.0f}")
    print("\n" + "=" * 80)
    print(f"完整结果已保存到: {result_path}")

if __name__ == "__main__":
    main()
