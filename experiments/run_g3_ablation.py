#!/usr/bin/env python3
"""G3: routing ablation experiments for strategy and weight comparison."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from statistics import mean, stdev
from typing import Any, Dict, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.task_dataset import TaskDataset
from baselines.impl_baselines import Ours_ProposedScheme
from experiment_runner import ExperimentRunner
from path_resolver import resolve_dataset_path, resolve_output_dir
from run_logger import append_run_log


ABLATION_PRESETS: Dict[str, Dict[str, Any]] = {
    "full": {},
    "no_rag": {"disabled_strategies": ["rag_retrieval"]},
    "no_template": {"disabled_strategies": ["template_reuse"]},
    "no_prompt": {"disabled_strategies": ["prompt_engineering"]},
    "no_finetune": {"disabled_strategies": ["fine_tuning"]},
    "speed_priority": {
        "expected_benefit_weight": 0.2,
        "success_probability_weight": 0.2,
        "resource_cost_weight": 0.3,
        "response_speed_weight": 0.3,
    },
    "quality_priority": {
        "expected_benefit_weight": 0.25,
        "success_probability_weight": 0.55,
        "resource_cost_weight": 0.1,
        "response_speed_weight": 0.1,
    },
}


METRIC_KEYS = [
    ("success_rate", True, "Success Rate"),
    ("avg_interaction_rounds", False, "Avg Interaction Rounds"),
    ("avg_token_cost", False, "Avg Token Cost"),
    ("avg_time_cost", False, "Avg Time Cost"),
]

DEFAULT_DATASET_JSON = "./benchmarks/g1_full_120_tasks.json"
DEFAULT_OUTPUT_DIR = "../results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run G3 ablation experiments")
    parser.add_argument("--dataset-json", type=str, default=DEFAULT_DATASET_JSON)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--seeds", type=str, default="11,22,33")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--scenarios",
        type=str,
        default="full,no_rag,no_template,no_prompt,no_finetune,speed_priority,quality_priority",
        help="Comma-separated scenario names",
    )
    return parser.parse_args()


def parse_seed_list(seed_text: str) -> List[int]:
    values = [v.strip() for v in seed_text.split(",") if v.strip()]
    if not values:
        raise ValueError("seeds cannot be empty")

    seeds: List[int] = []
    for value in values:
        try:
            seed = int(value)
        except ValueError as exc:
            raise ValueError(f"Invalid seed value: {value}") from exc
        seeds.append(seed)
    return seeds


def parse_scenarios(scenario_text: str) -> List[str]:
    names = [v.strip() for v in scenario_text.split(",") if v.strip()]
    unknown = [n for n in names if n not in ABLATION_PRESETS]
    if unknown:
        raise ValueError(f"Unknown scenarios: {unknown}")
    return names


def summarize(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "std": 0.0}
    if len(values) == 1:
        return {"mean": values[0], "std": 0.0}
    return {"mean": mean(values), "std": stdev(values)}


def run_single(
    dataset: TaskDataset,
    seed: int,
    rounds: int,
    scenario_name: str,
) -> Dict[str, float]:
    cfg = {
        "seed": seed,
        "simulate_latency": False,
    }
    cfg.update(ABLATION_PRESETS[scenario_name])

    baseline = Ours_ProposedScheme(config=cfg)
    runner = ExperimentRunner(dataset, [baseline])
    result = runner.run_all_experiments(rounds=rounds)
    return result["ours_proposed_scheme"]["metrics"]


def build_report(
    scenario_seed_metrics: Dict[str, Dict[int, Dict[str, float]]],
    scenarios: List[str],
    seeds: List[int],
    dataset_json: str,
    rounds: int,
) -> str:
    lines: List[str] = []
    lines.append("# G3 路由消融实验报告")
    lines.append("")
    lines.append(f"- 数据集: {dataset_json}")
    lines.append(f"- 场景: {scenarios}")
    lines.append(f"- 种子: {seeds}")
    lines.append(f"- 每种子轮次: {rounds}")
    lines.append("")

    for metric_key, _, metric_label in METRIC_KEYS:
        lines.append(f"## {metric_label}")
        lines.append("")
        lines.append("| Scenario | Mean±Std |")
        lines.append("|---|---:|")
        for scenario in scenarios:
            vals = [float(scenario_seed_metrics[scenario][s][metric_key]) for s in seeds]
            summary = summarize(vals)
            lines.append(f"| {scenario} | {summary['mean']:.6f}±{summary['std']:.6f} |")
        lines.append("")

    lines.append("## 结论提示")
    lines.append("")
    lines.append("- 与 full 对比，success_rate 下降越多，说明该组件对效果贡献越大。")
    lines.append("- 对于 avg_interaction_rounds / avg_token_cost / avg_time_cost，数值越低越好。")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if args.rounds <= 0:
        raise ValueError("rounds must be greater than 0")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_json = resolve_dataset_path(args.dataset_json, script_dir, DEFAULT_DATASET_JSON)
    output_dir = resolve_output_dir(args.output_dir, script_dir, DEFAULT_OUTPUT_DIR)

    seeds = parse_seed_list(args.seeds)
    scenarios = parse_scenarios(args.scenarios)

    dataset = TaskDataset.load_from_json(dataset_json)

    scenario_seed_metrics: Dict[str, Dict[int, Dict[str, float]]] = {}
    for scenario in scenarios:
        scenario_seed_metrics[scenario] = {}
        for seed in seeds:
            scenario_seed_metrics[scenario][seed] = run_single(dataset, seed, args.rounds, scenario)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, f"g3_ablation_{stamp}.json")
    md_path = os.path.join(output_dir, f"g3_ablation_{stamp}_report.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "meta": {
                    "dataset_json": dataset_json,
                    "scenarios": scenarios,
                    "seeds": seeds,
                    "rounds_per_seed": args.rounds,
                    "generated_at": datetime.now().isoformat(),
                },
                "metrics": scenario_seed_metrics,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    report_md = build_report(scenario_seed_metrics, scenarios, seeds, dataset_json, args.rounds)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    log_path = append_run_log(
        log_dir=output_dir,
        title="g3_routing_ablation",
        params={
            "rounds": args.rounds,
            "seeds": seeds,
            "scenarios": scenarios,
            "dataset_json": dataset_json,
            "output_dir": output_dir,
        },
        outputs={
            "ablation_json": json_path,
            "ablation_report": md_path,
            "scenario_count": len(scenarios),
        },
    )

    print(f"G3 ablation json: {json_path}")
    print(f"G3 ablation report: {md_path}")
    print(f"G3 run log: {log_path}")


if __name__ == "__main__":
    main()
