"""
监控模块 - 指标收集
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import json
from pathlib import Path

@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = field(default_factory=dict)

class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, metrics_dir: str = "logs/metrics"):
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.metrics: Dict[str, List[MetricPoint]] = defaultdict(list)
        
        # 实时指标缓存
        self.realtime_cache: Dict[str, float] = {}
    
    def record(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """记录指标"""
        point = MetricPoint(
            timestamp=datetime.now(),
            value=value,
            tags=tags or {}
        )
        self.metrics[metric_name].append(point)
        
        # 更新缓存
        self.realtime_cache[metric_name] = value
    
    def get(self, metric_name: str, duration: Optional[timedelta] = None) -> List[MetricPoint]:
        """获取指标数据"""
        points = self.metrics.get(metric_name, [])
        
        if duration:
            cutoff = datetime.now() - duration
            points = [p for p in points if p.timestamp >= cutoff]
        
        return points
    
    def get_average(self, metric_name: str, duration: Optional[timedelta] = None) -> Optional[float]:
        """获取指标平均值"""
        points = self.get(metric_name, duration)
        if not points:
            return None
        return sum(p.value for p in points) / len(points)
    
    def get_latest(self, metric_name: str) -> Optional[float]:
        """获取最新指标值"""
        return self.realtime_cache.get(metric_name)
    
    def get_percentile(self, metric_name: str, percentile: float, duration: Optional[timedelta] = None) -> Optional[float]:
        """获取指标百分位数"""
        points = self.get(metric_name, duration)
        if not points:
            return None
        
        values = sorted(p.value for p in points)
        idx = int(len(values) * percentile / 100)
        return values[min(idx, len(values) - 1)]
    
    def export(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """导出指标数据"""
        if file_path is None:
            file_path = self.metrics_dir / f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        data = {}
        for name, points in self.metrics.items():
            data[name] = [
                {
                    "timestamp": p.timestamp.isoformat(),
                    "value": p.value,
                    "tags": p.tags
                }
                for p in points
            ]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return data
    
    def clear(self, older_than: Optional[timedelta] = None):
        """清理旧指标"""
        if older_than is None:
            older_than = timedelta(days=7)
        
        cutoff = datetime.now() - older_than
        for name in self.metrics:
            self.metrics[name] = [p for p in self.metrics[name] if p.timestamp >= cutoff]


# 常用指标名称
class Metrics:
    EXPERIENCE_SUCCESS_RATE = "experience.success_rate"
    EXPERIENCE_USE_COUNT = "experience.use_count"
    EXPERIENCE_AVG_BENEFIT = "experience.avg_benefit"
    ROUTING_STRATEGY_COUNT = "routing.strategy_count"
    ROUTING_LATENCY = "routing.latency"
    MANAGER_QUALITY_SCORE = "manager.quality_score"
    SYSTEM_HEALTH_SCORE = "system.health_score"
    TASK_SUCCESS_RATE = "task.success_rate"
    TASK_AVG_LATENCY = "task.avg_latency"


# 全局指标收集器
metrics_collector = MetricsCollector()
