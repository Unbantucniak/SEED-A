"""Persist explicitly run IDE pytest receipts in the workbench experience graph."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator, model_validator

from src.runtime.verified_episode_memory import FeedbackSource, PublicExecutionEvidence
from src.experience_manager.lifecycle_policy import is_active


def verified_for_editor(node, scope, version):
    """List eligibility is independent of query vocabulary and retrieval rank."""
    if node is None or not is_active(node):
        return False
    env = node.context_state.environment_config
    result = node.execution_result
    if (env.get('memory_scope'), env.get('memory_version')) != (scope, version) or env.get('workbench_archived'):
        return False
    if (not result.is_success or result.error_info or not result.solution_validated or result.test_pass_rate != 1.0
            or env.get('credential_verified') is not True or 'human_reported' in (result.validation_notes or '')
            or 'verification_mode:human_reported' in node.static_meta.domain_tags
            or '[verification_mode:human_reported]' in (node.task_intent.user_instruction or '')):
        return False
    try:
        bound = PublicExecutionEvidence(**env.get('public_execution_evidence', {}))
    except (TypeError, ValueError):
        return False
    return (bound.task_id == env.get('source_task_id') and bound.memory_scope == scope and bound.memory_version == version
            and bound.is_success and bound.tests_passed == bound.tests_total
            and bound.code_sha256 == hashlib.sha256(result.final_output.encode()).hexdigest())


class IdeReceipt(BaseModel):
    receipt_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    title: str = Field(min_length=1, max_length=120)
    scope: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=40)
    code: str = Field(min_length=1, max_length=20000)
    file_label: str = Field(min_length=1, max_length=500)
    test_label: str = Field(min_length=1, max_length=500)
    code_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    file_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    test_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    executor_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    pytest_version: str = Field(min_length=1, max_length=80)
    passed: int = Field(ge=0)
    total: int = Field(ge=0)
    skipped: int = Field(ge=0)
    exit_code: int
    seconds: float = Field(ge=0, allow_inf_nan=False)
    source_id: str | None = Field(default=None, max_length=100)
    first_line: int | None = Field(default=None, ge=1)
    last_line: int | None = Field(default=None, ge=1)

    @field_validator('file_label', 'test_label')
    @classmethod
    def relative_label(cls, value):
        if value.startswith(('/', '\\')) or ':' in value or '..' in Path(value.replace('\\', '/')).parts:
            raise ValueError('请使用工作区相对文件路径')
        return value

    @model_validator(mode='after')
    def validate_counts(self):
        if self.passed + self.skipped > self.total or hashlib.sha256(self.code.encode()).hexdigest() != self.code_sha256:
            raise ValueError('测试计数或选区摘要无效')
        return self


def create_ide_router(root: Path):
    router = APIRouter()
    directory = root / 'results/workbench/ide-receipts'

    @router.get('/ide-capabilities')
    def capabilities():
        return {'protocol': 1, 'project_pytest': True, 'verified_browse': True}

    @router.get('/ide-verified-experiences')
    def verified_experiences(scope: str, version: str, request: Request):
        service = request.app.state.workbench
        with service.lock:
            rows = service.experiences(scope=scope, version=version, include_archived=False)
            eligible = (row for row in rows if verified_for_editor(service.memory.graph_ops.get_experience(row['id']), scope, version))
            return {'experiences': sorted(eligible, key=lambda row: (row['requirement'], row['id']))}

    @router.post('/ide-receipts')
    def add_receipt(body: IdeReceipt, request: Request):
        service = request.app.state.workbench
        path = directory / (body.receipt_id + '.json')
        payload = body.model_dump()
        with service.lock:
            directory.mkdir(parents=True, exist_ok=True)
            if path.exists():
                saved = json.loads(path.read_text(encoding='utf-8'))
                if saved['input'] != payload:
                    raise HTTPException(409, '相同收据 ID 对应不同内容')
                return saved['result']
            previous = None
            if body.source_id:
                previous = service.memory.graph_ops.get_experience(body.source_id)
                if not verified_for_editor(previous, body.scope, body.version) or previous.execution_result.final_output != body.code:
                    raise HTTPException(409, '复用来源、适用范围或选区内容已改变')
            passed = body.exit_code == 0 and body.passed > 0 and body.passed + body.skipped == body.total
            experience_id = body.source_id
            # A crash after graph persistence may leave the receipt file unwritten.
            # Use its stable ID on the graph to make replay safe.
            if previous:
                env = previous.context_state.environment_config
                ids = env.setdefault('ide_test_receipts', [])
                if body.receipt_id not in ids:
                    if body.total > body.skipped and body.exit_code in (0, 1):
                        service.memory.manager.update_experience_after_use(body.source_id, passed, body.passed / (body.total - body.skipped))
                    ids.append(body.receipt_id)
            elif passed:
                for node in service.memory.graph_ops.graph.experience_nodes.values():
                    if node.context_state.environment_config.get('ide_origin_receipt') == body.receipt_id:
                        experience_id = node.experience_id
                        break
                if not experience_id:
                    meta = {'memory_scope': body.scope, 'memory_version': body.version, 'public_test_set_id': body.test_label,
                            'public_test_set_sha256': body.test_sha256, 'executor_id': 'vscode-project-pytest',
                            'executor_sha256': body.executor_sha256}
                    session = service.memory.start_task({'task_id': body.receipt_id, 'requirement': body.title,
                        'task_type': 'code_generation', 'metadata': meta})
                    evidence = PublicExecutionEvidence(FeedbackSource.PUBLIC_EXECUTION, body.receipt_id, body.scope,
                        body.version, body.code_sha256, body.test_label, body.test_sha256, 'vscode-project-pytest',
                        body.executor_sha256, body.passed, body.total - body.skipped, body.seconds, True)
                    try:
                        experience_id = service.memory.record_execution_evidence(session, evidence, body.code)
                    finally:
                        service.memory._sessions.pop(session.session_id, None)
                    if not experience_id:
                        raise HTTPException(409, '该测试收据未通过经验库准入')
                    node = service.memory.graph_ops.get_experience(experience_id)
                    node.context_state.environment_config.update(workbench_title=body.title, ide_origin_receipt=body.receipt_id,
                        ide_test_receipts=[body.receipt_id], ide_file=body.file_label, ide_test=body.test_label)
            service._save_memory()
            result = {'status': 'passed' if passed else 'failed', 'experience_id': experience_id, 'receipt_id': body.receipt_id,
                      'passed': body.passed, 'total': body.total, 'skipped': body.skipped, 'exit_code': body.exit_code}
            service._write(path, {'recorded_at': datetime.now(timezone.utc).isoformat(), 'input': payload, 'result': result})
            return result

    return router
