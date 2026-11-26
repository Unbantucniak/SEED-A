"""Local IDE drafts and explicit research artifacts for the workbench UI."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .ide_receipts import create_ide_router


def display_json(path: Path):
    """Keep large decimal integers exact in browser-visible evidence only."""
    return json.loads(path.read_text(encoding='utf-8'),
                      parse_int=lambda token: token if len(token.lstrip('-')) > 15 else int(token))


class Draft(BaseModel):
    code: str = Field(min_length=1, max_length=20000)
    title: str = Field(default='IDE 开发任务', max_length=120)
    language: str = Field(default='python', max_length=50)
    source: str = Field(default='vscode', pattern='^(vscode|workbench)$')
    file_label: str = Field(default='', max_length=240)
    scope: str = Field(default='workbench-python', min_length=1, max_length=80)
    version: str = Field(default='v1', min_length=1, max_length=40)


def create_presentation_router(root: Path):
    router = APIRouter(prefix='/api/workbench')
    router.include_router(create_ide_router(root))
    drafts = root / 'results/workbench/drafts'
    closeout_versions = [root / 'output/docx' / name for name in (
        '自学习自演化智能体_结题验收书_20261024_多种子改进评测版.docx',
        '自学习自演化智能体_结题验收书_20261023_经验扩展复验版.docx',
        '自学习自演化智能体_结题验收书_20261023_跨数据集评测版.docx',
        '自学习自演化智能体_结题验收书_20261018_补充评测版.docx',
        '自学习自演化智能体_结题验收书_20261018_系统整合版.docx')]
    closeout = next((p for p in closeout_versions if p.is_file()), closeout_versions[0])
    proposal_versions = [root / 'output/docx' / name for name in (
        '自学习自演化智能体_项目申报书_20261024_多种子改进评测版.docx',
        '自学习自演化智能体_项目申报书_经验扩展更新版_20261023.docx',
        '自学习自演化智能体_项目申报书_完善版_20261023.docx')]
    files = {
        'report': root / 'docs/research/基线消融跨版本与LoRA迁移补充研究_20261018.md',
        'historical-report': root / 'docs/research/经验准入与任务复用实证研究_20261018.md',
        'closeout': closeout,
        'proposal': next((p for p in proposal_versions if p.is_file()), proposal_versions[0]),
        'proposal-map': root / 'docs/research/申报目标与现有成果对应说明_20261023.md',
        'paired-analysis': root / 'results/paired_uncertainty_20261023/配对不确定性与成本复核.md',
        'study-chart': root / 'results/experience_studies_report_20261018/admission_and_transfer.png',
        'cost-chart': root / 'results/experience_studies_report_20261018/admission_and_transfer_costs.png',
        'ide': root / 'src/prototype/dist/seeda-experience-assistant-0.2.0.vsix',
        'controlled-summary': root / 'results/controlled_comparison_20261018/summary.json',
        'controlled-protocol': root / 'results/controlled_comparison_20261018/protocol.json',
        'mbpp-summary': root / 'results/mbpp_transfer_20261023/summary.json',
        'mbpp-protocol': root / 'results/mbpp_transfer_20261023/protocol.json',
        'mbpp-report': root / 'docs/research/选择性检索与保守LoRA跨数据集评测_20261023.md',
        'mbpp-cases': root / 'docs/research/MBPP迁移失败与改善案例_20261023.md',
        'expansion-summary': root / 'results/mbpp_expansion_20261023/summary.json',
        'expansion-protocol': root / 'results/mbpp_expansion_20261023/protocol.json',
        'expansion-report': root / 'docs/research/经验扩展与持续内化复验_20261023.md',
        'expansion-cases': root / 'docs/research/经验扩展复验失败与改善案例_20261023.md',
        'stability-summary': root / 'results/mbpp_stability_20261024/summary.json',
        'stability-protocol': root / 'results/mbpp_stability_20261024/protocol.json',
        'stability-report': root / 'docs/research/契约检索与稳定内化多种子评测_20261024.md',
        'stability-cases': root / 'docs/research/契约检索与稳定内化多种子评测失败与改善案例_20261024.md',
        'continual-summary': root / 'results/continual_versions_20261018/summary.json',
        'release-review': root / 'deliverables/data_release_review_20261018/SEED-A_development_process_v2_review.zip',
        'release-note': root / 'deliverables/data_release_review_20261018/待审说明.txt',
        'release-review-b': root / 'deliverables/continual_data_release_review_20261018_B.zip',
    }

    @router.post('/drafts', status_code=201)
    def create_draft(body: Draft):
        identifier = uuid4().hex
        value = body.model_dump()
        value['file_label'] = value['file_label'].replace('\\', '/').split('/')[-1]
        value.update(id=identifier, created_at=datetime.now(timezone.utc).isoformat(), verified=False)
        drafts.mkdir(parents=True, exist_ok=True)
        (drafts / f'{identifier}.json').write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'id': identifier, 'verified': False}

    @router.get('/drafts/{identifier}')
    def get_draft(identifier: str):
        path = drafts / f'{identifier}.json'
        if not re.fullmatch(r'[a-f0-9]{32}', identifier) or not path.is_file():
            raise HTTPException(404, '未找到草稿')
        return json.loads(path.read_text(encoding='utf-8'))

    @router.get('/research')
    def research():
        studies = {}
        for key, directory in [('admission', 'experience_admission_humaneval_20261018_bounded'),
                               ('transfer', 'experience_memory_transfer_humaneval_20261018'),
                               ('controlled', 'controlled_comparison_20261018'),
                               ('continual', 'continual_versions_20261018'),
                               ('mbpp', 'mbpp_transfer_20261023'),
                               ('expansion', 'mbpp_expansion_20261023'),
                               ('stability', 'mbpp_stability_20261024')]:
            path = root / 'results' / directory / 'summary.json'
            studies[key] = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None
        files['closeout'] = next((p for p in closeout_versions if p.is_file()), closeout_versions[0])
        files['proposal'] = next((p for p in proposal_versions if p.is_file()), proposal_versions[0])
        latest_report = root / 'docs/research/基线消融跨版本与LoRA迁移补充研究_20261018.md'
        if latest_report.is_file():
            files['report'] = latest_report
        exposure_path = root / 'results/controlled_comparison_20261018/exposure_analysis.json'
        paired_path = root / 'results/paired_uncertainty_20261023/analysis.json'
        return {'source': 'archived_reproducible_experiment', 'studies': studies,
                'controlled_exposure': display_json(exposure_path) if exposure_path.is_file() else None,
                'paired_analysis': display_json(paired_path) if paired_path.is_file() else None,
                'artifacts': [{'id': k, 'name': p.name} for k, p in files.items() if p.is_file()],
                'publication': 'local_review_before_release'}

    @router.get('/files/{identifier}')
    def file(identifier: str):
        if identifier == 'closeout':
            files['closeout'] = next((p for p in closeout_versions if p.is_file()), closeout_versions[0])
        elif identifier == 'proposal':
            files['proposal'] = next((p for p in proposal_versions if p.is_file()), proposal_versions[0])
        path = files.get(identifier)
        if path is None or not path.is_file():
            raise HTTPException(404, '成果文件尚不可用')
        inline = path.suffix == '.png'
        return FileResponse(path, filename=path.name, content_disposition_type='inline' if inline else 'attachment')

    @router.get('/research-case')
    def research_case(task_id: str, arm: str):
        directory = root / 'results/controlled_comparison_20261018'
        summary_path = directory / 'summary.json'
        if not summary_path.is_file():
            raise HTTPException(404, '本轮结果尚未归档')
        summary = json.loads(summary_path.read_text(encoding='utf-8'))
        row = next((r for r in summary.get('rows', []) if r['task_id'] == task_id and r['arm'] == arm), None)
        if row is None or not re.fullmatch(r'[A-Za-z0-9_-]+', row['call_id']):
            raise HTTPException(404, '未找到该任务与方案的记录')
        call = directory / 'calls' / row['call_id']
        score = directory / 'scoring' / row['call_id']
        required = [call / 'candidate.py', call / 'prompt.json', score / 'base.json', score / 'scoring.json']
        if not all(p.is_file() for p in required):
            raise HTTPException(404, '该记录的完整证据暂不可用')
        base_test, scoring_test = display_json(required[2]), display_json(required[3])
        examples = {}
        task_path, expected_path = directory / 'task_cases.json', directory / 'expected_wire.json'
        if task_path.is_file() and expected_path.is_file():
            task = next((t for t in display_json(task_path) if t['task_id'] == task_id), None)
            expected = display_json(expected_path).get(task_id, {})
            if task:
                for suite, receipt in [('base', base_test), ('scoring', scoring_test)]:
                    observations = receipt.get('results', [])
                    selected = next((item for item in observations if item.get('passed') is not True),
                                    observations[0] if observations else None)
                    if selected is not None:
                        index = selected['index']
                        examples[suite] = {'index': index, 'args': task[suite][index],
                            'expected_wire': expected[suite][index], 'actual_wire': selected.get('actual'),
                            'passed': selected.get('passed'), 'observed': selected.get('observed'),
                            'error': selected.get('error')}
        return {'record': row, 'code': required[0].read_text(encoding='utf-8'),
                'prompt': display_json(required[1]),
                'base_test': base_test, 'scoring_test': scoring_test, 'case_examples': examples,
                'display_format': '超出 15 位十进制精度的整数以字符串展示，避免浏览器丢失精度；原始评分文件保持不变。'}

    @router.get('/mbpp-case')
    def mbpp_case(task_id: str, arm: str, study: str = 'mbpp'):
        studies = {'mbpp': 'mbpp_transfer_20261023', 'expansion': 'mbpp_expansion_20261023'}
        if study not in studies:
            raise HTTPException(404, '未注册的研究记录')
        directory = root / 'results' / studies[study]
        summary_path = directory / 'summary.json'
        if not summary_path.is_file():
            raise HTTPException(404, '本轮跨数据集结果尚未归档')
        summary = display_json(summary_path)
        row = next((r for r in summary.get('rows', [])
                    if r.get('task_id') == task_id and r.get('arm') == arm), None)
        if row is None or not re.fullmatch(r'[A-Za-z0-9_-]+', str(row.get('call_id', ''))):
            raise HTTPException(404, '未找到该任务与方案的记录')
        call = directory / 'calls' / row['call_id']
        score = directory / 'scoring' / row['call_id']
        required = [call / 'candidate.py', call / 'prompt.json', score / 'visible.json',
                    score / 'heldout.json', directory / 'task_cases.json']
        if not all(p.is_file() for p in required):
            raise HTTPException(404, '该记录的完整证据暂不可用')
        task = next((t for t in display_json(required[4]) if t.get('task_id') == task_id), None)
        if task is None:
            raise HTTPException(404, '未找到对应的冻结任务测试')
        return {'record': row, 'code': required[0].read_text(encoding='utf-8'),
                'prompt': display_json(required[1]), 'visible_test': display_json(required[2]),
                'heldout_test': display_json(required[3]), 'task': task,
                'display_format': '超出 15 位十进制精度的整数以字符串展示；评分完成后展示冻结测试和实际收据，不重新生成或运行。'}

    @router.get('/stability-case')
    def stability_case(task_id: str, arm: str):
        directory = root / 'results/mbpp_stability_20261024'
        summary_path = directory / 'summary.json'
        if not summary_path.is_file():
            raise HTTPException(404, '多种子评测尚未完成')
        summary = display_json(summary_path)
        if summary.get('status') != 'completed':
            raise HTTPException(404, '多种子评测尚未完成')
        row = next((r for r in summary.get('rows', [])
                    if r.get('task_id') == task_id and r.get('arm') == arm), None)
        if row is None:
            raise HTTPException(404, '未找到该任务与方案的记录')
        initial, repair, selected = row.get('initial_call_id'), row.get('repair_call_id'), row.get('call_id')
        identifiers = [initial] + ([repair] if repair is not None else [])
        if any(not isinstance(i, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', i) for i in identifiers):
            raise HTTPException(404, '调用记录无效')
        if selected not in identifiers:
            raise HTTPException(404, '选择结果与调用记录不一致')
        task_path = directory / 'task_cases.json'
        if not task_path.is_file():
            raise HTTPException(404, '冻结任务尚不可用')
        task = next((t for t in display_json(task_path) if t.get('task_id') == task_id), None)
        if task is None:
            raise HTTPException(404, '未找到冻结任务')
        attempts = []
        for role, call_id in [('initial', initial)] + ([('repairs', repair)] if repair is not None else []):
            call = directory / role / 'calls' / call_id
            visible = directory / ('visible_initial' if role == 'initial' else 'visible_repairs') / (call_id + '.json')
            heldout = directory / 'heldout' / role / (call_id + '.json')
            required = [call / 'candidate.py', call / 'prompt.json', call / 'call.json', visible, heldout]
            if not all(p.is_file() for p in required):
                raise HTTPException(404, '该记录的完整证据暂不可用')
            metadata = display_json(required[2])
            if metadata.get('task_id') != task_id or metadata.get('call_id') != call_id:
                raise HTTPException(404, '调用元数据不匹配')
            attempts.append({'role': role, 'call_id': call_id, 'selected': call_id == selected,
                             'code': required[0].read_text(encoding='utf-8'), 'prompt': display_json(required[1]),
                             'metadata': metadata, 'visible_test': display_json(visible),
                             'heldout_test': display_json(heldout)})
        retrieval_path = directory / 'retrieval_receipts.json'
        retrieval_receipts = [r for r in display_json(retrieval_path)
                              if r.get('task_id') == task_id and r.get('method') in ('legacy', 'contract')] if retrieval_path.is_file() else []
        return {'record': row, 'task': task, 'attempts': attempts, 'retrieval_receipts': retrieval_receipts,
                'display_format': '首次输出、可见修复和最终选择均保留；保留测试在选择封存后评分。未选中的修复仍计入调用与 token 成本。超过 15 位的整数以字符串展示。'}

    return router
