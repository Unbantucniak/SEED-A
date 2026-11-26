from typing import List, Optional, Dict, Any
from datetime import datetime
from .model import ExperienceUnit, ExperienceGraph, ExperienceEdge
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.common.config import get_config_section

try:
    from .vector_embedding import VectorEmbedder
except Exception:
    VectorEmbedder = None

class GraphOperations:
    """经验图谱操作类"""
    def __init__(self, graph: Optional[ExperienceGraph] = None, config: Optional[Dict[str, Any]] = None):
        self.graph = graph or ExperienceGraph()
        cfg = config or get_config_section("experience_graph")
        self.similarity_threshold = float(cfg.get("similarity_threshold", 0.7))
        self.retrieval_min_similarity = max(
            0.0,
            min(1.0, float(cfg.get("retrieval_min_similarity", 0.18))),
        )
        self.max_experience_count = int(cfg.get("max_experience_count", 100000))
        if self.max_experience_count < 1:
            raise ValueError("max_experience_count must be positive")
        self.auto_add_similarity_edges = bool(cfg.get("auto_add_similarity_edges", True))
        self.embedding_model = str(cfg.get("embedding_model", "BAAI/bge-base-zh-v1.5"))
        self.use_hybrid_retrieval = bool(cfg.get("use_hybrid_retrieval", True))
        self.dense_weight = max(0.0, min(1.0, float(cfg.get("dense_weight", 0.7))))

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
        self.embedder = None
        if self.use_hybrid_retrieval and VectorEmbedder is not None:
            try:
                self.embedder = VectorEmbedder(self.embedding_model)
            except Exception:
                self.embedder = None
        self._update_vectorizer()

    @staticmethod
    def _exp_text(exp: ExperienceUnit) -> str:
        tags = " ".join(exp.static_meta.domain_tags or [])
        return (
            f"{exp.task_intent.original_requirement} "
            f"{exp.task_intent.user_instruction} {tags}"
        ).strip()
    
    def _update_vectorizer(self):
        """更新TF-IDF向量器，用于语义搜索"""
        if len(self.graph.experience_nodes) == 0:
            return
        # 提取所有经验的任务意图文本用于向量化
        texts = [
            self._exp_text(exp)
            for exp in self.graph.experience_nodes.values()
        ]
        self.vectorizer.fit(texts)
    
    def add_experience(self, experience: ExperienceUnit) -> str:
        """添加经验节点"""
        self.add_experiences_batch([experience])
        return experience.experience_id

    def add_experiences_batch(self, experiences: List[ExperienceUnit], auto_link: Optional[bool] = None) -> List[str]:
        """批量写入，返回最终保留的唯一ID；超大批次保留最后的容量项。

        同一ID最后一次出现优先，替换已有节点不额外占用容量。批次中的
        保留项优先，其余旧节点按创建时间淘汰；删除仍沿用现有物理删除语义。
        """
        if not experiences:
            return []

        unique = {}
        for experience in experiences:
            # Move replacements to their last occurrence, including batch overflow.
            unique.pop(experience.experience_id, None)
            unique[experience.experience_id] = experience
        retained = list(unique.values())[-self.max_experience_count:]
        retained_ids = {experience.experience_id for experience in retained}
        changed_text_ids = {
            experience.experience_id for experience in retained
            if experience.experience_id in self.graph.experience_nodes
            and self._exp_text(self.graph.experience_nodes[experience.experience_id]) != self._exp_text(experience)
        }
        target_size = len(set(self.graph.experience_nodes) | retained_ids)
        while target_size > self.max_experience_count:
            oldest_exp_id = min(
                (identifier for identifier in self.graph.experience_nodes if identifier not in retained_ids),
                key=lambda exp_id: self.graph.experience_nodes[exp_id].created_at,
            )
            self.delete_experience(oldest_exp_id)
            target_size -= 1

        exp_ids: List[str] = []
        for exp in retained:
            self.graph.experience_nodes[exp.experience_id] = exp
            exp_ids.append(exp.experience_id)

        self.graph.updated_at = datetime.now()
        self._update_vectorizer()

        should_auto_link = self.auto_add_similarity_edges if auto_link is None else auto_link
        if should_auto_link:
            for exp_id in exp_ids:
                self._auto_add_similarity_edges(exp_id)
        elif changed_text_ids:
            # A disabled builder must not leave relations based on replaced text.
            # Explicit dependency/causality/derivation evidence is separate.
            obsolete = [edge_id for edge_id, edge in self.graph.edges.items()
                        if edge.edge_type == "similarity" and
                        (edge.from_experience_id in changed_text_ids or edge.to_experience_id in changed_text_ids)]
            for edge_id in obsolete:
                del self.graph.edges[edge_id]

        return exp_ids
    
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
        """刷新该节点的当前文本相似关系，每对节点至多保留一条相似边。

        未涉及节点之间的边保留其更新时间对应的历史分数；这不是全图重算。
        其他类型的显式来源/依赖关系不因文本重算而被删除。
        """
        new_exp = self.get_experience(new_exp_id)
        if not new_exp:
            return

        # 一次性向量化所有文本，避免逐条 transform 的重复开销。
        exp_ids = list(self.graph.experience_nodes.keys())
        texts = [
            self._exp_text(self.graph.experience_nodes[exp_id])
            for exp_id in exp_ids
        ]
        vectors = self.vectorizer.transform(texts)

        new_idx = exp_ids.index(new_exp_id)
        similarities = cosine_similarity(vectors[new_idx], vectors)[0]

        desired = {}
        for idx, exp_id in enumerate(exp_ids):
            if exp_id == new_exp_id:
                continue
            similarity = max(0.0, min(1.0, float(similarities[idx])))
            if similarity > self.similarity_threshold:
                desired[exp_id] = similarity

        existing = {}
        for edge_id, edge in self.graph.edges.items():
            if edge.edge_type != "similarity":
                continue
            if edge.from_experience_id == new_exp_id:
                other = edge.to_experience_id
            elif edge.to_experience_id == new_exp_id:
                other = edge.from_experience_id
            else:
                continue
            existing.setdefault(other, []).append(edge_id)

        now = datetime.now()
        for other, edge_ids in existing.items():
            keep = edge_ids[0] if other in desired else None
            for edge_id in edge_ids:
                if edge_id != keep:
                    del self.graph.edges[edge_id]
            if keep is not None:
                edge = self.graph.edges[keep]
                edge.weight = desired[other]
                edge.updated_at = now
        for other, similarity in desired.items():
            if other not in existing:
                self.add_edge(new_exp_id, other, "similarity", similarity)
        self.graph.updated_at = now
    
    def semantic_search(self, query: str, top_k: int = 5, *, include_inactive: bool = False) -> List[Dict]:
        """语义搜索相关经验"""
        if len(self.graph.experience_nodes) == 0:
            return []

        exp_ids = list(self.graph.experience_nodes.keys())
        texts = [self._exp_text(self.graph.experience_nodes[exp_id]) for exp_id in exp_ids]

        sparse_vectors = self.vectorizer.transform(texts)
        sparse_query = self.vectorizer.transform([query])
        sparse_sim = cosine_similarity(sparse_query, sparse_vectors)[0]

        dense_sim = None
        if self.embedder and self.embedder.model is not None:
            try:
                dense_sim = self.embedder.compute_similarities_batch(query, texts)
                if len(dense_sim) != len(exp_ids):
                    dense_sim = None
            except Exception:
                dense_sim = None

        results = []
        from src.experience_manager.lifecycle_policy import is_active
        for idx, exp_id in enumerate(exp_ids):
            exp = self.graph.experience_nodes[exp_id]
            if not include_inactive and not is_active(exp):
                continue
            sparse_score = max(0.0, min(1.0, float(sparse_sim[idx])))
            if dense_sim is not None:
                dense_score = max(0.0, min(1.0, float(dense_sim[idx])))
                similarity = self.dense_weight * dense_score + (1.0 - self.dense_weight) * sparse_score
            else:
                similarity = sparse_score

            # 综合相似度、成功率、时效性计算综合得分
            score = similarity * 0.4 + exp.dynamic_meta.success_rate * 0.3 + exp.dynamic_meta.timeliness * 0.3
            if similarity < self.retrieval_min_similarity:
                continue
            results.append({
                "experience_id": exp_id,
                "experience": exp,
                "similarity": float(similarity),
                "sparse_similarity": float(sparse_score),
                "dense_similarity": float(max(0.0, min(1.0, float(dense_sim[idx])))) if dense_sim is not None else None,
                "composite_score": float(score)
            })
        
        # 只在通过语义门槛后按综合得分排序。成功率和时效性不能把
        # 语义无关的经验“救”回检索结果，否则 RAG 会稳定注入噪声。
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
