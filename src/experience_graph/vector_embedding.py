"""
经验图谱向量嵌入模块
使用 sentence-transformers 实现语义嵌入，支持中英文
"""
from typing import List, Optional, Dict
import numpy as np
import logging
from datetime import datetime
from .model import ExperienceUnit, ExperienceGraph, ExperienceEdge


logger = logging.getLogger(__name__)


class VectorEmbedder:
    """向量嵌入器，支持多种嵌入模型"""
    
    def __init__(self, model_name: str = "BAAI/bge-base-zh-v1.5"):
        """
        初始化嵌入器
        
        Args:
            model_name: 模型名称，支持:
                - BAAI/bge-base-zh-v1.5 (中文增强)
                - BAAI/bge-base-en-v1.5 (英文)
                - sentence-transformers/all-MiniLM-L6-v2 (轻量)
        """
        self.model_name = model_name
        self.model = None
        self.dimension = 768  # 默认维度
        self._load_model()
    
    def _load_model(self):
        """加载嵌入模型"""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            print(f"✓ 嵌入模型加载成功: {self.model_name}, 维度: {self.dimension}")
        except ImportError:
            print("⚠ sentence-transformers 未安装，使用 TF-IDF 回退方案")
            self.model = None
        except Exception as e:
            print(f"⚠ 模型加载失败: {e}, 使用 TF-IDF 回退方案")
            self.model = None
    
    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        将文本编码为向量
        
        Args:
            texts: 文本列表
            batch_size: 批处理大小
            
        Returns:
            numpy.ndarray: 形状为 (len(texts), dimension) 的嵌入向量
        """
        if self.model is None:
            raise RuntimeError("嵌入模型未加载")
        
        embeddings = self.model.encode(texts, batch_size=batch_size, show_progress_bar=False)
        return embeddings
    
    def encode_single(self, text: str) -> np.ndarray:
        """编码单个文本"""
        return self.encode([text])[0]
    
    def compute_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的语义相似度"""
        emb1 = self.encode_single(text1)
        emb2 = self.encode_single(text2)
        # 余弦相似度
        return float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))
    
    def compute_similarities_batch(self, query: str, texts: List[str]) -> np.ndarray:
        """批量计算查询与文本列表的相似度"""
        if not texts:
            return np.array([])
        
        query_emb = self.encode_single(query)
        text_embs = self.encode(texts)
        
        # 批量计算余弦相似度
        similarities = np.dot(text_embs, query_emb) / (
            np.linalg.norm(text_embs, axis=1) * np.linalg.norm(query_emb)
        )
        return similarities


class HybridVectorStore:
    """混合向量存储，结合稠密向量和稀疏向量"""
    
    def __init__(self, graph_ops, embedder: Optional[VectorEmbedder] = None):
        """
        初始化混合向量存储
        
        Args:
            graph_ops: GraphOperations 实例
            embedder: VectorEmbedder 实例
        """
        self.graph_ops = graph_ops
        self.embedder = embedder or VectorEmbedder()
        
        # 缓存已计算的嵌入
        self._embedding_cache: Dict[str, np.ndarray] = {}
        
        # 是否使用混合模式
        self.use_hybrid = self.embedder.model is not None
    
    def _get_text_for_experience(self, exp: ExperienceUnit) -> str:
        """获取经验的可嵌入文本"""
        parts = [
            exp.task_intent.original_requirement,
            exp.task_intent.user_instruction,
            " ".join(exp.static_meta.domain_tags),
            " ".join(exp.constraints) if exp.constraints else ""
        ]
        return " ".join(filter(None, parts))
    
    def build_embeddings(self, force_rebuild: bool = False):
        """为所有经验构建嵌入向量"""
        if not self.use_hybrid:
            print("⚠ 嵌入模型不可用，跳过嵌入构建")
            return
        
        if not force_rebuild and self._embedding_cache:
            print("✓ 嵌入已缓存，使用现有嵌入")
            return
        
        print(f"开始为 {len(self.graph_ops.graph.experience_nodes)} 个经验构建嵌入...")
        
        exp_ids = list(self.graph_ops.graph.experience_nodes.keys())
        texts = [
            self._get_text_for_experience(
                self.graph_ops.graph.experience_nodes[exp_id]
            ) for exp_id in exp_ids
        ]
        
        if not texts:
            return
        
        embeddings = self.embedder.encode(texts)
        
        for exp_id, emb in zip(exp_ids, embeddings):
            self._embedding_cache[exp_id] = emb
        
        print(f"✓ 嵌入构建完成，缓存了 {len(self._embedding_cache)} 个嵌入")
    
    def add_embedding(self, experience_id: str):
        """为单个经验添加嵌入"""
        if not self.use_hybrid:
            return
        
        exp = self.graph_ops.get_experience(experience_id)
        if not exp:
            return
        
        text = self._get_text_for_experience(exp)
        self._embedding_cache[experience_id] = self.embedder.encode_single(text)
    
    def semantic_search_hybrid(self, query: str, top_k: int = 5, 
                                alpha: float = 0.7) -> List[Dict]:
        """
        混合语义搜索，结合稠密向量和TF-IDF
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            alpha: 稠密向量权重 (1-alpha 为 TF-IDF 权重)
            
        Returns:
            搜索结果列表
        """
        results = []
        
        if self.use_hybrid and self._embedding_cache:
            # 稠密向量搜索
            query_emb = self.embedder.encode_single(query)
            
            for exp_id, exp in self.graph_ops.graph.experience_nodes.items():
                if exp_id not in self._embedding_cache:
                    continue
                
                exp_emb = self._embedding_cache[exp_id]
                dense_sim = float(
                    np.dot(exp_emb, query_emb) / 
                    (np.linalg.norm(exp_emb) * np.linalg.norm(query_emb))
                )
                
                results.append({
                    "experience_id": exp_id,
                    "experience": exp,
                    "dense_similarity": dense_sim,
                    "similarity": dense_sim  # 统一字段
                })
        
        # 如果稠密向量不可用，使用 TF-IDF 回退
        if not results:
            return self.graph_ops.semantic_search(query, top_k)
        
        # 结合 TF-IDF 结果
        tfidf_results = {
            r["experience_id"]: r["similarity"] 
            for r in self.graph_ops.semantic_search(query, top_k=len(results))
        }
        
        for r in results:
            exp_id = r["experience_id"]
            tfidf_sim = tfidf_results.get(exp_id, 0.5)
            # 混合相似度
            r["hybrid_similarity"] = alpha * r["dense_similarity"] + (1 - alpha) * tfidf_sim
            r["similarity"] = r["hybrid_similarity"]
            exp = r["experience"]
            
            # 综合得分
            score = (
                r["hybrid_similarity"] * 0.4 +
                exp.dynamic_meta.success_rate * 0.3 +
                exp.dynamic_meta.timeliness * 0.3
            )
            r["composite_score"] = float(score)
        
        # 排序并返回
        results.sort(key=lambda x: x["composite_score"], reverse=True)
        return results[:top_k]


