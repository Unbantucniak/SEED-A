#!/usr/bin/env python3
"""H1: package final deliverables (reports/charts/summary/docs)."""

from __future__ import annotations

import argparse
import json
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package final project deliverables")
    parser.add_argument("--output-root", type=str, default="../deliverables", help="Packaging output root")
    parser.add_argument("--tag", type=str, default="", help="Optional custom tag suffix for package directory")
    parser.add_argument("--dry-run", action="store_true", help="Print planned files without copying")
    parser.add_argument(
        "--json-error-policy",
        type=str,
        default="lenient",
        choices=["lenient", "strict"],
        help="How to handle broken json artifacts when generating summary",
    )
    return parser.parse_args()


def latest_file(paths: Iterable[Path]) -> Optional[Path]:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def copy_if_exists(src: Optional[Path], dst_dir: Path, dry_run: bool) -> Optional[Path]:
    if src is None or not src.exists():
        return None
    dst = dst_dir / src.name
    if not dry_run:
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return dst


def read_json(path: Optional[Path], *, strict: bool, label: str, warnings: list[str]) -> dict:
    if path is None or not path.exists():
        warnings.append(f"{label}: source file missing")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        msg = f"{label}: failed to read json ({exc})"
        warnings.append(msg)
        if strict:
            raise RuntimeError(msg) from exc
        return {}


def build_summary(
    package_dir: Path,
    latest_exp: Optional[Path],
    latest_g2: Optional[Path],
    latest_g3: Optional[Path],
    dry_run: bool,
    strict_json: bool,
    warnings: list[str],
) -> Path:
    exp_data = read_json(latest_exp, strict=strict_json, label="baseline", warnings=warnings)
    g2_data = read_json(latest_g2, strict=strict_json, label="g2", warnings=warnings)
    g3_data = read_json(latest_g3, strict=strict_json, label="g3", warnings=warnings)

    lines = [
        "# 结题版指标摘要",
        "",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- baseline 实验源文件: {latest_exp.name if latest_exp else 'N/A'}",
        f"- G2 统计源文件: {latest_g2.name if latest_g2 else 'N/A'}",
        f"- G3 消融源文件: {latest_g3.name if latest_g3 else 'N/A'}",
        "",
    ]

    metrics = exp_data.get("ours_proposed_scheme", {}).get("metrics", {})
    if metrics:
        lines.extend([
            "## Ours 关键指标（latest baseline experiment）",
            "",
            f"- success_rate: {metrics.get('success_rate', 0):.6f}",
            f"- avg_interaction_rounds: {metrics.get('avg_interaction_rounds', 0):.6f}",
            f"- avg_time_cost: {metrics.get('avg_time_cost', 0):.6f}",
            f"- avg_token_cost: {metrics.get('avg_token_cost', 0):.6f}",
            "",
        ])

    comparisons = g2_data.get("comparisons", {})
    if comparisons:
        lines.extend([
            "## G2 统计检验概览",
            "",
            f"- 对比基线数: {len(comparisons)}",
            f"- 基线列表: {', '.join(comparisons.keys())}",
            "",
        ])

    g3_metrics = g3_data.get("metrics", {})
    if g3_metrics:
        lines.extend([
            "## G3 消融概览",
            "",
            f"- 场景数: {len(g3_metrics)}",
            f"- 场景列表: {', '.join(g3_metrics.keys())}",
            "",
        ])

    summary_path = package_dir / "metric_summary.md"
    if not dry_run:
        summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def _rel_to_package(package_dir: Path, path: Path) -> str:
    try:
        return path.relative_to(package_dir).as_posix()
    except ValueError:
        return path.as_posix()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    exp_results = script_dir / "results"
    root_results = repo_root / "results"

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = (script_dir / args.output_root).resolve()
    package_name = f"h1_package_{stamp}"
    if args.tag:
        package_name = f"{package_name}_{args.tag}"
    package_dir = output_root / package_name

    latest_exp = latest_file(list(exp_results.glob("experiment_*.json")) + list(root_results.glob("experiment_*.json")))
    latest_exp_report = latest_file(list(exp_results.glob("experiment_*_report.md")) + list(root_results.glob("experiment_*_report.md")))
    latest_g2 = latest_file(exp_results.glob("g2_stats_*.json"))
    latest_g2_report = latest_file(exp_results.glob("g2_stats_*_report.md"))
    latest_g3 = latest_file(exp_results.glob("g3_ablation_*.json"))
    latest_g3_report = latest_file(exp_results.glob("g3_ablation_*_report.md"))
    latest_success_chart = latest_file(list(exp_results.glob("success_rate_*.png")) + list(root_results.glob("success_rate_*.png")))
    latest_time_chart = latest_file(list(exp_results.glob("avg_time_*.png")) + list(root_results.glob("avg_time_*.png")))
    run_log = exp_results / "experiment_run_log.md"

    docs_to_copy = [
        repo_root / "README.md",
        repo_root / "项目优化修复清单.md",
        repo_root / "项目最终交付总览.md",
        repo_root / "申报书分阶段任务完成文档.md",
        repo_root / "技术研究报告初稿.md",
        repo_root / "docs" / "5-依赖锁定与升级流程.md",
        repo_root / "docs" / "6-论文附录与复现实验说明模板.md",
    ]

    if args.dry_run:
        print(f"[DRY-RUN] package_dir: {package_dir}")
    else:
        package_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for src in [
        latest_exp,
        latest_exp_report,
        latest_g2,
        latest_g2_report,
        latest_g3,
        latest_g3_report,
        latest_success_chart,
        latest_time_chart,
        run_log,
    ]:
        dst = copy_if_exists(src, package_dir / "artifacts", args.dry_run)
        if dst:
            copied.append(dst)

    for doc in docs_to_copy:
        dst = copy_if_exists(doc, package_dir / "docs", args.dry_run)
        if dst:
            copied.append(dst)

    warnings: list[str] = []
    summary_path = build_summary(
        package_dir,
        latest_exp,
        latest_g2,
        latest_g3,
        args.dry_run,
        strict_json=args.json_error_policy == "strict",
        warnings=warnings,
    )

    if args.dry_run:
        print(f"[DRY-RUN] summary would be written to: {summary_path}")
        if warnings:
            print(f"[DRY-RUN] warnings: {warnings}")
    else:
        manifest = package_dir / "manifest.txt"
        manifest_items = copied + [summary_path]
        manifest.write_text("\n".join(_rel_to_package(package_dir, p) for p in manifest_items), encoding="utf-8")

        metadata = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "package_name": package_name,
            "script": str(Path(__file__).name),
            "sources": {
                "latest_experiment_json": latest_exp.name if latest_exp else None,
                "latest_g2_json": latest_g2.name if latest_g2 else None,
                "latest_g3_json": latest_g3.name if latest_g3 else None,
            },
            "files": [_rel_to_package(package_dir, p) for p in manifest_items],
            "warnings": warnings,
        }
        (package_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        if warnings:
            logger.warning("H1 packaging completed with warnings: %s", warnings)

    print(f"H1 package output: {package_dir}")


if __name__ == "__main__":
    main()
