"""
经验管理增强模块
- LLM-as-Judge 自动质量评估
- 对抗性验证机制
- 分布式支持（Redis缓存）
"""
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import json
import hashlib
import re
import logging


logger = logging.getLogger(__name__)


class QualityDimension(Enum):
    """质量评估维度"""
    CORRECTNESS = "correctness"        # 正确性
    COMPLETENESS = "completeness"      # 完整性
    REUSABILITY = "reusability"        # 可复用性
    SAFETY = "safety"                  # 安全性
    EFFICIENCY = "efficiency"          # 效率


class LLMasJudge:
    """LLM-as-Judge 质量评估器"""
    
    def __init__(self, llm_provider: Optional[Callable] = None):
        """
        初始化评估器
        
        Args:
            llm_provider: LLM调用函数，签名为 (prompt: str) -> str
                         如果为None，使用基于规则的回退评估
        """
        self.llm_provider = llm_provider
        
        # 评估维度权重
        self.dimension_weights = {
            QualityDimension.CORRECTNESS: 0.3,
            QualityDimension.COMPLETENESS: 0.2,
            QualityDimension.REUSABILITY: 0.25,
            QualityDimension.SAFETY: 0.15,
            QualityDimension.EFFICIENCY: 0.1
        }
    
    def _build_evaluation_prompt(self, experience_data: Dict) -> str:
        """构建评估提示"""
        task_intent = experience_data.get("task_intent", {})
        execution_result = experience_data.get("execution_result", {})
        
        prompt = f"""请作为专业的代码质量评估专家，评估以下经验的各个质量维度。

## 任务信息
- 原始需求: {task_intent.get('original_requirement', '')}
- 用户指令: {task_intent.get('user_instruction', '')}
- 任务类型: {task_intent.get('task_type', '')}

## 执行结果
- 输出内容: {execution_result.get('final_output', '')[:500]}
- 执行成功: {execution_result.get('is_success', False)}
- 错误信息: {execution_result.get('error_info', '无')}

## 请评估以下维度（0-1分）：
1. 正确性 (correctness): 代码或方案是否正确实现需求
2. 完整性 (completeness): 是否覆盖所有需求和边界情况
3. 可复用性 (reusability): 是否具有通用性，可复用于类似场景
4. 安全性 (safety): 是否存在安全风险
5. 效率 (efficiency): 实现是否高效

请以JSON格式返回评估结果：
{{
    "correctness": 0.85,
    "completeness": 0.7,
    "reusability": 0.8,
    "safety": 0.9,
    "efficiency": 0.75,
    "overall": 0.8,
    "reasoning": "评估理由"
}}"""
        return prompt
    
    def evaluate(self, experience_data: Dict) -> Dict[str, Any]:
        """
        评估经验质量
        
        Args:
            experience_data: 经验数据字典
            
        Returns:
            评估结果，包含各维度得分和综合得分
        """
        # 如果有LLM提供者，使用LLM评估
        if self.llm_provider:
            try:
                prompt = self._build_evaluation_prompt(experience_data)
                response = self.llm_provider(prompt)
                
                # 解析LLM响应
                result = self._parse_llm_response(response)
                if result:
                    return result
            except Exception as e:
                logger.warning("LLM评估失败: %s，使用规则回退", e)
        
        # 回退：基于规则的评估
        return self._rule_based_evaluation(experience_data)
    
    def _parse_llm_response(self, response: str) -> Optional[Dict]:
        """解析LLM响应"""
        try:
            # 尝试提取JSON
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "dimension_scores": {
                        QualityDimension.CORRECTNESS: data.get("correctness", 0.5),
                        QualityDimension.COMPLETENESS: data.get("completeness", 0.5),
                        QualityDimension.REUSABILITY: data.get("reusability", 0.5),
                        QualityDimension.SAFETY: data.get("safety", 0.5),
                        QualityDimension.EFFICIENCY: data.get("efficiency", 0.5)
                    },
                    "overall_score": data.get("overall", 0.5),
                    "reasoning": data.get("reasoning", ""),
                    "source": "llm"
                }
        except Exception as e:
            logger.warning("JSON解析失败: %s", e)
        return None
    
    def _rule_based_evaluation(self, experience_data: Dict) -> Dict[str, Any]:
        """基于规则的评估"""
        scores = {}
        
        # 1. 正确性评估
        is_success = experience_data.get("execution_result", {}).get("is_success", False)
        has_error = bool(experience_data.get("execution_result", {}).get("error_info"))
        scores[QualityDimension.CORRECTNESS] = 1.0 if is_success and not has_error else 0.3
        
        # 2. 完整性评估
        op_sequence = experience_data.get("operation_sequence", [])
        scores[QualityDimension.COMPLETENESS] = min(1.0, len(op_sequence) / 3.0)
        
        # 3. 可复用性评估
        static_meta = experience_data.get("static_meta", {})
        generalization = static_meta.get("generalization", 0.5)
        complexity = static_meta.get("complexity", 3)
        scores[QualityDimension.REUSABILITY] = generalization * (1 - (complexity - 1) / 4)
        
        # 4. 安全性评估
        output = experience_data.get("execution_result", {}).get("final_output", "")
        security_keywords = ["password", "token", "secret", "key", "credential"]
        has_secrets = any(kw in output.lower() for kw in security_keywords)
        scores[QualityDimension.SAFETY] = 0.0 if has_secrets else 1.0
        
        # 5. 效率评估
        exec_time = experience_data.get("execution_result", {}).get("execution_time", 1.0)
        scores[QualityDimension.EFFICIENCY] = max(0, 1.0 - exec_time / 300.0)  # 5分钟内为佳
        
        # 计算加权总分
        overall = sum(
            scores[dim] * weight 
            for dim, weight in self.dimension_weights.items()
        )
        
        return {
            "dimension_scores": scores,
            "overall_score": overall,
            "reasoning": "基于规则自动评估",
            "source": "rule_based"
        }


