"""
路由引擎增强模块
- 在线学习机制（真正的实时强化学习）
- 多模态任务支持（图像、语音）
"""
from typing import List, Dict, Optional, Any, Union
from enum import Enum
from datetime import datetime
import ast
import numpy as np
import json
import os


class ModalityType(Enum):
    """任务模态类型"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    MULTIMODAL = "multimodal"


class TaskFeatureExtractor:
    """任务特征提取器，支持多模态"""
    
    def __init__(self):
        self.image_encoder = None
        self.audio_encoder = None
    
    def extract_modality(self, task_info: Dict[str, Any]) -> ModalityType:
        """识别任务模态"""
        # 通过字段判断
        if "image_data" in task_info or "image_url" in task_info:
            return ModalityType.IMAGE
        elif "audio_data" in task_info or "audio_url" in task_info:
            return ModalityType.AUDIO
        elif "video_data" in task_info or "video_url" in task_info:
            return ModalityType.VIDEO
        elif "modalities" in task_info and len(task_info["modalities"]) > 1:
            return ModalityType.MULTIMODAL
        return ModalityType.TEXT
    
    def extract_text_features(self, text: str) -> Dict[str, Any]:
        """提取文本特征"""
        words = text.split()
        return {
            "text_length": len(text),
            "word_count": len(words),
            "has_code": any(char in text for char in ['{', '}', 'def ', 'class ', 'import ']),
            "has_url": 'http' in text.lower(),
            "language": self._detect_language(text)
        }
    
    def _detect_language(self, text: str) -> str:
        """简单语言检测"""
        if any('\u4e00' <= c <= '\u9fff' for c in text):
            return "zh"
        return "en"
    
    def extract_image_features(self, image_data: Any) -> Dict[str, Any]:
        """提取图像特征"""
        # 简化实现，实际应使用视觉模型
        return {
            "modality": "image",
            "has_visual_content": True
        }
    
    def extract_audio_features(self, audio_data: Any) -> Dict[str, Any]:
        """提取音频特征"""
        return {
            "modality": "audio",
            "has_audio_content": True
        }
    
    def extract_features(self, task_info: Dict[str, Any]) -> Dict[str, Any]:
        """综合提取任务特征"""
        modality = self.extract_modality(task_info)
        
        features = {
            "task_type": task_info.get("task_type", "unknown"),
            "domain_tags": task_info.get("domain_tags", []),
            "complexity": task_info.get("complexity", 3),
            "historical_frequency": task_info.get("historical_frequency", 0),
            "expected_benefit": task_info.get("expected_benefit", 1.0),
            "urgency": task_info.get("urgency", 0.5),
            "modality": modality.value
        }
        
        # 文本特征
        if "original_requirement" in task_info:
            text_features = self.extract_text_features(task_info["original_requirement"])
            features.update(text_features)
        
        return features


class ReinforcementLearningOptimizer:
    """强化学习优化器 - 真正的在线学习"""
    
    def __init__(self, state_dim: int = 10, action_dim: int = 4,
                 learning_rate: float = 0.01, gamma: float = 0.95,
                 epsilon: float = 0.1):
        """
        初始化强化学习优化器
        
        Args:
            state_dim: 状态空间维度
            action_dim: 动作空间维度（策略数量）
            learning_rate: 学习率
            gamma: 折扣因子
            epsilon: 探索率
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.lr = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon
        
        # Q表：状态-动作价值函数
        self.q_table: Dict[tuple, np.ndarray] = {}
        
        # 经验回放缓冲区
        self.replay_buffer: List[Dict] = []
        self.max_buffer_size = 1000
        
        # 训练统计
        self.episode_count = 0
        self.total_reward = 0.0
        
        # 保存路径
        self.save_dir = "models/routing_rl"
        os.makedirs(self.save_dir, exist_ok=True)
    
    def _get_state_key(self, features: Dict[str, Any]) -> tuple:
        """将特征转换为离散状态键"""
        # 简化的状态离散化
        key_parts = [
            int(features.get("complexity", 3)),
            int(features.get("historical_frequency", 0) / 10),
            int(features.get("expected_benefit", 0.5) * 2),
            int(features.get("urgency", 0.5) * 2),
            hash(features.get("task_type", "unknown")) % 100
        ]
        return tuple(key_parts)
    
    def _get_q_values(self, state_key: tuple) -> np.ndarray:
        """获取或初始化Q值"""
        if state_key not in self.q_table:
            self.q_table[state_key] = np.random.randn(self.action_dim) * 0.1
        return self.q_table[state_key]
    
    def select_action(self, state_features: Dict[str, Any], 
                      exploit_only: bool = False) -> int:
        """
        选择动作（策略）
        
        Args:
            state_features: 状态特征
            exploit_only: 是否只利用（不探索）
            
        Returns:
            选择的动作索引
        """
        state_key = self._get_state_key(state_features)
        q_values = self._get_q_values(state_key)
        
        # ε-greedy 策略
        if not exploit_only and np.random.random() < self.epsilon:
            return np.random.randint(self.action_dim)
        
        return int(np.argmax(q_values))
    
    def store_transition(self, state: Dict, action: int, 
                         reward: float, next_state: Dict, done: bool):
        """存储转移经验"""
        experience = {
            "state": state,
            "action": action,
            "reward": reward,
            "next_state": next_state,
            "done": done
        }
        
        self.replay_buffer.append(experience)
        if len(self.replay_buffer) > self.max_buffer_size:
            self.replay_buffer.pop(0)
    
    def update(self, batch_size: int = 32) -> float:
        """从经验回放中学习"""
        if len(self.replay_buffer) < batch_size:
            return 0.0
        
        # 随机采样
        indices = np.random.choice(len(self.replay_buffer), batch_size, replace=False)
        batch = [self.replay_buffer[i] for i in indices]
        
        total_loss = 0.0
        
        for exp in batch:
            state_key = self._get_state_key(exp["state"])
            next_state_key = self._get_state_key(exp["next_state"])
            
            # 当前Q值
            current_q = self._get_q_values(state_key)[exp["action"]]
            
            # 目标Q值 (TD目标)
            next_q_values = self._get_q_values(next_state_key)
            target_q = exp["reward"] + self.gamma * np.max(next_q_values) * (1 - exp["done"])
            
            # TD误差更新
            td_error = target_q - current_q
            self.q_table[state_key][exp["action"]] += self.lr * td_error
            
            total_loss += abs(td_error)
        
        return total_loss / batch_size
    
    def compute_reward(self, actual_success: bool, expected_benefit: float,
                       actual_benefit: float, response_time: float) -> float:
        """
        计算奖励
        
        Args:
            actual_success: 实际是否成功
            expected_benefit: 预期收益
            actual_benefit: 实际收益
            response_time: 响应时间
            
        Returns:
            奖励值
        """
        # 基础奖励：成功为正，失败为负
        base_reward = 1.0 if actual_success else -0.5
        
        # 收益奖励：实际/预期收益比
        benefit_ratio = min(actual_benefit / max(expected_benefit, 0.1), 2.0)
        benefit_reward = (benefit_ratio - 1.0) * 0.5  # 偏离1.0的惩罚
        
        # 速度奖励：响应越快越好
        speed_reward = max(0, 1.0 - response_time / 60.0) * 0.2  # 60秒内有效
        
        return base_reward + benefit_reward + speed_reward
    
    def train_step(self, state: Dict, action: int, 
                   actual_success: bool, expected_benefit: float,
                   actual_benefit: float, response_time: float,
                   next_state: Optional[Dict] = None) -> float:
        """单步训练"""
        # 计算奖励
        reward = self.compute_reward(actual_success, expected_benefit, 
                                     actual_benefit, response_time)
        
        # 下一状态（如果没有提供，使用当前状态作为结束）
        done = next_state is None
        if next_state is None:
            next_state = state.copy()
            next_state["historical_frequency"] += 1
        
        # 存储经验
        self.store_transition(state, action, reward, next_state, done=done)
        
        # 更新Q表
        loss = self.update()
        
        # 更新统计
        self.total_reward += reward
        self.episode_count += 1
        
        # 逐渐降低探索率
        self.epsilon = max(0.01, self.epsilon * 0.995)
        
        return reward
    
    def get_policy_weights(self) -> Dict[str, float]:
        """从Q表提取策略权重"""
        # 简化：从Q表平均值推断权重
        if not self.q_table:
            return {}

        avg_q = np.mean(np.stack(list(self.q_table.values())), axis=0)
        strategies = ["RAG_RETRIEVAL", "TEMPLATE_REUSE", "PROMPT_ENGINEERING", "FINE_TUNING"]
        
        weights = {}
        for i, s in enumerate(strategies):
            weights[s.lower()] = max(0.0, float(avg_q[i]))
        
        # 归一化
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        else:
            uniform = 1.0 / len(strategies)
            weights = {s.lower(): uniform for s in strategies}
        
        return weights
    
    def save_model(self, path: Optional[str] = None):
        """保存模型"""
        path = path or os.path.join(self.save_dir, "q_table.json")
        
        # 转换numpy数组为列表
        serializable = {
            str(k): v.tolist() for k, v in self.q_table.items()
        }
        
        with open(path, 'w') as f:
            json.dump({
                "q_table": serializable,
                "epsilon": self.epsilon,
                "episode_count": self.episode_count
            }, f)
        print(f"✓ 模型已保存到 {path}")
    
    def load_model(self, path: Optional[str] = None) -> bool:
        """加载模型"""
        path = path or os.path.join(self.save_dir, "q_table.json")
        
        if not os.path.exists(path):
            print(f"⚠ 模型文件不存在: {path}")
            return False
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            self.q_table = {
                tuple(ast.literal_eval(k)): np.array(v) for k, v in data["q_table"].items()
            }
            self.epsilon = data.get("epsilon", 0.1)
            self.episode_count = data.get("episode_count", 0)
            
            print(f"✓ 模型已加载，共 {len(self.q_table)} 个状态")
            return True
        except Exception as e:
            print(f"⚠ 模型加载失败: {e}")
            return False


