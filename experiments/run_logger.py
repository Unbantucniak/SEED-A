"""Utilities for appending reproducible experiment run logs."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional


def append_run_log(log_dir: str, title: str, params: Dict[str, Any], outputs: Dict[str, Any], notes: Optional[str] = None) -> str:
    """Append one run record into a Markdown changelog under the target output directory."""
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "experiment_run_log.md")

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
