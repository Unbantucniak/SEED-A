#!/usr/bin/env python3
"""
IDE插件后端服务
对接核心经验管理模块，提供REST API接口
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import sys
import os

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.experience_manager.manager import ExperienceManager

app = FastAPI(title="自学习自演化智能体后端服务", version="0.0.1")

# 初始化全局经验管理器
experience_manager = ExperienceManager()

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

class AddExperienceRequest(BaseModel):
    original_requirement: str
    user_instruction: str
    task_type: str
    final_output: str
    is_success: bool
    execution_time: float
    source_credibility: float = 0.8
    domain_tags: List[str] = None
    dependency_versions: Dict[str, str] = None

@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    health_info = experience_manager.run_health_check()
    return {
        "status": "ok",
        "total_experiences": health_info["total_experiences"],
        "health_score": health_info["health_score"]
    }

@app.post("/api/experience/search")
async def search_experience(request: SearchRequest):
    """搜索相关经验"""
    try:
        results = experience_manager.graph_ops.semantic_search(request.query, top_k=request.top_k)
        return [
            {
                "experience_id": res["experience_id"],
                "task_intent": res["experience"].task_intent.model_dump(),
                "execution_result": res["experience"].execution_result.model_dump(),
                "static_meta": res["experience"].static_meta.model_dump(),
                "dynamic_meta": res["experience"].dynamic_meta.model_dump(),
                "similarity": res["similarity"],
                "composite_score": res["composite_score"]
            }
            for res in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

@app.post("/api/experience/add")
async def add_experience(request: AddExperienceRequest):
    """添加新经验"""
    try:
        raw_data = {
            "original_requirement": request.original_requirement,
            "user_instruction": request.user_instruction,
            "task_type": request.task_type,
            "final_output": request.final_output,
            "is_success": request.is_success,
            "execution_time": request.execution_time,
            "source_credibility": request.source_credibility,
            "domain_tags": request.domain_tags or [],
            "dependency_versions": request.dependency_versions or {}
        }
        exp_id = experience_manager.add_candidate_experience(raw_data, auto_verify=True)
        if not exp_id:
            raise HTTPException(status_code=400, detail="经验质量不足，未入库")
        return {"experience_id": exp_id, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加经验失败: {str(e)}")

@app.get("/api/experience/{experience_id}")
async def get_experience(experience_id: str):
    """获取经验详情"""
    exp = experience_manager.graph_ops.get_experience(experience_id)
    if not exp:
        raise HTTPException(status_code=404, detail="经验不存在")
    return {
        "experience_id": exp.experience_id,
        "task_intent": exp.task_intent.model_dump(),
        "context_state": exp.context_state.model_dump(),
        "operation_sequence": [step.model_dump() for step in exp.operation_sequence],
        "execution_result": exp.execution_result.model_dump(),
        "static_meta": exp.static_meta.model_dump(),
        "dynamic_meta": exp.dynamic_meta.model_dump(),
        "created_at": exp.created_at,
        "last_used_at": exp.last_used_at
    }

@app.delete("/api/experience/{experience_id}")
async def delete_experience(experience_id: str):
    """删除经验"""
    success = experience_manager.graph_ops.delete_experience(experience_id)
    if not success:
        raise HTTPException(status_code=404, detail="经验不存在")
    return {"status": "success"}

@app.get("/api/library/stats")
async def get_library_stats():
    """获取经验库统计信息"""
    health_info = experience_manager.run_health_check()
    return health_info

@app.post("/api/library/clean")
async def clean_outdated_experiences(auto_delete: bool = False):
    """清理过期经验"""
    deleted_ids = experience_manager.clean_outdated_experiences(auto_delete=auto_delete)
    return {
        "deleted_count": len(deleted_ids) if auto_delete else 0,
        "outdated_count": len(deleted_ids),
        "outdated_ids": deleted_ids
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
