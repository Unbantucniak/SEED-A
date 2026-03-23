#!/usr/bin/env python3
"""Build a reproducible 100+ task dataset for G1 large-scale experiments."""

from __future__ import annotations

import argparse
import copy
import json
import os
from typing import Any, Dict, List

from benchmarks.task_dataset import TaskDataset, EvaluationTask


def _task_to_dict(task: EvaluationTask) -> Dict[str, Any]:
    return {
        "task_id": task.task_id,
        "task_type": task.task_type.value,
        "name": task.name,
        "description": task.description,
        "requirement": task.requirement,
        "test_cases": task.test_cases,
        "expected_output": task.expected_output,
        "difficulty": task.difficulty,
        "domain_tags": task.domain_tags or [],
        "metadata": task.metadata or {},
    }


def _clone_task(base: Dict[str, Any], serial: int) -> Dict[str, Any]:
    cloned = copy.deepcopy(base)
    cloned["task_id"] = f"{base['task_id']}_g1_{serial:03d}"
    cloned["name"] = f"{base['name']} (G1-{serial:03d})"
    cloned["description"] = (
        f"{base.get('description', base['requirement'])} | g1 synthetic variant {serial:03d}"
    )
    cloned["requirement"] = (
        f"{base['requirement']}\n[Variant {serial:03d}] Keep semantic intent while changing details for robustness."
    )
    cloned["difficulty"] = ((int(base.get("difficulty", 3)) + serial - 1) % 5) + 1

    metadata = dict(base.get("metadata", {}))
    metadata.update(
        {
            "synthetic": True,
            "variant_serial": serial,
            "source_task_id": base["task_id"],
        }
    )
    cloned["metadata"] = metadata
    return cloned


def build_dataset(output_json: str, target_count: int, expanded_json: str = "") -> int:
    dataset = TaskDataset()
    dataset.load_sample_tasks()

    merged: Dict[str, Dict[str, Any]] = {}
    for task in dataset.get_all_tasks():
        merged[task.task_id] = _task_to_dict(task)

    if expanded_json and os.path.exists(expanded_json):
        try:
            external_dataset = TaskDataset.load_from_json(expanded_json)
            for task in external_dataset.get_all_tasks():
                merged.setdefault(task.task_id, _task_to_dict(task))
        except Exception as exc:
            print(f"[WARN] Skip external dataset due to parse error: {exc}")

    tasks: List[Dict[str, Any]] = list(merged.values())
    if not tasks:
        raise ValueError("No tasks available to build G1 dataset")

    serial = 1
    base_size = len(tasks)
    while len(tasks) < target_count:
        base = tasks[(serial - 1) % base_size]
        tasks.append(_clone_task(base, serial))
        serial += 1

    output_dir = os.path.dirname(output_json)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

    return len(tasks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fixed 100+ task dataset for G1")
    parser.add_argument("--target-count", type=int, default=120, help="Target number of tasks")
    parser.add_argument(
        "--output-json",
        type=str,
        default="./benchmarks/g1_full_120_tasks.json",
        help="Output dataset JSON path",
    )
    parser.add_argument(
        "--expanded-json",
        type=str,
        default="",
        help="Optional expanded dataset JSON path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = build_dataset(args.output_json, args.target_count, args.expanded_json)
    print(f"Built G1 dataset: {args.output_json} ({count} tasks)")


if __name__ == "__main__":
    main()
