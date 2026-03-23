"""
基于 LangChain 的 Agent 基线实现
用于与项目Agent进行对比评测
"""
from typing import Dict, Any, Tuple, List, Optional
import time
import json
from datetime import datetime

# LangChain 核心组件
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

# 工具定义
from langchain.tools import Tool

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from experiments.baselines.base_baseline import BaseBaseline
from experiments.benchmarks.task_dataset import EvaluationTask, TaskType


class LangChainAgentBaseline(BaseBaseline):
    """基于 LangChain 的 Agent 基线"""
    
    def __init__(self, name: str = "LangChain Agent", config: Dict[str, Any] = None):
        super().__init__(name, config)
        
        # 配置参数
        self.model_name = config.get("model_name", "gpt-3.5-turbo") if config else "gpt-3.5-turbo"
        self.temperature = config.get("temperature", 0.7) if config else 0.7
        self.max_iterations = config.get("max_iterations", 10) if config else 10
        
        # 初始化 LLM
        self.llm = None
        self.agent_executor = None
        self._initialize_agent()
    
    def _initialize_agent(self) -> None:
        """初始化 LangChain Agent"""
        try:
            # 初始化 ChatOpenAI
            self.llm = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                api_key=os.getenv("OPENAI_API_KEY", "sk-test-key")
            )
            
            # 定义工具
            tools = self._create_tools()
            
            # 创建 Prompt 模板
            prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content=self._get_system_prompt()),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                HumanMessage(content="{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])
            
            # 创建 Agent
            agent = create_openai_functions_agent(
                llm=self.llm,
                prompt=prompt,
                tools=tools
            )
            
            # 创建 AgentExecutor
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                max_iterations=self.max_iterations,
                verbose=True,
                handle_parsing_errors=True
            )
            
            print(f"[LangChain Agent] Initialized with model: {self.model_name}")
            
        except Exception as e:
            print(f"[LangChain Agent] Initialization error: {e}")
            self.llm = None
            self.agent_executor = None
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个专业的编程助手，擅长解决各种编程问题。

你需要根据用户的需求：
1. 如果是代码生成任务：生成高质量、可运行的代码
2. 如果是Bug修复任务：分析问题并提供修复方案
3. 如果是需求分解任务：将复杂需求拆分为具体的子任务