class GraphNeuralNetworkReasoner:
    """图神经网络关系推理模块（简化版）"""
    
    def __init__(self, graph_ops, embedder: Optional[VectorEmbedder] = None):
        self.graph_ops = graph_ops
        self.embedder = embedder
        self.edge_type_weights = {
            "similarity": 0.4,
            "dependency": 0.3,
            "causality": 0.2,
            "derivation": 0.1
        }
    
    def compute_relation_scores(self, source_exp_id: str, 
                                 target_exp_ids: List[str]) -> Dict[str, float]:
        """
        计算源经验到目标经验的关系推理得分
        
        Args:
            source_exp_id: 源经验ID
            target_exp_ids: 目标经验ID列表
            
        Returns:
            目标ID到推理得分的映射
        """
        source_exp = self.graph_ops.get_experience(source_exp_id)
        if not source_exp:
            return {}
        
        scores = {}
        
        for target_id in target_exp_ids:
            if target_id == source_exp_id:
                continue
            
            target_exp = self.graph_ops.get_experience(target_id)
            if not target_exp:
                continue
            
            # 1. 通过边权重传播
            edge_score = 0.0
            related = self.graph_ops.get_related_experiences(
                source_exp_id, 
                edge_types=list(self.edge_type_weights.keys())
            )
            
            for rel in related:
                if rel["experience_id"] == target_id:
                    edge_type = rel["relation"].replace("reverse_", "")
                    edge_score = rel["weight"] * self.edge_type_weights.get(edge_type, 0.1)
                    break
            
            # 2. 语义相似度增强
            semantic_score = 0.0
            if self.embedder and self.embedder.model:
                try:
                    source_text = f"{source_exp.task_intent.original_requirement} {source_exp.task_intent.user_instruction}"
                    target_text = f"{target_exp.task_intent.original_requirement} {target_exp.task_intent.user_instruction}"
                    semantic_score = self.embedder.compute_similarity(source_text, target_text)
                except (RuntimeError, ValueError, TypeError) as exc:
                    logger.debug("语义相似度增强失败，回退到边权推理: %s", exc)
            
            # 3. 综合推理得分
            total_score = edge_score * 0.6 + semantic_score * 0.4
            scores[target_id] = float(total_score)
        
        return scores
    
    def recommend_reasoning_chain(self, start_exp_id: str, 
                                   max_depth: int = 3, 
                                   top_k: int = 5) -> List[List[str]]:
        """
        推荐推理链路径
        
        Args:
            start_exp_id: 起始经验ID
            max_depth: 最大推理深度
            top_k: 每层最多保留节点数
            
        Returns:
            推理链列表，每条链是一个经验ID序列
        """
        chains = []
        
        def dfs(current_id: str, chain: List[str], depth: int):
            if depth >= max_depth:
                chains.append(chain.copy())
                return
            
            related = self.graph_ops.get_related_experiences(current_id)
            if not related:
                chains.append(chain.copy())
                return
            
            # 按权重排序
            related.sort(key=lambda x: x["weight"], reverse=True)
            
            # 扩展每条链
            for rel in related[:top_k]:
                next_id = rel["experience_id"]
                if next_id not in chain:  # 避免循环
                    chain.append(next_id)
                    dfs(next_id, chain, depth + 1)
                    chain.pop()
        
        dfs(start_exp_id, [start_exp_id], 0)
        
        # 按链长度和总权重排序
        chains.sort(key=lambda x: len(x), reverse=True)
        return chains[:10]


# 便捷函数
def create_enhanced_graph_ops(graph: Optional[ExperienceGraph] = None,
                                model_name: str = "BAAI/bge-base-zh-v1.5") -> tuple:
    """
    创建增强版图谱操作对象
    
    Returns:
        (GraphOperations, HybridVectorStore, VectorEmbedder)
    """
    from .operations import GraphOperations
    
    graph_ops = GraphOperations(graph)
    embedder = VectorEmbedder(model_name)
    vector_store = HybridVectorStore(graph_ops, embedder)
    
    return graph_ops, vector_store, embedder