class EnhancedRoutingEngine:
    """增强版路由引擎 - 集成在线学习和多模态支持"""
    
    def __init__(self, graph_ops=None, use_rl: bool = True):
        from .routing import RoutingEngine, StrategyType
        
        self.base_engine = RoutingEngine(graph_ops)
        self.feature_extractor = TaskFeatureExtractor()
        
        # 强化学习优化器
        self.rl_optimizer = None
        if use_rl:
            self.rl_optimizer = ReinforcementLearningOptimizer()
        
        # 策略类型映射
        self.strategy_types = list(StrategyType)
        
        # 模态配置
        self.modality_config = {
            ModalityType.TEXT: {
                "supported_strategies": ["RAG_RETRIEVAL", "TEMPLATE_REUSE", 
                                        "PROMPT_ENGINEERING", "FINE_TUNING"]
            },
            ModalityType.IMAGE: {
                "supported_strategies": ["RAG_RETRIEVAL", "PROMPT_ENGINEERING"]
            },
            ModalityType.AUDIO: {
                "supported_strategies": ["RAG_RETRIEVAL", "PROMPT_ENGINEERING"]
            },
            ModalityType.VIDEO: {
                "supported_strategies": ["RAG_RETRIEVAL", "PROMPT_ENGINEERING"]
            },
            ModalityType.MULTIMODAL: {
                "supported_strategies": ["RAG_RETRIEVAL", "PROMPT_ENGINEERING"]
            }
        }
    
    def route(self, task_info: Dict[str, Any],
              system_status: Optional[Dict[str, Any]] = None,
              use_rl: bool = True) -> Dict[str, Any]:
        """
        路由决策
        
        Args:
            task_info: 任务信息
            system_status: 系统状态
            use_rl: 是否使用强化学习
        """
        # 提取特征
        features = self.feature_extractor.extract_features(task_info)
        modality = features["modality"]
        
        # 获取支持的策略
        supported = self.modality_config[ModalityType(modality)]["supported_strategies"]
        
        if use_rl and self.rl_optimizer:
            # 使用强化学习选择策略
            action_idx = self.rl_optimizer.select_action(features)
            strategy = self.strategy_types[action_idx]
        else:
            # 使用基础引擎
            result = self.base_engine.route(task_info, system_status)
            return result
        
        # 调用基础引擎获取匹配经验
        matched = self.base_engine.get_matched_experiences(task_info)
        
        return {
            "selected_strategy": strategy.value,
            "modality": modality,
            "task_features": features,
            "matched_experiences": matched,
            "timestamp": datetime.now().isoformat()
        }
    
    def update_with_outcome(self, routing_result: Dict[str, Any],
                           actual_success: bool,
                           actual_benefit: float,
                           response_time: float) -> bool:
        """
        根据实际结果更新模型
        
        Args:
            routing_result: 路由结果
            actual_success: 是否成功
            actual_benefit: 实际收益
            response_time: 响应时间
            
        Returns:
            是否更新成功
        """
        if not self.rl_optimizer:
            return False
        
        # 找到对应的策略索引
        strategy_value = routing_result.get("selected_strategy", "")
        action_idx = 0
        for i, s in enumerate(self.strategy_types):
            if s.value == strategy_value:
                action_idx = i
                break
        
        state = routing_result.get("task_features", {})
        
        # 训练更新
        reward = self.rl_optimizer.train_step(
            state=state,
            action=action_idx,
            actual_success=actual_success,
            expected_benefit=state.get("expected_benefit", 1.0),
            actual_benefit=actual_benefit,
            response_time=response_time
        )
        
        return True
    
    def get_optimized_weights(self) -> Dict[str, float]:
        """获取优化后的策略权重"""
        if self.rl_optimizer:
            return self.rl_optimizer.get_policy_weights()
        return self.base_engine.strategy_weights
    
    def save(self):
        """保存模型"""
        if self.rl_optimizer:
            self.rl_optimizer.save_model()
    
    def load(self) -> bool:
        """加载模型"""
        if self.rl_optimizer:
            return self.rl_optimizer.load_model()
        return False
