"""Auditable asynchronous local inference, public verification and episode memory."""
from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import re
import threading
import time
from uuid import uuid4

from experiments.humaneval_admission_worker import run_suite, decode_value
from experiments import humaneval_admission_worker as public_executor
from src.experience_graph.model import ExperienceGraph, ExperienceEdge, OperationStep
from src.experience_manager.lifecycle_policy import archive as archive_experience
from src.experience_manager.parameterized_template import (
    TemplateSource, LiteralTemplate, induce_literal_template, instantiate_literal_template,
)
from src.runtime.verified_episode_memory import (
    VerifiedEpisodeMemory, MemoryArm, PublicExecutionEvidence, FeedbackSource,
)
from .tasks import TASKS, TaskSpec
from .experience_search import query_variants, rank_verified
from .learning import LearningService, task_prompt


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def code_from_response(content, entry_point):
    """Accept a full Python module; never replace a failed generation with an oracle."""
    fenced = re.findall(r'```(?:python|py)?\s*\n(.*?)```', content, re.S)
    candidates = fenced + [content]
    for candidate in candidates:
        try:
            tree = ast.parse(candidate.strip())
        except SyntaxError:
            continue
        if any(isinstance(n, ast.FunctionDef) and n.name == entry_point for n in tree.body):
            return candidate.strip()
    return (fenced[0] if fenced else content).strip()


