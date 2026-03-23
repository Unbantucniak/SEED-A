from typing import List, Optional, Dict, Any
from datetime import datetime
from .model import ExperienceUnit, ExperienceGraph, ExperienceEdge
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.common.config import get_config_section

class GraphOperations:
    """经验图谱操作类"""
    def __init__(self, graph: Optional[ExperienceGraph] = None, config: Optional[Dict[str, Any]] = None):
        self.graph = graph or ExperienceGraph()
        cfg = config or get_config_section("experience_graph")
        self.similarity_threshold = float(cfg.get("similarity_threshold", 0.7))

        vectorizer_mode = str(cfg.get("vectorizer_mode", "char_wb")).lower()
        ngram_min = int(cfg.get("vectorizer_ngram_min", 2))
        ngram_max = int(cfg.get("vectorizer_ngram_max", 4))

        kwargs: Dict[str, Any] = {
            "lowercase": False,
            "ngram_range": (ngram_min, ngram_max),
        }
        if vectorizer_mode in {"char", "char_wb", "word"}:
            kwargs["analyzer"] = vectorizer_mode
        else:
            kwargs["analyzer"] = "char_wb"

        self.vectorizer = TfidfVectorizer(**kwargs)
        self._update_vectorizer()
    
    def _update_vectorizer(self):
        """更新TF-IDF向量器，用于语义搜索"""
        if len(self.graph.experience_nodes) == 0:
            return
        # 提取所有经验的任务意图文本用于向量化
        texts = [
            f"{exp.task_intent.original_requirement} {exp.task_intent.user_instruction}"
            for exp in self.graph.experience_nodes.values()
        ]
        self.vectorizer.fit(texts)
    
    def add_experience(self, experience: ExperienceUnit) -> str:
        """添加经验节点"""
        self.graph.experience_nodes[experience.experience_id] = experience
        self.graph.updated_at = datetime.now()
        self._update_vectorizer()
        # 自动计算与现有经验的相似度边
        self._auto_add_similarity_edges(experience.experience_id)
        return experience.experience_id
    
    def get_experience(self, experience_id: str) -> Optional[ExperienceUnit]:
        """获取经验节点"""
        return self.graph.experience_nodes.get(experience_id)
    
    def update_experience_dynamic_meta(self, experience_id: str, is_success: bool, benefit: float) -> bool:
        """更新经验的动态元属性"""
        exp = self.get_experience(experience_id)
        if not exp:
            return False
        
        # 更新动态属性
        meta = exp.dynamic_meta
        meta.use_count += 1
        meta.success_rate = (meta.success_rate * (meta.use_count - 1) + (1 if is_success else 0)) / meta.use_count
        meta.average_benefit = (meta.average_benefit * (meta.use_count - 1) + benefit) / meta.use_count
        exp.last_used_at = datetime.now()
        self.graph.updated_at = datetime.now()
        return True
    
    def delete_experience(self, experience_id: str) -> bool:
        """删除经验节点及关联的边"""
        if experience_id not in self.graph.experience_nodes:
            return False
        
        # 删除节点
        del self.graph.experience_nodes[experience_id]
        # 删除所有关联的边
        edges_to_delete = [
            edge_id for edge_id, edge in self.graph.edges.items()
            if edge.from_experience_id == experience_id or edge.to_experience_id == experience_id
        ]
        for edge_id in edges_to_delete:
            del self.graph.edges[edge_id]
        
        self.graph.updated_at = datetime.now()
        self._update_vectorizer()
        return True
    
    def add_edge(self, from_id: str, to_id: str, edge_type: str, weight: float = 0.5) -> Optional[str]:
        """添加边"""
        if from_id not in self.graph.experience_nodes or to_id not in self.graph.experience_nodes:
            return None

        safe_weight = max(0.0, min(1.0, float(weight)))
        
        edge = ExperienceEdge(
            from_experience_id=from_id,
            to_experience_id=to_id,
            edge_type=edge_type,
            weight=safe_weight
        )
        self.graph.edges[edge.edge_id] = edge
        self.graph.updated_at = datetime.now()
        return edge.edge_id
    
    def _auto_add_similarity_edges(self, new_exp_id: str):
        """自动为新添加的经验添加相似度边"""
        new_exp = self.get_experience(new_exp_id)
        if not new_exp or len(self.graph.experience_nodes) < 2:
            return
        
        # 计算新经验与所有其他经验的相似度
        new_text = f"{new_exp.task_intent.original_requirement} {new_exp.task_intent.user_instruction}"
        new_vec = self.vectorizer.transform([new_text])
        
        for exp_id, exp in self.graph.experience_nodes.items():
            if exp_id == new_exp_id:
                continue
            exp_text = f"{exp.task_intent.original_requirement} {exp.task_intent.user_instruction}"
            exp_vec = self.vectorizer.transform([exp_text])
            similarity = float(cosine_similarity(new_vec, exp_vec)[0][0])
            similarity = max(0.0, min(1.0, similarity))
            if similarity > self.similarity_threshold:
                self.add_edge(new_exp_id, exp_id, "similarity", similarity)
    
    def semantic_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """语义搜索相关经验"""
        if len(self.graph.experience_nodes) == 0:
            return []
        
        query_vec = self.vectorizer.transform([query])
        results = []
        
        for exp_id, exp in self.graph.experience_nodes.items():
            exp_text = f"{exp.task_intent.original_requirement} {exp.task_intent.user_instruction}"
            exp_vec = self.vectorizer.transform([exp_text])
            similarity = cosine_similarity(query_vec, exp_vec)[0][0]
            # 综合相似度、成功率、时效性计算综合得分
            score = similarity * 0.4 + exp.dynamic_meta.success_rate * 0.3 + exp.dynamic_meta.timeliness * 0.3
            results.append({
                "experience_id": exp_id,
                "experience": exp,
                "similarity": float(similarity),
                "composite_score": float(score)
            })
        
        # 按综合得分排序
        results.sort(key=lambda x: x["composite_score"], reverse=True)
        return results[:top_k]
    
    def get_related_experiences(self, experience_id: str, edge_types: Optional[List[str]] = None) -> List[Dict]:
        """获取关联经验"""
        if experience_id not in self.graph.experience_nodes:
            return []
        
        edge_types = edge_types or ["dependency", "similarity", "causality", "derivation"]
        related = []
        
        for edge in self.graph.edges.values():
            if edge.edge_type not in edge_types:
                continue
            if edge.from_experience_id == experience_id:
                related.append({
                    "experience_id": edge.to_experience_id,
                    "relation": edge.edge_type,
                    "weight": edge.weight
                })
            elif edge.to_experience_id == experience_id:
                related.append({
                    "experience_id": edge.from_experience_id,
                    "relation": f"reverse_{edge.edge_type}",
                    "weight": edge.weight
                })
        
        return related
    
    def update_timeliness(self):
        """批量更新所有经验的时效性"""
        current_time = datetime.now()
        for exp in self.graph.experience_nodes.values():
            # 简化的时效性计算：超过6个月时效性开始衰减，18个月后降为0
            days_since_created = (current_time - exp.created_at).days
            if days_since_created <= 180:
                exp.dynamic_meta.timeliness = 1.0
            elif days_since_created >= 540:
                exp.dynamic_meta.timeliness = 0.0
            else:
                exp.dynamic_meta.timeliness = 1 - (days_since_created - 180) / 360
        self.graph.updated_at = current_time
