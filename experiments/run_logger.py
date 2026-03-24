"""Utilities for appending reproducible experiment run logs."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional


def _cleanup_archives(log_dir: str, backup_count: int) -> None:
    archives = [
        os.path.join(log_dir, name)
        for name in os.listdir(log_dir)
        if name.startswith("experiment_run_log_") and name.endswith(".md")
    ]
    archives.sort(key=lambda path: os.path.getmtime(path), reverse=True)

    for extra in archives[max(0, backup_count):]:
        try:
            os.remove(extra)
        except OSError:
            continue


def _rotate_if_needed(log_path: str, max_file_size_mb: int, backup_count: int) -> None:
    if max_file_size_mb <= 0:
        return
    if not os.path.exists(log_path):
        return

    max_bytes = max_file_size_mb * 1024 * 1024
    if os.path.getsize(log_path) < max_bytes:
        return

    log_dir = os.path.dirname(log_path)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = os.path.join(log_dir, f"experiment_run_log_{stamp}.md")
    os.replace(log_path, archive_path)
    _cleanup_archives(log_dir, backup_count)


def append_run_log(
    log_dir: str,
    title: str,
    params: Dict[str, Any],
    outputs: Dict[str, Any],
    notes: Optional[str] = None,
    max_file_size_mb: int = 10,
    backup_count: int = 20,
) -> str:
    """Append one run record into a Markdown changelog under the target output directory."""
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "experiment_run_log.md")
    _rotate_if_needed(log_path, max_file_size_mb=max_file_size_mb, backup_count=backup_count)

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"## {stamp} | {title}",
        "",
        "### Params",
        "",
        "```json",
        json.dumps(params, ensure_ascii=False, indent=2),
        "```",
        "",
        "### Outputs",
        "",
        "```json",
        json.dumps(outputs, ensure_ascii=False, indent=2),
        "```",
    ]

    if notes:
        lines.extend([
            "",
            "### Notes",
            "",
            notes,
        ])

    lines.append("\n---\n")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return log_path
