"""
AutoGen Agent 基线方案
基于 AutoGen 实现的多智能体软件系统
"""
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from autogen import ConversableAgent, AssistantAgent, UserProxyAgent
from autogen.agentchat import GroupChat, GroupChatManager
import json


@dataclass
class AutoGenAgentResult:
    """AutoGen Agent 执行结果"""
    success: bool
    output: str
    steps: int
    agents_used: List[str]
    error: Optional[str] = None


class AutoGenBaseline:
    """基于 AutoGen 的多智能体基线"""
    
    def __init__(
        self,
        model_name: str = "gpt-4",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.7
    ):
        self.model_name = model_name
        self.llm_config = {
            "model": model_name,
            "api_key": api_key,
            "base_url": base_url,
            "temperature": temperature
        }
        self.agents = {}
        self.group_chat = None
        self._create_agents()
    
    def _create_agents(self):
        """创建多智能体系统"""
        
        # 代码助手 Agent
        self.agents["coder"] = AssistantAgent(
            name="coder",
            llm_config=self.llm_config,
            system_message="""你是一个专业的程序员。
擅长各种编程语言的代码编写、调试和优化。
请根据需求编写高质量的代码。"""
        )
        
        # 代码审查 Agent
        self.agents["reviewer"] = AssistantAgent(
            name="reviewer",
            llm_config=self.llm_config,
            system_message="""你是一个资深的代码审查专家。
擅长发现代码中的问题、漏洞和性能问题。
请仔细审查代码并提出改进建议。"""
        )
        
        # 测试 Agent
        self.agents["tester"] = AssistantAgent(
            name="tester",
            llm_config=self.llm_config,
            system_message="""你是一个测试工程师。
擅长编写各种类型的测试，包括单元测试、集成测试和端到端测试。
请为代码编写全面的测试用例。"""
        )
        
        # 用户代理 Agent
        self.agents["user_proxy"] = UserProxyAgent(
            name="user_proxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=10
        )
        
        # 创建群聊
        self.group_chat = GroupChat(
            agents=[
                self.agents["coder"],
                self.agents["reviewer"],
                self.agents["tester"]
            ],
            speaker_selection_method="round_robin",
            allow_repeat_speaker=False
        )
        
        # 创建管理器
        self.manager = GroupChatManager(
            groupchat=self.group_chat,
            llm_config=self.llm_config
        )
    
    def execute(self, task: str) -> AutoGenAgentResult:
        """执行任务"""
        try:
            # 使用群聊执行任务
            chat_result = self.agents["user_proxy"].initiate_chat(
                self.manager,
                message=task,
                summary_method="reflection_with_llm"
            )
            
            # 提取结果
            output = ""
            steps = 0
            
            if chat_result and hasattr(chat_result, 'chat_history'):
                steps = len(chat_result.chat_history)
                output = chat_summary = ""
                if hasattr(chat_result, 'summary'):
                    output = chat_result.summary
            
            return AutoGenAgentResult(
                success=True,
                output=output,
                steps=steps,
                agents_used=["coder", "reviewer", "tester"]
            )
            
        except Exception as e:
            return AutoGenAgentResult(
                success=False,
                output="",
                steps=0,
                agents_used=[],
                error=str(e)
            )
    
    def execute_with_strategy(self, task: str, strategy: str) -> AutoGenAgentResult:
        """使用指定策略执行任务"""
        
        if strategy == "coder_only":
            # 仅使用 coder
            try:
                result = self.agents["user_proxy"].initiate_chat(
                    self.agents["coder"],
                    message=task
                )
                return AutoGenAgentResult(
                    success=True,
                    output=result.summary if hasattr(result, 'summary') else "",
                    steps=len(result.chat_history) if hasattr(result, 'chat_history') else 0,
                    agents_used=["coder"]
                )
            except Exception as e:
                return AutoGenAgentResult(
                    success=False, output="", steps=0, agents_used=["coder"], error=str(e)
                )
        
        elif strategy == "coder_reviewer":
            # coder + reviewer
            try:
                c_result = self.agents["user_proxy"].initiate_chat(
                    self.agents["coder"],
                    message=task
                )
                code = c_result.summary if hasattr(c_result, 'summary') else ""
                
                r_result = self.agents["user_proxy"].initiate_chat(
                    self.agents["reviewer"],
                    message=f"请审查以下代码:\n{code}"
                )
                
                return AutoGenAgentResult(
                    success=True,
                    output=f"Code:\n{code}\n\nReview:\n{r_result.summary if hasattr(r_result, 'summary') else ''}",
                    steps=len(c_result.chat_history) + len(r_result.chat_history),
                    agents_used=["coder", "reviewer"]
                )
            except Exception as e:
                return AutoGenAgentResult(
                    success=False, output="", steps=0, agents_used=["coder", "reviewer"], error=str(e)
                )
        
        else:
            # 默认使用群聊
            return self.execute(task)
    
    def reset(self):
        """重置所有 Agent 状态"""
        for agent in self.agents.values():
            if hasattr(agent, 'chat_messages'):
                agent.chat_messages.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "type": "autogen_multi_agent",
            "model": self.model_name,
            "agents_count": len(self.agents),
            "agent_names": list(self.agents.keys())
        }


def create_autogen_baseline(config: Optional[Dict[str, Any]] = None) -> AutoGenBaseline:
    """创建 AutoGen 基线实例"""
    config = config or {}
    return AutoGenBaseline(
        model_name=config.get("model", "gpt-4"),
        api_key=config.get("api_key"),
        base_url=config.get("base_url"),
        temperature=config.get("temperature", 0.7)
    )
