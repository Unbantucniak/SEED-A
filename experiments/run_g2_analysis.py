#!/usr/bin/env python3
"""G2: multi-seed statistical test and effect size analysis."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime
from statistics import mean, stdev
from typing import Any, Dict, List, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.task_dataset import TaskDataset
from baselines.impl_baselines import (
    Baseline1_NoExperience,
    Baseline2_OnlyRAG,
    Baseline3_PeriodicFinetune,
    Ours_ProposedScheme,
)
from experiment_runner import ExperimentRunner
from build_g1_dataset import build_dataset
from path_resolver import resolve_dataset_path, resolve_output_dir
from run_logger import append_run_log


DEFAULT_DATASET_JSON = "./benchmarks/g1_full_120_tasks.json"
DEFAULT_OUTPUT_DIR = "../results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run G2 multi-seed statistical analysis")
    parser.add_argument("--rounds", type=int, default=1, help="Rounds per seed")
    parser.add_argument(
        "--seeds",
        type=str,
        default="11,22,33,44,55",
        help="Comma-separated seeds, e.g. 11,22,33,44,55",
    )
    parser.add_argument(
        "--dataset-json",
        type=str,
        default=DEFAULT_DATASET_JSON,
        help="Dataset path used for multi-seed runs",
    )
    parser.add_argument("--target-count", type=int, default=120, help="Build dataset size if missing")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--target-success-ci", type=float, default=0.0, help="Adaptive stop when ours success_rate CI half-width <= target (>0 to enable)")
    parser.add_argument("--max-seeds", type=int, default=0, help="Maximum seeds to run in adaptive mode (0 means no limit)")
    parser.add_argument("--log-level", type=str, default="WARNING", help="Reserved for compatibility")
    return parser.parse_args()


def _validate_args(args: argparse.Namespace) -> None:
    if args.rounds <= 0:
        raise ValueError("rounds must be greater than 0")
    if args.target_count <= 0:
        raise ValueError("target_count must be greater than 0")
    if args.target_success_ci < 0:
        raise ValueError("target_success_ci must be >= 0")
    if args.max_seeds < 0:
        raise ValueError("max_seeds must be >= 0")


def _parse_seed_list(seed_text: str) -> List[int]:
    values = [s.strip() for s in seed_text.split(",") if s.strip()]
    if not values:
        raise ValueError("seeds cannot be empty")
    return [int(v) for v in values]


def _ensure_dataset(dataset_json: str, target_count: int, script_dir: str) -> str:
    path = dataset_json
    if not os.path.isabs(path):
        path = os.path.join(script_dir, path)

    if os.path.exists(path):
        return path

    build_dataset(path, target_count, "")
    return path


def _ranks_with_ties(values: List[float]) -> List[float]:
    ordered = sorted((v, i) for i, v in enumerate(values))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1][0] == ordered[i][0]:
            j += 1
        avg_rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            _, idx = ordered[k]
            ranks[idx] = avg_rank
        i = j + 1
    return ranks


def mann_whitney_u_test(x: List[float], y: List[float]) -> Dict[str, float]:
    if not x or not y:
        return {"u": 0.0, "z": 0.0, "p_value": 1.0}

    n1, n2 = len(x), len(y)
    combined = x + y
    ranks = _ranks_with_ties(combined)
    r1 = sum(ranks[:n1])
    u1 = r1 - n1 * (n1 + 1) / 2.0

    n = n1 + n2
    tie_counts = Counter(combined)
    tie_term = sum(t ** 3 - t for t in tie_counts.values())
    if n > 1:
        sigma_sq = n1 * n2 / 12.0 * ((n + 1) - tie_term / (n * (n - 1)))
    else:
        sigma_sq = 0.0

    if sigma_sq <= 0:
        return {"u": u1, "z": 0.0, "p_value": 1.0}

    sigma = math.sqrt(sigma_sq)
    mu = n1 * n2 / 2.0
    z = (u1 - mu) / sigma
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return {"u": u1, "z": z, "p_value": p}


def cliffs_delta(x: List[float], y: List[float]) -> float:
    if not x or not y:
        return 0.0
    gt = 0
    lt = 0
    for xv in x:
        for yv in y:
            if xv > yv:
                gt += 1
            elif xv < yv:
                lt += 1
    return (gt - lt) / (len(x) * len(y))


def effect_size_label(delta: float) -> str:
    ad = abs(delta)
    if ad < 0.147:
        return "negligible"
    if ad < 0.33:
        return "small"
    if ad < 0.474:
        return "medium"
    return "large"


def summarize(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "std": 0.0}
    if len(values) == 1:
        return {"mean": values[0], "std": 0.0}
    return {"mean": mean(values), "std": stdev(values)}


def ci_half_width(values: List[float], z: float = 1.96) -> float:
    if len(values) <= 1:
        return float("inf")
    return z * stdev(values) / math.sqrt(len(values))


def run_single_seed(dataset: TaskDataset, seed: int, rounds: int) -> Dict[str, Dict[str, float]]:
    baseline_config = {"seed": seed, "simulate_latency": False}
    baselines = [
        Baseline1_NoExperience(config=baseline_config),
        Baseline2_OnlyRAG(config=baseline_config),
        Baseline3_PeriodicFinetune(config=baseline_config),
        Ours_ProposedScheme(config=baseline_config),
    ]
    runner = ExperimentRunner(dataset, baselines)
    results = runner.run_all_experiments(rounds=rounds)
    return {name: data["metrics"] for name, data in results.items()}


def build_report(
    per_seed: Dict[int, Dict[str, Dict[str, float]]],
    seeds: List[int],
    rounds: int,
    dataset_json: str,
) -> Tuple[Dict[str, Any], str]:
    metric_specs = [
        ("success_rate", True, "Success Rate"),
        ("avg_interaction_rounds", False, "Avg Interaction Rounds"),
        ("avg_token_cost", False, "Avg Token Cost"),
        ("avg_time_cost", False, "Avg Time Cost"),
    ]

    baselines = ["baseline1_no_experience", "baseline2_only_rag", "baseline3_periodic_finetune"]
    ours = "ours_proposed_scheme"

    report_data: Dict[str, Any] = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "seeds": seeds,
            "rounds_per_seed": rounds,
            "dataset_json": dataset_json,
        },
        "seed_metrics": per_seed,
        "comparisons": {},
    }

    lines: List[str] = []
    lines.append("# G2 多随机种子统计检验报告")
    lines.append("")
    lines.append(f"- 数据集: {dataset_json}")
    lines.append(f"- 种子列表: {seeds}")
    lines.append(f"- 每种子轮次: {rounds}")
    lines.append("")

    for baseline_name in baselines:
        lines.append(f"## 对比: {ours} vs {baseline_name}")
        lines.append("")
        lines.append("| Metric | Ours Mean±Std | Baseline Mean±Std | p-value | Cliff's delta | Effect |")
        lines.append("|---|---:|---:|---:|---:|---|")

        baseline_result: Dict[str, Any] = {}

        for key, higher_better, label in metric_specs:
            ours_values = [float(per_seed[s][ours][key]) for s in seeds]
            base_values = [float(per_seed[s][baseline_name][key]) for s in seeds]

            stat = mann_whitney_u_test(ours_values, base_values)
            delta = cliffs_delta(ours_values, base_values)

            # For lower-better metrics, positive delta should still indicate ours is better.
            signed_delta = delta if higher_better else -delta

            ours_summary = summarize(ours_values)
            base_summary = summarize(base_values)
            eff_label = effect_size_label(signed_delta)

            lines.append(
                "| "
                f"{label} | "
                f"{ours_summary['mean']:.6f}±{ours_summary['std']:.6f} | "
                f"{base_summary['mean']:.6f}±{base_summary['std']:.6f} | "
                f"{stat['p_value']:.6f} | "
                f"{signed_delta:.6f} | "
                f"{eff_label} |"
            )

            baseline_result[key] = {
                "ours_values": ours_values,
                "baseline_values": base_values,
                "ours_summary": ours_summary,
                "baseline_summary": base_summary,
                "mann_whitney": stat,
                "cliffs_delta_signed": signed_delta,
                "effect_label": eff_label,
            }

        report_data["comparisons"][baseline_name] = baseline_result
        lines.append("")

    lines.append("## 判读建议")
    lines.append("")
    lines.append("- 统计显著性建议阈值: p < 0.05。")
    lines.append("- Cliff's delta(已按指标方向统一): 正值表示本方案更优，绝对值越大效应越强。")

    return report_data, "\n".join(lines)


def main() -> None:
    args = parse_args()
    _validate_args(args)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    seeds = _parse_seed_list(args.seeds)
    dataset_json = resolve_dataset_path(args.dataset_json, script_dir, DEFAULT_DATASET_JSON)
    dataset_json = _ensure_dataset(dataset_json, args.target_count, script_dir)

    dataset = TaskDataset.load_from_json(dataset_json)

    per_seed: Dict[int, Dict[str, Dict[str, float]]] = {}
    processed_seeds: List[int] = []
    for seed in seeds:
        if args.max_seeds and len(processed_seeds) >= args.max_seeds:
            break

        per_seed[seed] = run_single_seed(dataset, seed, args.rounds)
        processed_seeds.append(seed)

        if args.target_success_ci > 0:
            ours_values = [float(per_seed[s]["ours_proposed_scheme"]["success_rate"]) for s in processed_seeds]
            width = ci_half_width(ours_values)
            if width <= args.target_success_ci:
                break

    report_data, report_md = build_report(per_seed, processed_seeds, args.rounds, dataset_json)
    report_data["meta"]["target_success_ci"] = args.target_success_ci
    report_data["meta"]["max_seeds"] = args.max_seeds
    report_data["meta"]["processed_seeds"] = processed_seeds

    output_dir = resolve_output_dir(args.output_dir, script_dir, DEFAULT_OUTPUT_DIR)
    os.makedirs(output_dir, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(output_dir, f"g2_stats_{stamp}.json")
    md_path = os.path.join(output_dir, f"g2_stats_{stamp}_report.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    log_path = append_run_log(
        log_dir=output_dir,
        title="g2_multi_seed_stats",
        params={
            "rounds": args.rounds,
            "seeds": processed_seeds,
            "dataset_json": dataset_json,
            "target_count": args.target_count,
            "output_dir": output_dir,
            "target_success_ci": args.target_success_ci,
            "max_seeds": args.max_seeds,
        },
        outputs={
            "stats_json": json_path,
            "stats_report": md_path,
            "comparison_keys": list(report_data.get("comparisons", {}).keys()),
        },
    )

    print(f"G2 stats json: {json_path}")
    print(f"G2 stats report: {md_path}")
    print(f"G2 run log: {log_path}")


if __name__ == "__main__":
    main()
