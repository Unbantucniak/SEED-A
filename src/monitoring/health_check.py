"""
监控模块 - 健康检查
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

class HealthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

@dataclass
class HealthCheckResult:
    """健康检查结果"""
    component: str
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    timestamp: datetime

class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        self.checks: Dict[str, callable] = {}
        self.last_results: List[HealthCheckResult] = []
    
    def register_check(self, name: str, check_func: callable):
        """注册健康检查函数"""
        self.checks[name] = check_func
    
    def run_check(self, name: str) -> HealthCheckResult:
        """运行单个健康检查"""
        if name not in self.checks:
            return HealthCheckResult(
                component=name,
                status=HealthStatus.UNKNOWN,
                message=f"Check '{name}' not registered",
                details={},
                timestamp=datetime.now()
            )
        
        try:
            result = self.checks[name]()
            if isinstance(result, tuple):
                status, message, details = result
                return HealthCheckResult(
                    component=name,
                    status=status if isinstance(status, HealthStatus) else HealthStatus(status),
                    message=message,
                    details=details,
                    timestamp=datetime.now()
                )
            return result
        except Exception as e:
            return HealthCheckResult(
                component=name,
                status=HealthStatus.CRITICAL,
                message=f"Check failed: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now()
            )
    
    def run_all_checks(self) -> List[HealthCheckResult]:
        """运行所有健康检查"""
        results = []
        for name in self.checks:
            result = self.run_check(name)
            results.append(result)
        
        self.last_results = results
        return results
    
    def get_overall_status(self) -> HealthStatus:
        """获取整体健康状态"""
        if not self.last_results:
            self.run_all_checks()
        
        statuses = [r.status for r in self.last_results]
        
        if HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL
        if HealthStatus.WARNING in statuses:
            return HealthStatus.WARNING
        if HealthStatus.HEALTHY in statuses:
            return HealthStatus.HEALTHY
        return HealthStatus.UNKNOWN
    
    def get_status_summary(self) -> Dict[str, Any]:
        """获取健康状态摘要"""
        overall = self.get_overall_status()
        
        return {
            "overall_status": overall.value,
            "timestamp": datetime.now().isoformat(),
            "checks": [
                {
                    "component": r.component,
                    "status": r.status.value,
                    "message": r.message
                }
                for r in self.last_results
            ]
        }


# 预定义健康检查
def create_experience_graph_health_check(graph) -> callable:
    """创建经验图谱健康检查"""
    def check():
        if not graph:
            return (HealthStatus.CRITICAL, "Experience graph not initialized", {})
        
        node_count = len(graph.experience_nodes)
        edge_count = len(graph.edges)
        
        details = {
            "node_count": node_count,
            "edge_count": edge_count
        }
        
        if node_count == 0:
            return (HealthStatus.WARNING, "No experiences in graph", details)
        
        if node_count < 10:
            return (HealthStatus.WARNING, "Few experiences, may affect performance", details)
        
        return (HealthStatus.HEALTHY, f"Graph healthy: {node_count} experiences", details)
    
    return check

def create_experience_quality_health_check(manager) -> callable:
    """创建经验质量健康检查"""
    def check():
        if not manager:
            return (HealthStatus.CRITICAL, "Experience manager not initialized", {})
        
        stats = manager.get_statistics()
        
        avg_success_rate = stats.get("average_success_rate", 0)
        avg_timeliness = stats.get("average_timeliness", 0)
        redundancy_rate = stats.get("redundancy_rate", 0)
        conflict_rate = stats.get("conflict_rate", 0)
        
        issues = []
        
        if avg_success_rate < 0.6:
            issues.append(f"Low success rate: {avg_success_rate:.1%}")
        
        if avg_timeliness < 0.5:
            issues.append(f"Low timeliness: {avg_timeliness:.1%}")
        
        if redundancy_rate > 0.3:
            issues.append(f"High redundancy: {redundancy_rate:.1%}")
        
        if conflict_rate > 0.1:
            issues.append(f"High conflict rate: {conflict_rate:.1%}")
        
        details = {
            "average_success_rate": avg_success_rate,
            "average_timeliness": avg_timeliness,
            "redundancy_rate": redundancy_rate,
            "conflict_rate": conflict_rate
        }
        
        if len(issues) >= 3:
            return (HealthStatus.CRITICAL, "; ".join(issues), details)
        elif len(issues) >= 1:
            return (HealthStatus.WARNING, "; ".join(issues), details)
        
        return (HealthStatus.HEALTHY, "Experience quality healthy", details)
    
    return check

def create_routing_health_check(router) -> callable:
    """创建路由引擎健康检查"""
    def check():
        if not router:
            return (HealthStatus.CRITICAL, "Router not initialized", {})
        
        strategy_stats = router.get_strategy_usage_stats()
        
        details = {
            "total_routes": strategy_stats.get("total", 0),
            "strategy_distribution": strategy_stats
        }
        
        if strategy_stats.get("total", 0) == 0:
            return (HealthStatus.WARNING, "No routing data yet", details)
        
        return (HealthStatus.HEALTHY, f"Routed {strategy_stats['total']} tasks", details)
    
    return check


# 全局健康检查器
health_checker = HealthChecker()
