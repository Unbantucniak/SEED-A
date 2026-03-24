#!/usr/bin/env python3
"""One-click G1 runner: fixed params + 100+ tasks dataset."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from build_g1_dataset import build_dataset
from path_resolver import resolve_dataset_path, resolve_output_dir
from run_logger import append_run_log


DEFAULT_DATASET_JSON = "./benchmarks/g1_full_120_tasks.json"
DEFAULT_OUTPUT_DIR = "../results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run G1 large-scale experiment with fixed params")
    parser.add_argument("--rounds", type=int, default=5, help="Experiment rounds")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--target-count", type=int, default=120, help="Target task count")
    parser.add_argument(
        "--dataset-json",
        type=str,
        default=DEFAULT_DATASET_JSON,
        help="G1 dataset JSON path",
    )
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument(
        "--expanded-json",
        type=str,
        default="",
        help="Optional external dataset to merge before synthetic expansion",
    )
    parser.add_argument("--log-level", type=str, default="INFO", help="Logging level")
    parser.add_argument("--simulate-latency", action="store_true", help="Enable baseline latency simulation")
    parser.add_argument("--rebuild-dataset", action="store_true", help="Force rebuild G1 dataset")
    return parser.parse_args()


def _validate_args(args: argparse.Namespace) -> None:
    if args.rounds <= 0:
        raise ValueError("rounds must be greater than 0")
    if args.target_count <= 0:
        raise ValueError("target_count must be greater than 0")


def main() -> None:
    args = parse_args()
    _validate_args(args)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    dataset_json = resolve_dataset_path(args.dataset_json, script_dir, DEFAULT_DATASET_JSON)

    if args.rebuild_dataset or not os.path.exists(dataset_json):
        expanded_json = ""
        if args.expanded_json:
            expanded_json = resolve_dataset_path(args.expanded_json, script_dir, args.expanded_json)
        built_count = build_dataset(dataset_json, args.target_count, expanded_json)
        print(f"[G1] dataset ready: {dataset_json} ({built_count} tasks)")

    output_dir = resolve_output_dir(args.output_dir, script_dir, DEFAULT_OUTPUT_DIR)

    run_experiment_py = os.path.join(script_dir, "run_experiment.py")
    cmd = [
        sys.executable,
        run_experiment_py,
        "--rounds",
        str(args.rounds),
        "--seed",
        str(args.seed),
        "--dataset-json",
        dataset_json,
        "--output-dir",
        output_dir,
        "--log-level",
        args.log_level,
    ]

    if args.simulate_latency:
        cmd.append("--simulate-latency")

    print("[G1] run command:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    log_path = append_run_log(
        log_dir=output_dir,
        title="g1_full_scale_run",
        params={
            "rounds": args.rounds,
            "seed": args.seed,
            "target_count": args.target_count,
            "dataset_json": dataset_json,
            "expanded_json": args.expanded_json,
            "simulate_latency": args.simulate_latency,
            "output_dir": output_dir,
        },
        outputs={
            "invoked_command": cmd,
        },
        notes="Detailed baseline metrics are recorded by run_experiment.py in the same output directory log.",
    )
    print(f"[G1] run log: {log_path}")


if __name__ == "__main__":
    main()
