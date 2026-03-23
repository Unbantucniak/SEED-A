"""Shared path resolution utilities for experiment scripts."""

from __future__ import annotations

import os


def resolve_dataset_path(dataset_arg: str, script_dir: str, default_dataset: str) -> str:
    if os.path.isabs(dataset_arg):
        return dataset_arg

    if dataset_arg == default_dataset:
        return os.path.abspath(os.path.join(script_dir, dataset_arg))

    cwd_candidate = os.path.abspath(dataset_arg)
    if os.path.exists(cwd_candidate):
        return cwd_candidate
    return os.path.abspath(os.path.join(script_dir, dataset_arg))


def resolve_output_dir(output_arg: str, script_dir: str, default_output: str) -> str:
    if os.path.isabs(output_arg):
        return output_arg

    if output_arg == default_output:
        return os.path.abspath(os.path.join(script_dir, output_arg))

    return os.path.abspath(output_arg)
