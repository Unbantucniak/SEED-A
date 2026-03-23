#!/usr/bin/env python3
"""
实验运行入口脚本
"""
import sys
import os
import argparse
import random
import logging
from logging.handlers import RotatingFileHandler
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchmarks.task_dataset import TaskDataset
from baselines.impl_baselines import (
    Baseline1_NoExperience,
    Baseline2_OnlyRAG,
    Baseline3_PeriodicFinetune,
    Ours_ProposedScheme
)
from experiment_runner import ExperimentRunner
from run_logger import append_run_log
from src.common.config import get_config_section


logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="运行经验演化项目实验")
    parser.add_argument("--rounds", type=int, default=3, help="实验轮次")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--dataset-json", type=str, default="", help="外部数据集JSON路径")
    parser.add_argument("--simulate-latency", action="store_true", help="启用基线模拟耗时")
    parser.add_argument("--output-dir", type=str, default="./results", help="结果输出目录")
    parser.add_argument("--log-level", type=str, default="", help="日志级别覆盖（DEBUG/INFO/WARNING/ERROR）")
    return parser.parse_args()


def setup_logging(log_level_override: str = "") -> None:
    logging_cfg = get_config_section("logging")
    level_name = (log_level_override or str(logging_cfg.get("level", "INFO"))).upper()
    level = getattr(logging, level_name, logging.INFO)
    log_format = str(logging_cfg.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    handlers = [logging.StreamHandler()]

    log_file = str(logging_cfg.get("file", "")).strip()
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        max_file_size_mb = int(logging_cfg.get("max_file_size", 10))
        backup_count = int(logging_cfg.get("backup_count", 5))
        handlers.append(
            RotatingFileHandler(
                log_file,
                maxBytes=max(1, max_file_size_mb) * 1024 * 1024,
                backupCount=max(0, backup_count),
                encoding="utf-8",
            )
        )

    logging.basicConfig(level=level, format=log_format, handlers=handlers, force=True)


def main():
    args = parse_args()
    setup_logging(args.log_level)
    random.seed(args.seed)

    # 1. 加载数据集
    logger.info("加载评测数据集...")
    if args.dataset_json:
        dataset = TaskDataset.load_from_json(args.dataset_json)
    else:
        dataset = TaskDataset()
        dataset.load_sample_tasks()
    logger.info("数据集加载完成，共%s个任务", len(dataset.get_all_tasks()))
    
    # 2. 初始化所有基线方案
    logger.info("初始化基线方案...")
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
    logger.info("初始化完成，共%s个对比方案", len(baselines))
    
    # 3. 初始化实验运行器
    runner = ExperimentRunner(dataset, baselines)
    
    # 4. 运行实验
    logger.info("开始运行实验...")
    results = runner.run_all_experiments(rounds=args.rounds)
    
    # 5. 导出结果
    logger.info("导出实验结果...")
    result_path = runner.export_results(output_dir=args.output_dir)
    
    # 6. 打印汇总结果
    logger.info("实验完成！结果汇总：")
    logger.info("%s", "=" * 80)
    for baseline_name, result in results.items():
        metrics = result["metrics"]
        logger.info("%s:", baseline_name)
        logger.info("  成功率: %.2f%%", metrics["success_rate"] * 100)
        logger.info("  平均交互轮次: %.2f", metrics["avg_interaction_rounds"])
        logger.info("  平均耗时: %.2fs", metrics["avg_time_cost"])
        logger.info("  平均Token消耗: %.0f", metrics["avg_token_cost"])
    logger.info("%s", "=" * 80)
    logger.info("完整结果已保存到: %s", result_path)

    report_path = result_path.replace(".json", "_report.md")
    run_log = append_run_log(
        log_dir=os.path.abspath(args.output_dir),
        title="baseline_comparison",
        params={
            "rounds": args.rounds,
            "seed": args.seed,
            "dataset_json": args.dataset_json or "sample_tasks",
            "simulate_latency": args.simulate_latency,
            "output_dir": os.path.abspath(args.output_dir),
        },
        outputs={
            "result_json": result_path,
            "result_report": report_path,
            "baseline_metrics": {name: data["metrics"] for name, data in results.items()},
        },
    )
    logger.info("实验记录已追加到: %s", run_log)

if __name__ == "__main__":
    main()
