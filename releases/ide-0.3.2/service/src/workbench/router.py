"""FastAPI attachment for the persistent local workbench."""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .service import WorkbenchService
from .ide_receipts import verified_for_editor
from .tasks import TASKS, TaskSpec


class RunRequest(BaseModel):
    task_id: str | None = None
    task: TaskSpec | None = None
    mode: Literal['auto', 'base', 'rag', 'reuse', 'template', 'lora', 'hybrid'] = 'auto'
    max_tokens: int = Field(default=384, ge=64, le=1200)
    template_id: str | None = None
    bindings: dict[str, Any] = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    success: bool
    note: str = Field(default='', max_length=1200)
    archive: bool = False


class MaintenanceRequest(BaseModel):
    action: Literal['archive_invalid', 'build_templates']


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=6000)
    scope: str = Field(default='workbench-python', min_length=1, max_length=80)
    version: str = Field(default='v1', min_length=1, max_length=40)
    top_k: int = Field(default=5, ge=1, le=30)


def create_workbench_router(root: Path, *, service: WorkbenchService | None = None):
    service = service or WorkbenchService(root)

    @asynccontextmanager
    async def lifespan(app):
        yield
        service.close()

    router = APIRouter(prefix='/api/workbench', tags=['workbench'], lifespan=lifespan)
    router.workbench_service = service

    @router.get('/capabilities')
    def capabilities():
        return service.capabilities()

    @router.get('/overview')
    def overview():
        return service.overview()

    @router.get('/tasks')
    def tasks():
        return {'tasks': TASKS}

    @router.get('/runs')
    def runs():
        return {'runs': service.list_runs()}

    @router.post('/runs', status_code=202)
    def submit(request: RunRequest):
        try:
            return service.submit(request)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error

    @router.get('/runs/{identifier}')
    def run(identifier: str):
        try:
            return service.get_run(identifier)
        except KeyError as error:
            raise HTTPException(404, '未找到运行记录') from error

    @router.get('/experiences')
    def experiences(version: str | None = None, scope: str | None = None, include_archived: bool = True):
        return {'experiences': service.experiences(version, scope, include_archived)}

    @router.get('/templates')
    def templates():
        with service.lock:
            return {'templates': list(service.templates)}

    @router.post('/ide-ranked-experiences')
    def browse_verified(request: SearchRequest):
        with service.lock:
            rows = service.experiences(request.version, request.scope, include_archived=False)
            eligible = sorted((row for row in rows if verified_for_editor(
                service.memory.graph_ops.get_experience(row['id']), request.scope, request.version)),
                key=lambda row: (row['requirement'], row['id']))
            engine = service.semantic_search
            if engine is None or not request.query.strip():
                return {'experiences': eligible, 'ranking': 'verified_titles'}
            ranked = engine.candidates(request.query, eligible)
            scores = {(row['requirement'], row['code']): row['composite_score'] for row in ranked}
            eligible.sort(key=lambda row: -scores[(row['requirement'], row['code'])])
            return {'experiences': eligible, 'ranking': 'multilingual_e5_manual'}

    @router.get('/graph')
    def graph():
        return service.graph()

    @router.post('/search')
    def search(request: SearchRequest):
        return service.search(**request.model_dump())

    @router.post('/experiences/{identifier}/feedback')
    def feedback(identifier: str, request: FeedbackRequest):
        try:
            return service.feedback(identifier, **request.model_dump())
        except KeyError as error:
            raise HTTPException(404, '未找到经验') from error

    @router.post('/maintenance')
    def maintenance(request: MaintenanceRequest):
        return service.maintenance(request.action)

    return router