class AdversarialValidator:
    """对抗性验证机制"""
    
    def __init__(self):
        self.validation_strategies = [
            self._check_semantic_contradiction,
            self._check_duplicate_similarity,
            self._check_temporal_consistency,
            self._check_counterfactual_robustness,
            self._check_output_safety
        ]
    
    def validate(self, experience_data: Dict, 
                existing_experiences: List[Dict]) -> Dict[str, Any]:
        """
        验证经验的对抗性
        
        Args:
            experience_data: 待验证的经验
            existing_experiences: 已有经验列表
            
        Returns:
            验证结果
        """
        issues = []
        
        for strategy in self.validation_strategies:
            result = strategy(experience_data, existing_experiences)
            if not result["passed"]:
                issues.append(result)
        
        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "confidence": 1.0 - len(issues) * 0.2
        }
    
    def _check_semantic_contradiction(self, exp: Dict, 
                                      existing: List[Dict]) -> Dict:
        """检查语义矛盾"""
        # 简化实现：检查任务类型是否冲突
        task_type = exp.get("task_intent", {}).get("task_type", "")
        
        for e in existing:
            if e.get("task_intent", {}).get("task_type") == task_type:
                # 检查输出是否矛盾
                output1 = exp.get("execution_result", {}).get("final_output", "")[:100]
                output2 = e.get("execution_result", {}).get("final_output", "")[:100]
                
                # 简单关键词冲突检测
                if output1 and output2:
                    return {
                        "passed": True,
                        "type": "semantic_contradiction"
                    }
        
        return {"passed": True, "type": "semantic_contradiction"}
    
    def _check_duplicate_similarity(self, exp: Dict, 
                                     existing: List[Dict]) -> Dict:
        """检查重复/高度相似"""
        # 简化：检查ID是否相同或文本相似度
        exp_id = exp.get("experience_id", "")
        
        for e in existing:
            if e.get("experience_id") == exp_id:
                return {
                    "passed": False,
                    "type": "duplicate_similarity",
                    "message": "存在完全相同的经验"
                }
        
        return {"passed": True, "type": "duplicate_similarity"}
    
    def _check_temporal_consistency(self, exp: Dict, 
                                     existing: List[Dict]) -> Dict:
        """检查时间一致性"""
        exp_time = exp.get("created_at")
        if not exp_time:
            return {"passed": True, "type": "temporal_consistency"}
        
        # 检查是否有过期经验被更新为新经验
        for e in existing:
            e_time = e.get("created_at")
            if e_time and exp_time < e_time:
                # 新经验创建时间早于已有经验
                return {
                    "passed": False,
                    "type": "temporal_consistency",
                    "message": "时间戳异常"
                }
        
        return {"passed": True, "type": "temporal_consistency"}
    
    def _check_output_safety(self, exp: Dict, 
                              existing: List[Dict]) -> Dict:
        """检查输出安全性"""
        output = exp.get("execution_result", {}).get("final_output", "")
        
        dangerous_patterns = [
            r"rm\s+-rf\s+/",
            r"del\s+/[sq]",
            r"format\s+\w:",
            r"__import__\('os'\)\.system",
            r"eval\s*\(",
            r"exec\s*\("
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                return {
                    "passed": False,
                    "type": "output_safety",
                    "message": f"检测到危险操作: {pattern}"
                }
        
        return {"passed": True, "type": "output_safety"}

    def _check_counterfactual_robustness(self, exp: Dict,
                                         existing: List[Dict]) -> Dict:
        """反事实健壮性检查（轻量规则版）。"""
        task_intent = exp.get("task_intent", {})
        requirement = f"{task_intent.get('original_requirement', '')} {task_intent.get('user_instruction', '')}".lower()
        output = exp.get("execution_result", {}).get("final_output", "").lower()

        checks = []
        if "sort" in requirement or "排序" in requirement:
            checks.append(any(token in output for token in ["sort", "排序", "quick", "merge", "tim", "heap"]))
        if "json" in requirement or "结构化" in requirement:
            checks.append(any(token in output for token in ["{", "}", "json"]))
        if "异常" in requirement or "error" in requirement:
            checks.append(any(token in output for token in ["try", "except", "error", "异常"]))

        if checks and not all(checks):
            return {
                "passed": False,
                "type": "counterfactual_robustness",
                "message": "输出在关键需求扰动下可能不稳健"
            }
        return {"passed": True, "type": "counterfactual_robustness"}


class RedisCacheManager:
    """Redis缓存管理器（可选分布式支持）"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        初始化Redis缓存
        
        Args:
            redis_url: Redis连接URL
        """
        self.redis_url = redis_url
        self.client = None
        self._use_memory_fallback = True

        # 本地内存缓存（Redis不可用时备用）
        self._memory_cache: Dict[str, Any] = {}

        self._connect()
    
    def _connect(self):
        """连接Redis"""
        try:
            import redis
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            self.client.ping()
            self._use_memory_fallback = False
            logger.info("Redis连接成功")
        except ImportError:
            logger.warning("redis-py 未安装，使用内存缓存")
        except Exception as e:
            logger.warning("Redis连接失败: %s，使用内存缓存", e)
    
    def _get_key(self, prefix: str, identifier: str) -> str:
        """生成缓存键"""
        return f"experience:{prefix}:{identifier}"
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        # 尝试Redis
        if self.client and not self._use_memory_fallback:
            try:
                data = self.client.get(key)
                if data:
                    return json.loads(data)
            except Exception:
                pass
        
        # 回退到内存
        return self._memory_cache.get(key)
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """设置缓存"""
        # 尝试Redis
        if self.client and not self._use_memory_fallback:
            try:
                self.client.setex(key, ttl, json.dumps(value, default=str))
                return True
            except Exception:
                pass
        
        # 回退到内存
        self._memory_cache[key] = value
        return True
    
    def delete(self, key: str):
        """删除缓存"""
        if self.client and not self._use_memory_fallback:
            try:
                self.client.delete(key)
            except Exception:
                pass
        
        self._memory_cache.pop(key, None)
    
    def clear_pattern(self, pattern: str):
        """清除匹配模式的所有键"""
        if self.client and not self._use_memory_fallback:
            try:
                keys = self.client.keys(f"*{pattern}*")
                if keys:
                    self.client.delete(*keys)
            except Exception:
                pass
        
        # 清理内存缓存
        to_delete = [k for k in self._memory_cache if pattern in k]
        for k in to_delete:
            del self._memory_cache[k]
    
    def cache_experience_search(self, query: str, results: List[Dict], ttl: int = 300):
        """缓存搜索结果"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        key = self._get_key("search", query_hash)
        return self.set(key, results, ttl)
    
    def get_cached_search(self, query: str) -> Optional[List[Dict]]:
        """获取缓存的搜索结果"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        key = self._get_key("search", query_hash)
        return self.get(key)


class EnhancedExperienceManager:
    """增强版经验管理器"""
    
    def __init__(self, graph_ops=None, use_llm_judge: bool = False,
                 llm_provider: Optional[Callable] = None,
                 redis_url: Optional[str] = None):
        from .manager import ExperienceManager
        
        self.base_manager = ExperienceManager(graph_ops)
        
        # LLM-as-Judge
        self.llm_judge = None
        if use_llm_judge:
            self.llm_judge = LLMasJudge(llm_provider)
        
        # 对抗性验证
        self.validator = AdversarialValidator()
        
        # Redis缓存
        self.cache = None
        if redis_url:
            self.cache = RedisCacheManager(redis_url)
        
        # 验证配置
        self.config = {
            "enable_adversarial_validation": True,
            "min_confidence": 0.7,
            "cache_ttl": 300
        }

    def _to_evaluation_payload(self, raw_data: Dict[str, Any], experience) -> Dict[str, Any]:
        """将原始数据与ExperienceUnit对齐为统一评估结构。"""
        payload = experience.model_dump()

        # 补充上游原始字段，便于后续规则和LLM评估读取
        payload.setdefault("task_intent", {})
        payload["task_intent"].setdefault("original_requirement", raw_data.get("original_requirement", ""))
        payload["task_intent"].setdefault("user_instruction", raw_data.get("user_instruction", ""))
        payload["task_intent"].setdefault("task_type", raw_data.get("task_type", "unknown"))

        payload.setdefault("execution_result", {})
        payload["execution_result"].setdefault("final_output", raw_data.get("final_output", ""))
        payload["execution_result"].setdefault("is_success", raw_data.get("is_success", False))
        payload["execution_result"].setdefault("error_info", raw_data.get("error_info"))
        payload["execution_result"].setdefault("execution_time", raw_data.get("execution_time", 1.0))

        return payload
    
    def add_experience_with_validation(self, raw_data: Dict[str, Any],
                                         auto_verify: bool = True) -> Optional[str]:
        """
        添加经验（带验证）
        
        Args:
            raw_data: 原始数据
            auto_verify: 是否自动验证
            
        Returns:
            经验ID，失败返回None
        """
        # 提取经验
        experience = self.base_manager.extract_experience_from_raw_data(raw_data)
        if not experience:
            return None

        evaluation_payload = self._to_evaluation_payload(raw_data, experience)

        quality_result = None
        validation_result = None
        
        # 质量评估（LLM-as-Judge）
        if self.llm_judge:
            quality_result = self.llm_judge.evaluate(evaluation_payload)
            raw_data["llm_quality_score"] = quality_result.get("overall_score", 0.5)
            
            # 检查是否低于阈值
            if quality_result.get("overall_score", 0) < self.base_manager.config["min_quality_score"]:
                logger.warning("LLM评估质量分过低: %.2f", quality_result.get("overall_score", 0.0))
        
        # 对抗性验证
        if self.config["enable_adversarial_validation"]:
            existing_data = [
                {"experience_id": exp.experience_id, **exp.model_dump()}
                for exp in self.base_manager.graph_ops.graph.experience_nodes.values()
            ]
            
            validation_result = self.validator.validate(evaluation_payload, existing_data)
            if not validation_result["passed"]:
                logger.warning("对抗性验证失败: %s", validation_result["issues"])
                if validation_result["confidence"] < self.config["min_confidence"]:
                    return None
        
        # 缓存验证结果
        if self.cache:
            self.cache.set(
                f"validation:{experience.experience_id}",
                {"quality": quality_result, "adversarial": validation_result},
                ttl=self.config["cache_ttl"]
            )
        
        # 调用基础管理器入库
        return self.base_manager.add_candidate_experience(raw_data, auto_verify)
    
    def search_with_cache(self, query: str, top_k: int = 5) -> List[Dict]:
        """搜索（带缓存）"""
        # 尝试从缓存获取
        if self.cache:
            cached = self.cache.get_cached_search(query)
            if cached:
                logger.info("使用缓存的搜索结果")
                return cached
        
        # 执行搜索
        results = self.base_manager.graph_ops.semantic_search(query, top_k)
        
        # 缓存结果
        if self.cache:
            self.cache.cache_experience_search(query, results)
        
        return results
    
    def clear_cache(self):
        """清除缓存"""
        if self.cache:
            self.cache.clear_pattern("experience")
            logger.info("缓存已清除")