请确保：
- 代码完整、可运行
- 包含必要的导入和错误处理
- 遵循最佳实践
- 注释清晰易懂"""
    
    def _create_tools(self) -> List[Tool]:
        """创建 LangChain 工具"""
        tools = [
            Tool(
                name="code_generator",
                func=self._code_generator_tool,
                description="用于生成代码的工具。输入：需求描述，输出：生成的代码"
            ),
            Tool(
                name="bug_fixer",
                func=self._bug_fixer_tool,
                description="用于修复Bug的工具。输入：代码和错误描述，输出：修复后的代码"
            ),
            Tool(
                name="requirement_analyzer",
                func=self._requirement_analyzer_tool,
                description="用于分析需求的工具。输入：需求描述，输出：分解后的子任务"
            )
        ]
        return tools
    
    def _code_generator_tool(self, requirement: str) -> str:
        """代码生成工具"""
        # 直接使用 LLM 生成代码
        if self.llm:
            response = self.llm.invoke([
                HumanMessage(content=f"请根据以下需求生成Python代码：\n{requirement}\n\n请只输出代码，不要其他解释。")
            ])
            return response.content
        return "# LLM未初始化，无法生成代码"
    
    def _bug_fixer_tool(self, code_and_error: str) -> str:
        """Bug修复工具"""
        if self.llm:
            response = self.llm.invoke([
                HumanMessage(content=f"请修复以下代码中的Bug：\n{code_and_error}\n\n请只输出修复后的代码，不要其他解释。")
            ])
            return response.content
        return "# LLM未初始化，无法修复代码"
    
    def _requirement_analyzer_tool(self, requirement: str) -> str:
        """需求分析工具"""
        if self.llm:
            response = self.llm.invoke([
                HumanMessage(content=f"请将以下需求分解为具体的子任务：\n{requirement}\n\n请以JSON格式输出，每个子任务包含：任务名称、任务描述、优先级。")
            ])
            return response.content
        return "# LLM未初始化，无法分析需求"
    
    def solve_task(self, task: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        解决单个任务
        Args:
            task: 评测任务信息
        Returns:
            result: 任务结果
            info: 详细信息
        """
        start_time = time.time()
        
        # 提取任务信息
        task_id = task.get("task_id", "unknown")
        task_type = task.get("task_type", "code_generation")
        requirement = task.get("requirement", "")
        
        print(f"[LangChain Agent] Solving task: {task_id} ({task_type})")
        
        if not self.agent_executor:
            return self._create_error_result("Agent not initialized", start_time)
        
        try:
            # 根据任务类型构建输入
            if task_type == "code_generation":
                input_text = f"请帮我生成代码：{requirement}"
            elif task_type == "bug_fix":
                input_text = f"请帮我修复Bug：{requirement}"
            elif task_type == "requirement_decomposition":
                input_text = f"请帮我分解需求：{requirement}"
            else:
                input_text = requirement
            
            # 执行任务
            result = self.agent_executor.invoke({"input": input_text})
            
            # 提取结果
            output = result.get("output", "")
            token_count = len(output) // 4  # 粗略估算
            
            elapsed_time = time.time() - start_time
            
            info = {
                "success": True,
                "task_id": task_id,
                "task_type": task_type,
                "elapsed_time": elapsed_time,
                "token_count": token_count,
                "interaction_rounds": result.get("steps", 1),
                "output_length": len(output)
            }
            
            return output, info
            
        except Exception as e:
            print(f"[LangChain Agent] Error: {e}")
            return self._create_error_result(str(e), start_time)
    
    def _create_error_result(self, error_msg: str, start_time: float) -> Tuple[str, Dict[str, Any]]:
        """创建错误结果"""
        elapsed_time = time.time() - start_time
        return f"Error: {error_msg}", {
            "success": False,
            "error": error_msg,
            "elapsed_time": elapsed_time,
            "token_count": 0,
            "interaction_rounds": 0
        }
    
    def solve_task_with_llm_directly(self, task: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        直接使用 LLM 解决任务（不通过 Agent）
        用于对比测试
        """
        start_time = time.time()
        
        task_id = task.get("task_id", "unknown")
        task_type = task.get("task_type", "code_generation")
        requirement = task.get("requirement", "")
        
        if not self.llm:
            return self._create_error_result("LLM not initialized", start_time)
        
        try:
            # 构建提示词
            prompt = self._build_prompt(task_type, requirement)
            
            # 调用 LLM
            response = self.llm.invoke([HumanMessage(content=prompt)])
            output = response.content
            
            token_count = len(output) // 4
            elapsed_time = time.time() - start_time
            
            info = {
                "success": True,
                "task_id": task_id,
                "task_type": task_type,
                "elapsed_time": elapsed_time,
                "token_count": token_count,
                "interaction_rounds": 1,
                "output_length": len(output)
            }
            
            return output, info
            
        except Exception as e:
            return self._create_error_result(str(e), start_time)
    
    def _build_prompt(self, task_type: str, requirement: str) -> str:
        """根据任务类型构建提示词"""
        if task_type == "code_generation":
            return f"""你是一个专业的Python编程助手。请根据以下需求生成完整的、可运行的Python代码：

需求：{requirement}

请确保：
1. 代码完整，包含所有必要的导入
2. 包含错误处理
3. 代码清晰，有适当的注释
4. 只输出代码，不要其他解释"""
        
        elif task_type == "bug_fix":
            return f"""你是一个专业的Bug修复助手。请分析并修复以下代码中的问题：

需求描述：{requirement}

请：
1. 分析问题原因
2. 提供修复后的完整代码
3. 解释修复内容"""
        
        elif task_type == "requirement_decomposition":
            return f"""你是一个专业的需求分析师。请将以下复杂需求分解为具体的子任务：

需求：{requirement}

请以JSON数组格式输出，每个元素包含：
- task_name: 任务名称
- task_description: 任务描述
- priority: 优先级（1-5，1最高）
- estimated_hours: 预估工时"""
        
        return requirement
    
    def run_evaluation(self, tasks: List[Dict[str, Any]], use_direct_llm: bool = False) -> Dict[str, Any]:
        """
        运行评测
        Args:
            tasks: 任务列表
            use_direct_llm: 是否直接使用LLM（不用Agent）
        """
        results = []
        
        for task in tasks:
            if use_direct_llm:
                result, info = self.solve_task_with_llm_directly(task)
            else:
                result, info = self.solve_task(task)
            
            results.append({
                "task_id": info.get("task_id"),
                "success": info.get("success", False),
                "result": result,
                "info": info
            })
            
            # 更新统计
            self.update_stats(
                success=info.get("success", False),
                interaction_rounds=info.get("interaction_rounds", 1),
                time_cost=info.get("elapsed_time", 0),
                token_cost=info.get("token_count", 0)
            )
        
        return {
            "baseline": self.name,
            "results": results,
            "metrics": self.get_metrics()
        }


def create_langchain_baseline(config: Dict[str, Any] = None) -> LangChainAgentBaseline:
    """创建 LangChain 基线实例"""
    return LangChainAgentBaseline(config=config)


# 测试代码
if __name__ == "__main__":
    # 测试初始化
    config = {
        "model_name": "gpt-3.5-turbo",
        "temperature": 0.7,
        "max_iterations": 5
    }
    
    baseline = create_langchain_baseline(config)
    print(f"Created baseline: {baseline.name}")
    print(f"Metrics: {baseline.get_metrics()}")