class WorkbenchService:
    def __init__(self, root: Path, *, provider_factory=None, semantic_model_dir=None):
        self.root = Path(root).resolve()
        self.directory = self.root / 'results/workbench/session'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='workbench')
        self.provider = None
        self.provider_factory = provider_factory
        self.semantic_search = None
        if semantic_model_dir is not None:
            from .semantic_search import SemanticSearch
            model_path = Path(semantic_model_dir)
            policy = json.loads((model_path / 'policy.json').read_text(encoding='utf-8'))
            self.semantic_search = SemanticSearch(model_path, policy['threshold'], policy['margin'])
        self.model_state = 'unloaded'
        self.model_error = None
        self.model_dir = self.root / 'artifacts/base_models/qwen2.5-coder-1.5b-instruct'
        self.runs = {}
        self.templates = []
        graph = ExperienceGraph()
        state_file = self.directory / 'memory.json'
        if state_file.exists():
            state = json.loads(state_file.read_text(encoding='utf-8'))
            graph = ExperienceGraph.model_validate(state['graph'])
            self.templates = state.get('templates', [])
        self.memory = VerifiedEpisodeMemory('workbench-local', policy=MemoryArm(
            require_execution_evidence=True), seed_graph=graph)
        for path in self.directory.glob('run-*.json'):
            run = json.loads(path.read_text(encoding='utf-8'))
            if run['status'] in ('queued', 'running'):
                run.update(status='interrupted', error='服务重启，未完成的推理没有自动重放', finished_at=now())
                self._save_run(run)
            self.runs[run['id']] = run
        self._migrate_reuse_provenance()
        self.learning = LearningService(self.root, self)

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)

    def _write(self, path, payload):
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        temp.replace(path)

    def _save_run(self, run):
        self._write(self.directory / f"run-{run['id']}.json", run)

    def _save_memory(self):
        self._write(self.directory / 'memory.json', {
            'schema': 'workbench-memory-v1', 'updated_at': now(),
            'graph': self.memory.graph_ops.graph.model_dump(mode='json'), 'templates': self.templates})

    @staticmethod
    def _legacy_used_ids(run):
        """Recover only source use directly established by the saved artifact/prompt."""
        actual = (run.get('route') or {}).get('actual')
        if actual == 'reuse' and run.get('execution_source') == 'verified_experience_reuse':
            # The legacy implementation selected the first same-requirement hit.
            exact = next((h for h in run.get('retrieval', [])
                if h.get('requirement') == (run.get('task') or {}).get('requirement')), None)
            if exact and exact.get('code') == run.get('code') and run.get('code'):
                return [exact['id']]
            return None
        if actual in ('rag', 'hybrid'):
            marker = '\nVersion-compatible verified examples (adapt to current contract):\n'
            prompt = run.get('prompt') or ''
            if marker not in prompt:
                return [] if not run.get('retrieval') else None
            try:
                examples = json.loads(prompt.split(marker, 1)[1])
                return [item['id'] for item in examples]
            except (ValueError, TypeError, KeyError):
                return None
        if actual in ('base', 'lora', 'template'):
            return []
        return None

    def _run_with_usage(self, run):
        result = deepcopy(run)
        if 'used_experience_ids' not in result:
            recovered = self._legacy_used_ids(run)
            result['used_experience_ids'] = recovered or []
            result['usage_record_source'] = 'derived_from_saved_artifact_or_prompt' if recovered is not None else 'unknown_legacy_usage'
        return result

    def _migrate_reuse_provenance(self):
        """One-time graph-only repair; never rewrite raw runs or mixed usage stats."""
        audit_path = self.directory / 'migration-reuse-provenance-v1.json'
        if audit_path.exists():
            return
        removed = []
        graph = self.memory.graph_ops.graph
        for identifier, edge in list(graph.edges.items()):
            if edge.edge_type != 'verified_reuse_source':
                continue
            target = graph.experience_nodes.get(edge.to_experience_id)
            if target is None:
                continue
            run = self.runs.get(target.context_state.environment_config.get('workbench_run_id'))
            if not run or (run.get('route') or {}).get('actual') != 'reuse':
                continue
            used = self._legacy_used_ids(run)
            if used is None or len(used) != 1:
                continue
            if edge.from_experience_id not in used:
                removed.append({'edge': edge.model_dump(mode='json'), 'run_id': run['id'],
                    'verified_source_id': used[0], 'reason': 'legacy_reuse_recorded_unconsumed_retrieval_candidate'})
                del graph.edges[identifier]
        if removed:
            self._save_memory()
        self._write(audit_path, {'migration': 'reuse-provenance-v1', 'at': now(), 'removed_edges': removed,
            'raw_run_files_modified': False, 'dynamic_usage_modified': False,
            'usage_reason': 'Legacy counters mix machine use and human feedback; no counter reconstruction attempted.'})

    def _event(self, run, stage, message, **data):
        with self.lock:
            run['timeline'].append({'at': now(), 'stage': stage, 'message': message, **data})
            self._save_run(run)

    def capabilities(self):
        return {'model': 'Qwen2.5-Coder-1.5B-Instruct', 'model_available': self.model_dir.is_dir(),
            'model_state': self.model_state, 'model_error': self.model_error,
            'model_loaded': self.provider is not None, 'local_only': True,
            'modes': ['auto', 'base', 'rag', 'reuse', 'template', 'lora', 'hybrid'],
            'test_executor': 'restricted_python_subprocess',
            'execution_boundary': 'AST/import guard + credential-free subprocess + 8-second timeout; not an OS sandbox',
            'persistence': 'results/workbench/session', 'source': 'local_live',
            'adapter_inference': True, 'adapter_gate': 'requires_active_scope_version_compatible_adapter',
            'claim_boundary': '仅证明当前公开测试通过，不代表隐藏测试或通用能力提升'}

    def list_runs(self):
        with self.lock:
            return [{k: v for k, v in self._run_with_usage(run).items() if k not in ('raw_response', 'prompt', 'code', 'timeline', 'tests')}
                    for run in sorted(self.runs.values(), key=lambda x: x['created_at'], reverse=True)]

    def get_run(self, identifier):
        with self.lock:
            return self._run_with_usage(self.runs[identifier])

    def experiences(self, version=None, scope=None, include_archived=True):
        with self.lock:
            rows = []
            for exp in self.memory.graph_ops.graph.experience_nodes.values():
                env = exp.context_state.environment_config
                if version and env.get('memory_version') != version:
                    continue
                if scope and env.get('memory_scope') != scope:
                    continue
                if not include_archived and env.get('workbench_archived'):
                    continue
                rows.append({'id': exp.experience_id, 'title': env.get('workbench_title'),
                    'requirement': exp.task_intent.original_requirement, 'scope': env.get('memory_scope'),
                    'version': env.get('memory_version'), 'code': exp.execution_result.final_output,
                    'validated': exp.execution_result.solution_validated,
                    'archived': bool(env.get('workbench_archived')), 'archive_reason': env.get('archive_reason'),
                    'created_at': exp.created_at.isoformat(), 'run_id': env.get('workbench_run_id'),
                    'source_path': env.get('ide_file'), 'test_path': env.get('ide_test'),
                    'stats': exp.dynamic_meta.model_dump(mode='json'),
                    'static_meta': exp.static_meta.model_dump(mode='json'),
                    'operation_sequence': [s.model_dump(mode='json') for s in exp.operation_sequence],
                    'evidence_type': 'machine_public_execution_receipt',
                    'feedback': env.get('workbench_feedback', []), 'receipt': env.get('public_execution_evidence')})
            return rows

    def graph(self):
        with self.lock:
            nodes = self.experiences()
            conflicts = []
            for a, b in itertools.combinations(nodes, 2):
                if (not a['archived'] and not b['archived'] and
                    (a['scope'], a['version'], a['requirement']) == (b['scope'], b['version'], b['requirement'])
                    and a['code'] != b['code']):
                    conflicts.append({'a': a['id'], 'b': b['id'], 'status': 'pending_verification',
                        'reason': '同契约出现不同通过公开测试的代码；不代表语义冲突，需追加区分测试'})
            return {'nodes': nodes, 'edges': [e.model_dump(mode='json') for e in self.memory.graph_ops.graph.edges.values()],
                'templates': deepcopy(self.templates), 'potential_conflicts': conflicts,
                'metadata_rules': {'source_credibility': '公开测试执行收据，由现有ExperienceManager生成',
                    'success_rate': '既有动态元属性更新规则；机器执行与人工反馈事件分别保留',
                    'generalization': '启发式元属性，不是跨任务能力提升证据',
                    'edges': '真实检索/复用来源关系，非因果正确性证明'}}

    def search(self, query, scope, version, top_k=5):
        with self.lock:
            rows = {e['id']: e for e in self.experiences(version, scope, include_archived=False)}
            scores = {}
            checks = []
            for variant in query_variants(query):
                session = self.memory.start_task({'task_id': 'search-' + uuid4().hex,
                    'requirement': variant, 'task_type': 'code_generation',
                    'metadata': {'memory_scope': scope, 'memory_version': version}})
                try:
                    hits = self.memory.compatible_search(session, top_k=max(1, len(rows)))
                    checks.append(deepcopy(self.memory.last_retrieval_diagnostics))
                    for hit in hits:
                        key = hit['experience_id']
                        if key in rows:
                            scores[key] = max(scores.get(key, 0), hit.get('similarity', 0))
                finally:
                    self.memory._sessions.pop(session.session_id, None)
            selected = rank_verified(query, [{**rows[key], 'similarity': score}
                for key, score in scores.items()], top_k)
            ranking = 'bilingual_lexical_v1'
            if not selected and self.semantic_search is not None:
                from .ide_receipts import verified_for_editor
                eligible = [row for key, row in rows.items() if verified_for_editor(
                    self.memory.graph_ops.get_experience(key), scope, version)]
                candidates = self.semantic_search.candidates(query, eligible)
                selected = self.semantic_search.select(candidates, top_k)
                ranking = 'multilingual_e5_fallback'
            diagnostics = {**checks[0], 'query_checks': checks, 'verified_candidates': len(scores),
                           'returned_count': len(selected), 'ranking': ranking}
            return {'experiences': selected, 'diagnostics': diagnostics, 'source': 'local_verified_memory'}

    def overview(self):
        rows, runs = self.experiences(), self.list_runs()
        return {'source': 'local_live', 'runs_total': len(runs),
            'completed': sum(r['status'] == 'completed' for r in runs),
            'successful': sum(r.get('success') is True for r in runs),
            'active_jobs': sum(r['status'] in ('queued', 'running') for r in runs),
            'experiences_total': len(rows), 'experiences_active': sum(not e['archived'] for e in rows),
            'templates_total': len(self.templates), 'capabilities': self.capabilities()}

    def submit(self, request):
        data = request.model_dump()
        if request.task_id:
            selected = next((t for t in TASKS if t['id'] == request.task_id), None)
            if not selected:
                raise ValueError('未知任务')
            spec = TaskSpec.model_validate(selected)
            task_id = selected['id']
        elif request.task:
            spec, task_id = request.task, 'custom-' + uuid4().hex[:12]
        else:
            raise ValueError('需要 task_id 或带公开测试的 task')
        if len(json.dumps(spec.model_dump(), ensure_ascii=False)) > 24000:
            raise ValueError('任务及测试总长度不能超过24000字符')
        with self.lock:
            if sum(r['status'] in ('queued', 'running') for r in self.runs.values()) >= 8:
                raise ValueError('队列已满，请等待当前任务完成')
            run = {'id': uuid4().hex, 'task_id': task_id, 'task': spec.model_dump(),
                'mode': request.mode, 'max_tokens': request.max_tokens, 'status': 'queued',
                'created_at': now(), 'source': 'local_live', 'timeline': [],
                'success': None, 'retrieval': [], 'code': '', 'tests': None,
                'template_id': data.get('template_id'), 'bindings': data.get('bindings') or {}}
            run.update(used_experience_ids=[], template_source_ids=[], usage_record_source='explicit_execution_path')
            self.runs[run['id']] = run
            self._event(run, 'queued', '任务已持久化，等待本地执行队列')
            self.pool.submit(self._execute, run['id'])
            return deepcopy(run)

    def _get_provider(self, run):
        if self.provider is None:
            self.model_state = 'loading'
            self._event(run, 'model_loading', '首次装载本地模型；后续任务复用同一实例')
            try:
                if self.provider_factory:
                    self.provider = self.provider_factory()
                else:
                    from src.runtime.local_model import LocalCausalLMProvider
                    active = self.learning.active()
                    self.provider = LocalCausalLMProvider(self.model_dir,
                        adapter_dir=Path(active['adapter_dir']) if active else None)
                self.model_state, self.model_error = 'ready', None
            except Exception as error:
                self.model_state, self.model_error = 'error', str(error)
                raise
        return self.provider

    def _execute(self, identifier):
        run = self.runs[identifier]
        started = time.monotonic()
        try:
            with self.lock:
                run.update(status='running', started_at=now())
                task = run['task']
                test_manifest = json.dumps(task['cases'], sort_keys=True, ensure_ascii=False)
                executor_hash = digest(Path(public_executor.__file__).read_text(encoding='utf-8'))
                # Unit tests can point at a temporary root; use the actual imported executor.
                session = self.memory.start_task({'task_id': run['task_id'],
                    'requirement': task['requirement'], 'task_type': 'code_generation',
                    'metadata': {'memory_scope': task['scope'], 'memory_version': task['version'],
                        'public_test_set_id': run['id'], 'public_test_set_sha256': digest(test_manifest),
                        'executor_id': 'humaneval-admission-cpu-v1', 'executor_sha256': executor_hash}})
                hits = self.memory.compatible_search(session, top_k=max(3, len(self.memory.graph_ops.graph.experience_nodes)))
                archived_dropped = sum(bool(h['experience'].context_state.environment_config.get('workbench_archived')) for h in hits)
                hits = [h for h in hits if not h['experience'].context_state.environment_config.get('workbench_archived')][:3]
                run['retrieval_diagnostics'] = deepcopy(self.memory.last_retrieval_diagnostics)
                run['retrieval_diagnostics']['archived_dropped'] = archived_dropped
                run['retrieval_diagnostics']['active_accepted_count'] = len(hits)
                run['retrieval'] = [{'id': h['experience_id'], 'similarity': h.get('similarity', 0),
                    'requirement': h['experience'].task_intent.original_requirement,
                    'code': h['experience'].execution_result.final_output} for h in hits]
            self._event(run, 'retrieval', f"兼容性过滤后检索到 {len(hits)} 条可用经验", diagnostics=run['retrieval_diagnostics'])
            exact = next((h for h in hits if h['experience'].task_intent.original_requirement == task['requirement']), None)
            run['route'] = self.learning.router.choose(task, run['retrieval'], requested=run['mode'],
                active_adapter=self.learning.active(), history=list(self.runs.values()))
            actual = run['route']['actual']
            self._event(run, 'routing', run['route']['reason'], route=run['route'])
            if actual == 'template':
                with self.lock:
                    record = next(t for t in self.templates if t['fingerprint'] == run['template_id'])
                    active_ids = {e['id'] for e in self.experiences(include_archived=False)}
                    if not all(s['source_id'] in active_ids for s in record['sources']):
                        raise ValueError('模板来源含失效或归档经验，请重新归纳')
                code = instantiate_literal_template(LiteralTemplate.from_dict(record), run['bindings'],
                    scope=task['scope'], version=task['version'])
                run['execution_source'] = 'verified_template_instantiation'
                run['template_source_ids'] = [s['source_id'] for s in record['sources']]
            elif actual == 'reuse':
                if exact is None:
                    raise ValueError('没有相同契约的可用经验；请选择auto/rag/base')
                code = exact['experience'].execution_result.final_output
                run['execution_source'] = 'verified_experience_reuse'
                run['used_experience_ids'] = [exact['experience_id']]
            else:
                examples = run['retrieval'] if actual in ('rag', 'hybrid') else []
                prompt = task_prompt(task)
                if examples:
                    prompt += '\nVersion-compatible verified examples (adapt to current contract):\n' + json.dumps(examples, ensure_ascii=False)
                run['used_experience_ids'] = [e['id'] for e in examples]
                run['prompt'] = prompt
                provider = self._get_provider(run)
                self._event(run, 'generation', '正在使用本地 Qwen 贪心生成代码')
                response = provider.generate(prompt, system='You are a careful Python programmer.',
                    max_tokens=run['max_tokens'], use_adapter=actual in ('lora', 'hybrid'))
                run.update(raw_response=response.content,
                    model={'name': response.model, 'prompt_tokens': response.prompt_tokens,
                           'completion_tokens': response.completion_tokens, 'latency': response.latency,
                           'metadata': response.extra}, execution_source='local_qwen_generation')
                code = code_from_response(response.content, task['entry_point'])
            run['code'] = code
            self._event(run, 'verification', '在独立受限子进程执行当前全部公开测试')
            tests = run_suite(code, task['entry_point'], [c['args'] for c in task['cases']],
                [c['expected'] for c in task['cases']], timeout=8)
            for row, case in zip(tests['results'], task['cases']):
                row.update(args=case['args'], expected=case['expected'])
                actual_value = decode_value(row['actual']) if row['observed'] and row['actual'] is not None else None
                try:
                    json.dumps(actual_value, allow_nan=False)
                    row['actual_display'] = actual_value
                except (ValueError, TypeError):
                    row['actual_display'] = repr(actual_value)
            run.update(tests=tests, success=tests['success'])
            with self.lock:
                receipt = PublicExecutionEvidence(source=FeedbackSource.PUBLIC_EXECUTION,
                    task_id=session.task_id, memory_scope=session.memory_scope, memory_version=session.memory_version,
                    code_sha256=digest(code), public_test_set_id=run['id'], public_test_set_sha256=digest(test_manifest),
                    executor_id='humaneval-admission-cpu-v1', executor_sha256=executor_hash,
                    tests_passed=tests['cases_passed'], tests_total=tests['cases_total'],
                    execution_time=tests['wall_seconds'], is_success=tests['success'])
                admitted = self.memory.record_execution_evidence(session, receipt, code)
                run['experience_id'] = admitted
                if admitted:
                    exp = self.memory.graph_ops.get_experience(admitted)
                    env = exp.context_state.environment_config
                    env.update(workbench_run_id=run['id'], workbench_title=task['title'])
                    exp.operation_sequence = [OperationStep(action_type=e['stage'],
                        input_params={'run_id': run['id']}, output_result={'message': e['message']},
                        timestamp=datetime.fromisoformat(e['at'])) for e in run['timeline']]
                    exp.operation_sequence.append(OperationStep(action_type='public_test_execution',
                        input_params={'code_sha256': digest(code), 'test_set_sha256': digest(test_manifest)},
                        output_result={'passed': tests['cases_passed'], 'total': tests['cases_total'],
                            'executor_sha256': executor_hash, 'success': tests['success']}))
                    for source_id in run['used_experience_ids']:
                        edge = ExperienceEdge(from_experience_id=source_id, to_experience_id=admitted,
                            edge_type='verified_reuse_source' if actual == 'reuse' else 'retrieved_prompt_source', weight=1.0)
                        self.memory.graph_ops.graph.edges[edge.edge_id] = edge
                for source_id in run['used_experience_ids']:
                    self.memory.manager.update_experience_after_use(source_id, tests['success'], tests['cases_passed']/tests['cases_total'])
                self._save_memory()
            self._event(run, 'admission', '测试通过，已绑定代码/测试/执行器哈希并写入经验库' if admitted else '验证未通过，失败代码未进入可复用经验库', experience_id=admitted)
            run.update(status='completed', elapsed=round(time.monotonic()-started, 3), finished_at=now())
            self._event(run, 'completed', '本次闭环已完成')
        except Exception as error:
            run.update(status='failed', error=f'{type(error).__name__}: {error}',
                elapsed=round(time.monotonic()-started, 3), finished_at=now())
            self._event(run, 'error', run['error'])

    def feedback(self, identifier, success, note, archive=False):
        with self.lock:
            exp = self.memory.graph_ops.get_experience(identifier)
            if exp is None:
                raise KeyError(identifier)
            self.memory.manager.update_experience_after_use(identifier, success, float(success))
            env = exp.context_state.environment_config
            env.setdefault('workbench_feedback', []).append({'at': now(), 'success': success, 'note': note,
                'source': 'human_feedback', 'objective_verification': False})
            if archive or not success:
                env.update(workbench_archived=True, archive_reason=note or '用户报告失效')
                archive_experience(exp, reason=env['archive_reason'], decision_id='human-' + uuid4().hex)
            self._save_memory()
            return next(e for e in self.experiences() if e['id'] == identifier)

    def maintenance(self, action):
        with self.lock:
            if action == 'archive_invalid':
                affected = []
                outdated = set(self.memory.manager.get_outdated_experiences())
                for exp in self.memory.graph_ops.graph.experience_nodes.values():
                    env = exp.context_state.environment_config
                    if not env.get('workbench_archived') and (exp.experience_id in outdated or not exp.execution_result.solution_validated):
                        env.update(workbench_archived=True, archive_reason='维护策略识别失效/低效经验')
                        archive_experience(exp, reason=env['archive_reason'], decision_id='maintenance-' + uuid4().hex)
                        affected.append(exp.experience_id)
                self._save_memory()
                return {'action': action, 'affected': affected}
            if action != 'build_templates':
                raise ValueError('未知维护操作')
            rows = self.experiences(include_archived=False)
            known = {t['fingerprint'] for t in self.templates}
            added = []
            for a, b in itertools.combinations(rows[:80], 2):
                if (a['scope'], a['version']) != (b['scope'], b['version']):
                    continue
                try:
                    template = induce_literal_template([TemplateSource(e['id'], e['code'], e['scope'], e['version']) for e in (a, b)])
                except (ValueError, SyntaxError):
                    continue
                value = template.to_dict()
                if value['fingerprint'] not in known:
                    self.templates.append(value)
                    added.append(value)
                    known.add(value['fingerprint'])
            self._save_memory()
            return {'action': action, 'templates_added': added, 'templates_total': len(self.templates)}
