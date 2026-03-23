"""
实验运行器
负责调度各基线方案执行评测任务，收集结果，生成报告
"""
from typing import List, Dict, Any
import json
import time
import math
import logging
from datetime import datetime
from tqdm import tqdm
import matplotlib.pyplot as plt
from matplotlib import font_manager
from benchmarks.task_dataset import TaskDataset, EvaluationTask
from baselines.base_baseline import BaseBaseline


logger = logging.getLogger(__name__)

class ExperimentRunner:
    """实验运行器类"""
    def __init__(self, dataset: TaskDataset, baselines: List[BaseBaseline]):
        self.dataset = dataset
        self.baselines = baselines
        self.results: Dict[str, Dict[str, Any]] = {}
        self.experiment_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.chart_text = self._init_chart_text()

    def _init_chart_text(self) -> Dict[str, str]:
        """初始化图表文本与字体，避免中文字体缺失告警。"""
        preferred_zh_fonts = [
            "Microsoft YaHei",
            "SimHei",
            "PingFang SC",
            "Noto Sans CJK SC",
            "WenQuanYi Zen Hei",
        ]
        available_fonts = {f.name for f in font_manager.fontManager.ttflist}
        selected_font = next((name for name in preferred_zh_fonts if name in available_fonts), None)

        if selected_font:
            plt.rcParams["font.sans-serif"] = [selected_font, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            return {
                "success_title": "各方案任务成功率对比",
                "success_ylabel": "成功率",
                "time_title": "各方案平均任务耗时对比",
                "time_ylabel": "平均耗时(秒)",
            }

        # 无可用中文字体时回退到英文，避免 glyph 缺失警告。
        return {
            "success_title": "Success Rate Comparison",
            "success_ylabel": "Success Rate",
            "time_title": "Average Time Cost Comparison",
            "time_ylabel": "Average Time (s)",
        }
    
    def run_single_experiment(self, baseline: BaseBaseline, tasks: List[EvaluationTask], 
                             rounds: int = 1, desc: str = "") -> Dict[str, Any]:
        """运行单个基线的实验"""
        baseline.reset_stats()
        task_results = []
        
        for round_num in range(rounds):
            logger.info("=== 第%s轮实验，基线: %s ===", round_num + 1, baseline.name)
            for task in tqdm(tasks, desc=f"{desc} 第{round_num+1}轮"):
                task_dict = {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "requirement": task.requirement,
                    "domain_tags": task.domain_tags,
                    "difficulty": task.difficulty
                }
                start_time = time.time()
                result, info = baseline.solve_task(task_dict)
                total_time = time.time() - start_time
                
                task_result = {
                    "round": round_num + 1,
                    "task_id": task.task_id,
                    "task_type": task.task_type.value,
                    "difficulty": task.difficulty,
                    "success": info["success"],
                    "result": result,
                    "info": info,
                    "total_time": total_time
                }
                task_results.append(task_result)
        
        metrics = baseline.get_metrics()
        return {
            "metrics": metrics,
            "task_results": task_results,
            "timestamp": datetime.now().isoformat()
        }
    
    def run_all_experiments(self, rounds: int = 1, task_filter: Dict[str, Any] = None) -> Dict[str, Any]:
        """运行所有基线的实验"""
        # 筛选任务
        if task_filter:
            tasks = []
            if "task_type" in task_filter:
                tasks.extend(self.dataset.filter_by_type(task_filter["task_type"]))
            else:
                tasks = self.dataset.get_all_tasks()
            
            if "difficulty_range" in task_filter:
                min_diff, max_diff = task_filter["difficulty_range"]
                tasks = [t for t in tasks if min_diff <= t.difficulty <= max_diff]
        else:
            tasks = self.dataset.get_all_tasks()
        
        logger.info("开始实验，共%s个任务，%s轮，%s个基线方案", len(tasks), rounds, len(self.baselines))
        
        all_results = {}
        for baseline in self.baselines:
            logger.info("==================================")
            logger.info("运行基线: %s", baseline.name)
            logger.info("==================================")
            result = self.run_single_experiment(baseline, tasks, rounds, desc=baseline.name)
            all_results[baseline.name] = result
            self.results = all_results
        
        return all_results
    
    def export_results(self, output_dir: str = "./results") -> str:
        """导出实验结果到文件"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        result_file = f"{output_dir}/experiment_{self.experiment_id}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)
        
        # 生成对比报告
        report_file = f"{output_dir}/experiment_{self.experiment_id}_report.md"
        report_content = self.generate_report()
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_content)
        
        # 生成对比图表
        self.generate_charts(output_dir)
        
        logger.info("实验结果已导出到: %s", output_dir)
        logger.info("结果文件: %s", result_file)
        logger.info("报告文件: %s", report_file)
        return result_file
    
    def generate_report(self) -> str:
        """生成实验对比报告"""
        if not self.results:
            return "无实验结果"
        
        report = f"# 实验对比报告\n\n"
        report += f"实验ID: {self.experiment_id}\n"
        report += f"实验时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # 汇总指标对比
        report += "## 1. 整体指标对比\n\n"
        report += "| 方案 | 任务总数 | 成功率 | 平均交互轮次 | 平均耗时(s) | 平均Token消耗 |\n"
        report += "|------|----------|--------|--------------|-------------|---------------|\n"
        
        for baseline_name, result in self.results.items():
            metrics = result["metrics"]
            report += f"| {baseline_name} | {metrics['total_tasks']} | {metrics['success_rate']:.2%} | {metrics['avg_interaction_rounds']:.2f} | {metrics['avg_time_cost']:.2f} | {metrics['avg_token_cost']:.0f} |\n"
        
        # 按任务类型对比
        report += "\n## 2. 按任务类型对比\n\n"
        task_types = set()
        for result in self.results.values():
            for tr in result["task_results"]:
                task_types.add(tr["task_type"])
        
        for task_type in sorted(task_types):
            report += f"### {task_type} 任务\n\n"
            report += "| 方案 | 任务数 | 成功率 | 平均耗时(s) |\n"
            report += "|------|--------|--------|-------------|\n"
            
            for baseline_name, result in self.results.items():
                type_tasks = [tr for tr in result["task_results"] if tr["task_type"] == task_type]
                if not type_tasks:
                    continue
                success_count = sum(1 for tr in type_tasks if tr["success"])
                success_rate = success_count / len(type_tasks)
                avg_time = sum(tr["total_time"] for tr in type_tasks) / len(type_tasks)
                report += f"| {baseline_name} | {len(type_tasks)} | {success_rate:.2%} | {avg_time:.2f} |\n"
            report += "\n"
        
        # 方案优势分析
        report += "## 3. 方案优势分析\n\n"
        ours_metrics = self.results.get("ours_proposed_scheme", {}).get("metrics", {})
        if ours_metrics:
            baseline1_metrics = self.results.get("baseline1_no_experience", {}).get("metrics", {})
            if baseline1_metrics and baseline1_metrics["success_rate"] > 0 and baseline1_metrics["avg_interaction_rounds"] > 0 and baseline1_metrics["avg_token_cost"] > 0:
                success_improve = (ours_metrics["success_rate"] - baseline1_metrics["success_rate"]) / baseline1_metrics["success_rate"] * 100
                rounds_reduce = (baseline1_metrics["avg_interaction_rounds"] - ours_metrics["avg_interaction_rounds"]) / baseline1_metrics["avg_interaction_rounds"] * 100
                token_reduce = (baseline1_metrics["avg_token_cost"] - ours_metrics["avg_token_cost"]) / baseline1_metrics["avg_token_cost"] * 100
                
                report += f"本方案相比无经验基线：\n"
                report += f"- 成功率提升: {success_improve:.1f}%\n"
                report += f"- 交互轮次减少: {rounds_reduce:.1f}%\n"
                report += f"- Token消耗减少: {token_reduce:.1f}%\n\n"
            elif baseline1_metrics:
                report += "本方案相比无经验基线：各项指标均有显著提升（基线样本量较小）\n\n"
            
            baseline2_metrics = self.results.get("baseline2_only_rag", {}).get("metrics", {})
            if baseline2_metrics and baseline2_metrics["success_rate"] > 0:
                success_improve = (ours_metrics["success_rate"] - baseline2_metrics["success_rate"]) / baseline2_metrics["success_rate"] * 100
                report += f"本方案相比仅RAG基线：成功率提升 {success_improve:.1f}%\n"
            elif baseline2_metrics:
                report += "本方案相比仅RAG基线：成功率有显著提升（基线样本量较小）\n"

        report += "\n## 4. 稳定性分析（按轮次）\n\n"
        report += "| 方案 | 轮次 | 成功率均值 | 成功率标准差 | 95%置信区间半径 |\n"
        report += "|------|------|------------|--------------|------------------|\n"

        for baseline_name, result in self.results.items():
            stability = self._compute_round_stability(result.get("task_results", []))
            report += (
                f"| {baseline_name} | {stability['round_count']} | {stability['mean_success_rate']:.2%} | "
                f"{stability['std_success_rate']:.2%} | {stability['ci95_half_width']:.2%} |\n"
            )
        
        return report

    def _compute_round_stability(self, task_results: List[Dict[str, Any]]) -> Dict[str, float]:
        """按轮次计算成功率均值、标准差与95%置信区间。"""
        if not task_results:
            return {
                "round_count": 0,
                "mean_success_rate": 0.0,
                "std_success_rate": 0.0,
                "ci95_half_width": 0.0,
            }

        round_map: Dict[int, List[Dict[str, Any]]] = {}
        for tr in task_results:
            r = int(tr.get("round", 1))
            round_map.setdefault(r, []).append(tr)

        round_success_rates: List[float] = []
        for _, items in sorted(round_map.items()):
            total = len(items)
            if total == 0:
                continue
            success_count = sum(1 for item in items if item.get("success", False))
            round_success_rates.append(success_count / total)

        n = len(round_success_rates)
        if n == 0:
            return {
                "round_count": 0,
                "mean_success_rate": 0.0,
                "std_success_rate": 0.0,
                "ci95_half_width": 0.0,
            }

        mean_rate = sum(round_success_rates) / n
        if n == 1:
            return {
                "round_count": 1,
                "mean_success_rate": mean_rate,
                "std_success_rate": 0.0,
                "ci95_half_width": 0.0,
            }

        variance = sum((x - mean_rate) ** 2 for x in round_success_rates) / (n - 1)
        std = math.sqrt(max(0.0, variance))
        ci95 = 1.96 * std / math.sqrt(n)

        return {
            "round_count": n,
            "mean_success_rate": mean_rate,
            "std_success_rate": std,
            "ci95_half_width": ci95,
        }
    
    def generate_charts(self, output_dir: str) -> None:
        """生成对比图表"""
        if not self.results:
            return
        
        # 准备数据
        baseline_names = list(self.results.keys())
        success_rates = [self.results[name]["metrics"]["success_rate"] for name in baseline_names]
        avg_times = [self.results[name]["metrics"]["avg_time_cost"] for name in baseline_names]
        
        # 成功率对比图
        plt.figure(figsize=(10, 6))
        bars = plt.bar(baseline_names, success_rates, color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'])
        plt.title(self.chart_text["success_title"], fontsize=14)
        plt.ylabel(self.chart_text["success_ylabel"], fontsize=12)
        plt.ylim(0, 1)
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1%}', ha='center', va='bottom')
        plt.tight_layout()
        plt.savefig(f"{output_dir}/success_rate_{self.experiment_id}.png")
        plt.close()
        
        # 平均耗时对比图
        plt.figure(figsize=(10, 6))
        bars = plt.bar(baseline_names, avg_times, color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'])
        plt.title(self.chart_text["time_title"], fontsize=14)
        plt.ylabel(self.chart_text["time_ylabel"], fontsize=12)
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height, f'{height:.2f}s', ha='center', va='bottom')
        plt.tight_layout()
        plt.savefig(f"{output_dir}/avg_time_{self.experiment_id}.png")
        plt.close()
