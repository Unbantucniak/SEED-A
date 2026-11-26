"""Local, bounded experience SFT and auditable feedback-aware routing.

This is an operational mechanism demo. Its known public regression gate is not
evidence of a general quality improvement. All GPU work uses the workbench's
single worker; imports and planning never load a model.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import gc
import hashlib
import json
import math
from pathlib import Path
import time
from uuid import uuid4


SYSTEM = 'You are a careful Python programmer.'
MODES = ('base', 'rag', 'lora', 'hybrid', 'reuse', 'template')
ROUTING_POLICY = 'auditable_feedback_heuristic_v3'


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def task_prompt(task):
    """Keep inference and SFT prefixes identical to the workbench base path."""
    return ('Implement the requested Python function. Return only a complete Python module in a python code block. '
        'Include only the function definition and necessary imports. Do not include test cases, assertions, example calls, printing or executable top-level statements. '
        'No input(), file/network access or third-party packages.\n'
        + task['requirement'] + '\nExact entry point: ' + task['entry_point']
        + '\nPublic test cases:\n' + json.dumps(task['cases'], sort_keys=True, ensure_ascii=False))


class WorkbenchRouter:
    """Deterministic cold-start rules with observed, local outcome preferences.

    LoRA evidence is isolated by the weights actually used, not only task
    scope/version. Unknown costs and unmatched weights cannot qualify a path;
    elapsed time is end-to-end service cost, not isolated model latency.

    The project's Actor-Critic implementation needs a qualified policy for this
    task distribution. An untrained/random policy is deliberately not presented
    as learned routing; no extra model calls are spent training it for a demo.
    """
    def choose(self, task, matches, *, requested='auto', active_adapter=None, history=()):
        # Callers supply only verified, active, scope/version-compatible search
        # hits. In particular, a text match from an unfiltered store is not a
        # sufficient premise for the exact-contract reuse shortcut.
        if requested not in ('auto', *MODES):
            raise ValueError('unknown workbench route')
        exact = any(m.get('requirement') == task['requirement'] for m in matches)
        coverage = (active_adapter or {}).get('coverage', [])
        compatible_adapter = bool(active_adapter) and any(
            c.get('scope') == task['scope'] and c.get('version') == task['version'] for c in coverage)
        adapter_sha256 = (active_adapter or {}).get('adapter_sha256')
        adapter_identity_known = (isinstance(adapter_sha256, str) and len(adapter_sha256) == 64
            and all(c in '0123456789abcdef' for c in adapter_sha256))
        observed = defaultdict(lambda: {'count': 0, 'passed': 0, 'seconds': 0.0})
        excluded = defaultdict(int)
        for run in history:
            old = run.get('task', {})
            if run.get('status') != 'completed' or type(run.get('success')) is not bool:
                continue
            if (old.get('scope'), old.get('version')) != (task['scope'], task['version']):
                continue
            route = run.get('route') or {}
            mode = route.get('actual')
            if mode not in MODES:
                continue
            if mode in ('lora', 'hybrid'):
                # A new/rolled-back adapter is a different treatment even when
                # its declared contract coverage is unchanged. Route labels or
                # candidate IDs alone cannot establish the weights actually used.
                metadata = (run.get('model') or {}).get('metadata') or {}
                if (not adapter_identity_known or metadata.get('adapter_active') is not True
                        or metadata.get('adapter_sha256') != adapter_sha256):
                    excluded['adapter_identity_mismatch_or_missing'] += 1
                    continue
            elapsed = run.get('elapsed')
            if (isinstance(elapsed, bool) or not isinstance(elapsed, (int, float))
                    or not math.isfinite(elapsed) or elapsed < 0):
                # Missing, negative and nonfinite measurements must not become
                # free execution or propagate NaN into the persisted decision.
                excluded['invalid_or_missing_elapsed'] += 1
                continue
            row = observed[mode]
            row['count'] += 1
            row['passed'] += int(run['success'])
            row['seconds'] += elapsed
        features = {'scope': task['scope'], 'version': task['version'],
            'requirement_length': len(task['requirement']), 'public_cases': len(task.get('cases', [])),
            'compatible_experiences': len(matches), 'exact_contract': exact,
            'adapter_compatible': compatible_adapter,
            'active_adapter_sha256': adapter_sha256 if adapter_identity_known else None,
            'excluded_observations': dict(excluded),
            'cost_basis': 'completed_run_elapsed_seconds_including_loading_verification_and_persistence',
            'observed_outcomes': dict(observed)}
        if requested != 'auto':
            actual, reason = requested, '用户显式选择执行路径'
            if requested in ('lora', 'hybrid') and not compatible_adapter:
                raise ValueError('当前契约范围/版本没有通过回归并激活的适配器')
        elif exact:
            actual, reason = 'reuse', '相同契约且版本兼容，复用后重新执行公开测试'
        else:
            actual = 'base'
            reason = '同范围/版本的基座及候选路径反馈证据不足，保留基座；检索命中或适配器激活不单独触发切换'
            available = ['base'] + (['rag'] if matches else []) + (['lora'] if compatible_adapter else []) + (['hybrid'] if matches and compatible_adapter else [])
            # Compare only paths with repeated actual observations. Smoothed
            # outcomes avoid a single failure dominating cold-start routing.
            qualified = [m for m in available if observed[m]['count'] >= 3]
            if 'base' in qualified and len(qualified) >= 2:
                def score(mode):
                    row = observed[mode]
                    return (row['passed'] + 1) / (row['count'] + 2) - min(row['seconds'] / row['count'] / 6000, .05)
                preferred = max(qualified, key=score)
                features['observed_scores'] = {m: score(m) for m in qualified}
                if score(preferred) > score('base') + .05:
                    actual = preferred
                    reason = '同范围/版本的基座及候选路径均至少3次已完成执行；候选平滑成功率与耗时分数超过基座0.05，按局部反馈切换'
                else:
                    reason = '同范围/版本已有重复反馈，但候选平滑分数未超过基座0.05，保留基座'
        return {'requested': requested, 'actual': actual, 'reason': reason, 'features': features,
            'policy': ROUTING_POLICY, 'actor_critic_used': False,
            'policy_boundary': '局部历史执行的启发式选择，非配对因果评估；LoRA反馈按当前权重哈希隔离，耗时包含加载、验证及持久化，非纯生成速度；v3未纳入本轮32题冻结评测，不声称已验证收益或已学习最优策略'}


def select_experiences(experiences, runs, identifiers=None):
    """Bind exact generated targets to public execution receipts, fail closed."""
    wanted = set(identifiers or ())
    selected, rejected, seen = [], [], set()
    for exp in experiences:
        if wanted and exp['id'] not in wanted:
            continue
        try:
            if exp.get('archived') or exp.get('validated') is not True:
                raise ValueError('experience is archived or unvalidated')
            run = runs.get(exp.get('run_id')) or {}
            receipt = exp.get('receipt') or {}
            code = exp.get('code', '')
            task = run.get('task') or {}
            tests = run.get('tests') or {}
            if run.get('status') != 'completed' or run.get('success') is not True:
                raise ValueError('missing successful completed source run')
            if run.get('execution_source') != 'local_qwen_generation':
                raise ValueError('training requires an actual local generation, not reuse/template output')
            if not code.strip() or code != run.get('code') or code not in run.get('raw_response', ''):
                raise ValueError('target differs from exact model generated code')
            model = run.get('model') or {}
            if (model.get('metadata') or {}).get('execution_backend') != 'local_hf_causal_lm':
                raise ValueError('local model execution identity missing')
            manifest = json.dumps(task['cases'], sort_keys=True, ensure_ascii=False)
            if (receipt.get('source') != 'public_execution' or receipt.get('code_sha256') != digest(code)
                    or receipt.get('public_test_set_sha256') != digest(manifest)
                    or receipt.get('public_test_set_id') != run.get('id')
                    or receipt.get('is_success') is not True):
                raise ValueError('code/public-test receipt binding mismatch')
            if receipt.get('tests_total', 0) < 2 or receipt.get('tests_passed') != receipt.get('tests_total'):
                raise ValueError('at least two actually passing public tests required')
            if not tests.get('success') or not tests.get('suite_complete'):
                raise ValueError('complete actual source execution required')
            if (task['scope'], task['version']) != (exp.get('scope'), exp.get('version')):
                raise ValueError('source context differs from experience')
            identity = (task['requirement'], task['scope'], task['version'])
            if identity in seen:
                raise ValueError('duplicate contract; not an independent training example')
            seen.add(identity)
            selected.append({'experience_id': exp['id'], 'source_run_id': run['id'], 'task': deepcopy(task),
                'code': code, 'code_sha256': digest(code), 'source_model': deepcopy(model),
                'source_receipt': deepcopy(receipt), 'prompt': task_prompt(task), 'system': SYSTEM})
        except (ValueError, KeyError, TypeError) as error:
            rejected.append({'experience_id': exp['id'], 'reason': str(error)})
    missing = wanted - {e['id'] for e in experiences}
    rejected.extend({'experience_id': identifier, 'reason': 'unknown experience'} for identifier in sorted(missing))
    return sorted(selected, key=lambda e: (len(e['code']), e['experience_id'])), rejected


def regression_gate(before, after, rehearsal):
    """Known public checks allow neutral admission, never a gain claim."""
    if not before or set(before) != set(after) or not rehearsal:
        raise ValueError('complete matching regression and rehearsal observations required')
    if any(type(v) is not bool for v in [*before.values(), *after.values(), *rehearsal.values()]):
        raise ValueError('gate requires real complete boolean observations')
    losses = [k for k in before if before[k] and not after[k]]
    gains = [k for k in before if not before[k] and after[k]]
    accepted = not losses and any(after.values()) and all(rehearsal.values())
    return {'accepted': accepted, 'decision': 'candidate_available' if accepted else 'rollback_keep_previous',
        'losses': losses, 'gains': gains, 'before_passed': sum(before.values()),
        'after_passed': sum(after.values()), 'regression_total': len(before),
        'rehearsal_passed': sum(rehearsal.values()), 'rehearsal_total': len(rehearsal),
        'quality_improvement_claimed': False, 'gate_scope': 'known_public_development_contracts'}


class LearningService:
    def __init__(self, root, runtime):
        self.root, self.runtime = Path(root).resolve(), runtime
        self.directory = self.root / 'results/workbench/training'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.router = WorkbenchRouter()
        self.jobs = {}
        for path in self.directory.glob('*/job.json'):
            job = json.loads(path.read_text(encoding='utf-8'))
            if job['status'] in ('queued', 'running'):
                job.update(status='interrupted', error='服务重启，未完成训练没有自动重放', finished_at=now())
                write_json(path, job)
            self.jobs[job['id']] = job

    def _save(self, job):
        write_json(self.directory / job['id'] / 'job.json', job)

    def _event(self, job, stage, message, **data):
        with self.runtime.lock:
            job['timeline'].append({'at': now(), 'stage': stage, 'message': message, **data})
            self._save(job)

    def active(self):
        path = self.directory / 'active.json'
        if not path.is_file():
            return None
        active = json.loads(path.read_text(encoding='utf-8'))
        directory = (self.directory / active['candidate_id'] / 'adapter').resolve()
        if not directory.is_relative_to(self.directory):
            raise ValueError('active adapter path escapes training directory')
        weights = directory / 'adapter_model.safetensors'
        if not weights.is_file():
            raise ValueError('active adapter weights are missing')
        job = self.jobs.get(active['candidate_id']) or {}
        if job.get('status') != 'completed' or not (job.get('gate') or {}).get('accepted'):
            raise ValueError('active adapter has no accepted completed training job')
        self._verify_adapter(directory, job)
        active['adapter_dir'] = str(directory)
        return active

    @staticmethod
    def _verify_adapter(directory, job):
        from src.runtime.local_model import file_sha256
        metrics = job.get('metrics') or {}
        hashes = metrics.get('adapter_files_sha256') or {'adapter_model.safetensors': metrics.get('adapter_sha256')}
        for name, expected in hashes.items():
            path = directory / name
            if path.name != name or not expected or not path.is_file() or file_sha256(path) != expected:
                raise ValueError('candidate adapter integrity mismatch: ' + name)

    def status(self):
        with self.runtime.lock:
            selected, rejected = select_experiences(self.runtime.experiences(), self.runtime.runs)
            jobs = sorted(self.jobs.values(), key=lambda j: j['created_at'], reverse=True)
            return {'source': 'local_live', 'eligible_experiences': [
                {'id': e['experience_id'], 'title': e['task']['title'], 'source_run_id': e['source_run_id'],
                 'scope': e['task']['scope'], 'version': e['task']['version']} for e in selected],
                'selection_rejections': rejected, 'minimum_examples': 2, 'active': self.active(),
                'jobs': deepcopy(jobs), 'candidates': deepcopy([j for j in jobs if (j.get('gate') or {}).get('accepted')]),
                'routing': {'policy': ROUTING_POLICY, 'actor_critic_used': False},
                'claim_boundary': '真实参数更新及公开回归；不声称通用能力或隐藏测试提升'}

    def plan(self, config):
        config = dict(config)
        steps, length, tokens = int(config.get('max_steps', 8)), int(config.get('max_length', 1536)), int(config.get('max_tokens', 384))
        rate = float(config.get('learning_rate', 5e-5))
        if not 1 <= steps <= 24 or not 256 <= length <= 2048 or not 64 <= tokens <= 1024:
            raise ValueError('bounded training limits exceeded')
        if not math.isfinite(rate) or not 1e-6 <= rate <= 2e-4:
            raise ValueError('learning_rate must be finite and between 1e-6 and 2e-4')
        selected, rejected = select_experiences(self.runtime.experiences(), self.runtime.runs, config.get('experience_ids'))
        if config.get('experience_ids') and rejected:
            raise ValueError('requested experience rejected: ' + json.dumps(rejected, ensure_ascii=False))
        selected = selected[:8]
        if len(selected) < 2:
            raise ValueError('至少需要两条不同契约、由真实本地模型生成并通过不少于两个公开测试的经验')
        parent = self.active()
        rehearsal_ids = []
        if parent:
            previous = json.loads((self.directory / parent['candidate_id'] / 'plan.json').read_text(encoding='utf-8'))
            previous_ids = [e['experience_id'] for e in previous['examples']]
            previous_rows, previous_rejections = select_experiences(self.runtime.experiences(), self.runtime.runs, previous_ids)
            if previous_rejections or len(previous_rows) != len(previous_ids):
                raise ValueError('active adapter rehearsal source is archived or invalid; continuing it is blocked')
            identities = {(e['task']['requirement'], e['task']['scope'], e['task']['version']) for e in selected}
            old = [e for e in previous_rows if (e['task']['requirement'], e['task']['scope'], e['task']['version']) not in identities]
            selected = old + selected
            rehearsal_ids = previous_ids
            if len(selected) > 16:
                raise ValueError('cumulative rehearsal exceeds bounded sixteen-example capacity')
        if steps * 2 < len(selected):
            raise ValueError('max_steps too small to execute every new and rehearsal training example')
        from .tasks import TASKS
        seen = {e['task']['requirement'] for e in selected}
        regressions = [deepcopy(t) for t in TASKS if t['requirement'] not in seen][:3]
        if len(regressions) < 2:
            raise ValueError('至少需要两条不参与训练的公开回归契约')
        return {'examples': selected, 'selection_rejections': rejected, 'regression_tasks': regressions,
            'parent_candidate_id': parent['candidate_id'] if parent else None, 'rehearsal_experience_ids': rehearsal_ids,
            'max_steps': steps, 'max_length': length, 'max_tokens': tokens, 'learning_rate': rate,
            'lora': {'r': 8, 'alpha': 16, 'dropout': .05, 'targets': ['q_proj', 'v_proj']},
            'gradient_accumulation': 2, 'seed': 20261018, 'target_source': 'exact_successful_local_generated_code',
            'gate': 'no former passing known public regression lost; all training regeneration passes; at least one regression passes',
            'quality_improvement_claimed': False}

    def submit(self, config):
        with self.runtime.lock:
            if any(j['status'] in ('queued', 'running') for j in self.jobs.values()):
                raise ValueError('已有内化任务在队列中')
            plan = self.plan(config)
            job = {'id': uuid4().hex, 'status': 'queued', 'created_at': now(), 'timeline': [],
                'max_steps': plan['max_steps'], 'example_count': len(plan['examples']),
                'source': 'local_live', 'metrics': None, 'gate': None}
            self.jobs[job['id']] = job
            write_json(self.directory / job['id'] / 'plan.json', plan)
            self._event(job, 'queued', '真实经验训练计划已固定，等待与推理共用的单工作队列')
            self.runtime.pool.submit(self._train, job['id'], plan)
            return deepcopy(job)

    def _release_provider(self):
        self.runtime.provider = None
        self.runtime.model_state = 'unloaded'
        gc.collect()
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def activate(self, identifier):
        # Activation must join the same serial queue: never unload a model while
        # a generation or training operation holds references to it.
        with self.runtime.lock:
            job = self.jobs[identifier]
            if job.get('status') != 'completed' or not (job.get('gate') or {}).get('accepted'):
                raise ValueError('只有完整训练且通过公开回归的候选可以激活')
            if any(j['status'] in ('queued', 'running') for j in self.jobs.values()):
                raise ValueError('请等待当前内化任务完成后再切换适配器')
        # The worker serializes this operation with inference. Do not time out
        # the HTTP request while leaving a later activation queued invisibly.
        return self.runtime.pool.submit(self._activate, identifier).result()

    def _activate(self, identifier):
        job = self.jobs[identifier]
        adapter = self.directory / identifier / 'adapter'
        self._verify_adapter(adapter, job)
        plan = json.loads((self.directory / identifier / 'plan.json').read_text(encoding='utf-8'))
        selected, rejected = select_experiences(self.runtime.experiences(), self.runtime.runs,
            [e['experience_id'] for e in plan['examples']])
        if rejected or len(selected) != len(plan['examples']):
            raise ValueError('candidate source experience has become invalid or archived')
        active = {'candidate_id': identifier, 'activated_at': now(), 'adapter_sha256': job['metrics']['adapter_sha256'],
            'coverage': list({(e['task']['scope'], e['task']['version']) for e in plan['examples']})}
        active['coverage'] = [{'scope': s, 'version': v} for s, v in sorted(active['coverage'])]
        self._event(job, 'activation_ready', '候选及来源完整性验证通过，准备原子切换')
        self._release_provider()
        write_json(self.directory / 'active.json', active)
        # The atomic active pointer is the authoritative commit. A secondary
        # timeline write must not report a failed switch after it committed.
        try:
            self._event(job, 'activated', '已切换到通过公开回归的候选；后续本地推理加载此适配器')
        except OSError:
            pass
        return self.active()

    def _train(self, identifier, plan):
        job = self.jobs[identifier]
        provider, optimizer = None, None
        started = time.monotonic()
        try:
            import torch
            if not torch.cuda.is_available():
                raise RuntimeError('真实LoRA训练要求本地CUDA；未进行模拟或CPU假训练')
            from experiments.humaneval_admission_worker import run_suite
            from src.runtime.local_model import LocalCausalLMProvider, file_sha256
            from .service import code_from_response
            from peft import LoraConfig, TaskType, get_peft_model
            job.update(status='running', started_at=now())
            self._event(job, 'validation', '重放固定训练目标的全部公开测试，防止失效经验进入训练')
            directory = self.directory / identifier
            current, rejected = select_experiences(self.runtime.experiences(), self.runtime.runs,
                [e['experience_id'] for e in plan['examples']])
            if rejected or {(e['experience_id'], e['code_sha256']) for e in current} != {
                    (e['experience_id'], e['code_sha256']) for e in plan['examples']}:
                raise ValueError('queued experience provenance changed or was archived')
            for row in plan['examples']:
                task = row['task']
                result = run_suite(row['code'], task['entry_point'], [c['args'] for c in task['cases']],
                    [c['expected'] for c in task['cases']], timeout=8)
                write_json(directory / 'target_replays' / (row['experience_id'] + '.json'), result)
                if not result['success']:
                    raise ValueError('training target failed actual replay: ' + row['experience_id'])
            parent = self.active()
            if (parent and parent['candidate_id'] != plan.get('parent_candidate_id')) or (not parent and plan.get('parent_candidate_id')):
                raise ValueError('active adapter changed after the training plan was fixed')
            job['parent_candidate_id'] = parent['candidate_id'] if parent else None
            self._release_provider()
            self.runtime.model_state = 'training'
            self._event(job, 'model_loading', '独占工作队列装载当前模型，开始固定公开回归前测')
            provider = LocalCausalLMProvider(self.runtime.model_dir, adapter_dir=Path(parent['adapter_dir']) if parent else None)
            import importlib.metadata
            write_json(directory / 'runtime_identity.json', {
                'model_dir': str(provider.model_dir), 'base_model_files_sha256': provider.model_files_sha256,
                'parent_adapter_sha256': provider.adapter_sha256, 'device': str(provider.device),
                'versions': {name: importlib.metadata.version(name) for name in ('torch', 'transformers', 'peft')},
                'local_files_only': True, 'training_data_source': 'workbench_successful_local_generations'})
            torch.manual_seed(plan['seed'])
            torch.cuda.manual_seed_all(plan['seed'])

            def evaluate(tasks, phase, use_adapter):
                outcomes = {}
                for index, task in enumerate(tasks):
                    response = provider.generate(task_prompt(task), system=SYSTEM, max_tokens=plan['max_tokens'], use_adapter=use_adapter)
                    code = code_from_response(response.content, task['entry_point'])
                    receipt = run_suite(code, task['entry_point'], [c['args'] for c in task['cases']],
                        [c['expected'] for c in task['cases']], timeout=8)
                    key = task.get('id') or digest(task['requirement'])[:16]
                    outcomes[key] = bool(receipt['success'])
                    write_json(directory / phase / f'{index}_{key}.json', {'task': task, 'raw_response': response.content,
                        'code': code, 'model': response.model, 'metadata': response.extra,
                        'prompt_tokens': response.prompt_tokens, 'completion_tokens': response.completion_tokens,
                        'seconds': response.latency, 'receipt': receipt})
                    self._event(job, phase, f"{task['title']}：{'通过' if receipt['success'] else '未通过'}", task=key, success=receipt['success'])
                return outcomes

            before = evaluate(plan['regression_tasks'], 'regression_before', bool(parent))
            tokenizer = provider.tokenizer
            encoded, audits = [], []
            for row in plan['examples']:
                text = tokenizer.apply_chat_template([{'role': 'system', 'content': SYSTEM},
                    {'role': 'user', 'content': row['prompt']}], tokenize=False, add_generation_prompt=True)
                prefix = tokenizer(text, add_special_tokens=False)['input_ids']
                target = tokenizer(row['code'] + tokenizer.eos_token, add_special_tokens=False)['input_ids']
                if len(prefix) + len(target) > plan['max_length']:
                    raise ValueError('complete target/prompt exceeds training budget; truncation forbidden')
                encoded.append((prefix + target, [-100] * len(prefix) + target))
                audits.append({'experience_id': row['experience_id'], 'source_run_id': row['source_run_id'],
                    'code_sha256': row['code_sha256'], 'prefix_tokens': len(prefix), 'target_tokens': len(target)})
            write_json(directory / 'training_target_audit.json', audits)
            if not parent:
                lc = plan['lora']
                provider.model = get_peft_model(provider.model, LoraConfig(task_type=TaskType.CAUSAL_LM,
                    r=lc['r'], lora_alpha=lc['alpha'], lora_dropout=lc['dropout'], target_modules=lc['targets'], bias='none'))
            model = provider.model
            for name, parameter in model.named_parameters():
                parameter.requires_grad_('lora_' in name)
            trainable = [p for p in model.parameters() if p.requires_grad]
            if not trainable or any(p.requires_grad and 'lora_' not in name for name, p in model.named_parameters()):
                raise ValueError('only real adapter parameters may be updated')

            def parameters_hash():
                hasher = hashlib.sha256()
                for name, parameter in sorted(model.named_parameters()):
                    if parameter.requires_grad:
                        hasher.update(name.encode())
                        hasher.update(parameter.detach().float().cpu().contiguous().numpy().tobytes())
                return hasher.hexdigest()

            initial = parameters_hash()
            model.config.use_cache = False
            model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
            model.enable_input_require_grads()
            model.train()
            optimizer = torch.optim.AdamW(trainable, lr=plan['learning_rate'])
            steps = []
            torch.cuda.reset_peak_memory_stats()
            self._event(job, 'training', '执行目标token掩码交叉熵训练；只更新LoRA参数')
            for step in range(plan['max_steps']):
                optimizer.zero_grad(set_to_none=True)
                losses = []
                for micro in range(plan['gradient_accumulation']):
                    ids, labels = encoded[(step * plan['gradient_accumulation'] + micro) % len(encoded)]
                    x = torch.tensor([ids], device=provider.device)
                    y = torch.tensor([labels], device=provider.device)
                    logits = model(input_ids=x, attention_mask=torch.ones_like(x), use_cache=False).logits
                    shifted = y[:, 1:]
                    mask = shifted != -100
                    loss = torch.nn.functional.cross_entropy(logits[:, :-1, :][mask].float(), shifted[mask])
                    if not torch.isfinite(loss):
                        raise ValueError('nonfinite actual training loss')
                    (loss / plan['gradient_accumulation']).backward()
                    losses.append(float(loss.detach().cpu()))
                    del logits, loss, x, y
                grad_norm = torch.nn.utils.clip_grad_norm_(trainable, 1.0)
                if not torch.isfinite(grad_norm):
                    raise ValueError('nonfinite actual training gradient')
                optimizer.step()
                metrics = {'step': step + 1, 'target_cross_entropy': sum(losses) / len(losses),
                    'gradient_norm': float(grad_norm.detach().cpu()), 'elapsed_seconds': time.monotonic() - started}
                steps.append(metrics)
                write_json(directory / 'optimizer_steps.json', steps)
                self._event(job, 'optimizer_step', f"真实优化步骤 {step + 1}/{plan['max_steps']}", **metrics)
            final = parameters_hash()
            if initial == final:
                raise ValueError('adapter parameter hash did not change')
            model.eval()
            model.gradient_checkpointing_disable()
            model.config.use_cache = True
            model.save_pretrained(directory / 'adapter')
            tokenizer.save_pretrained(directory / 'adapter')
            weight_hash = file_sha256(directory / 'adapter/adapter_model.safetensors')
            provider.adapter_dir = directory / 'adapter'
            provider.adapter_sha256 = weight_hash
            job['metrics'] = {'optimizer_steps': len(steps), 'target_cross_entropy_first': steps[0]['target_cross_entropy'],
                'target_cross_entropy_last': steps[-1]['target_cross_entropy'], 'initial_parameters_sha256': initial,
                'final_parameters_sha256': final, 'adapter_sha256': weight_hash,
                'trainable_parameters': sum(p.numel() for p in trainable),
                'peak_cuda_memory_mib': torch.cuda.max_memory_allocated() / 2**20,
                'seconds': time.monotonic() - started, 'quality_improvement_claimed': False}
            job['metrics']['adapter_files_sha256'] = {name: file_sha256(directory / 'adapter' / name)
                for name in ('adapter_model.safetensors', 'adapter_config.json')}
            write_json(directory / 'training_metrics.json', job['metrics'])
            del optimizer
            optimizer = None
            torch.cuda.empty_cache()
            after = evaluate(plan['regression_tasks'], 'regression_after', True)
            rehearsal = evaluate([e['task'] for e in plan['examples']], 'training_regeneration', True)
            job['gate'] = regression_gate(before, after, rehearsal)
            write_json(directory / 'gate.json', {'before': before, 'after': after, 'rehearsal': rehearsal, **job['gate']})
            job.update(status='completed', finished_at=now(), elapsed_seconds=time.monotonic() - started)
            self._event(job, 'completed', '候选通过公开回归，可手动切换使用；中性结果不代表质量提升' if job['gate']['accepted'] else '候选未通过回归，保留原模型及失败记录')
        except Exception as error:
            job.update(status='failed', error=f'{type(error).__name__}: {error}', finished_at=now(), elapsed_seconds=time.monotonic() - started)
            self._event(job, 'error', job['error'])
        finally:
            # Drop local references before empty_cache; old active pointer/files
            # are untouched even when training, evaluation, or saving fails.
            provider, optimizer = None, None
            try:
                model = None
                trainable = None
                parameter = None
                self._release_provider()
            except Exception:
                self.runtime.model_state = 'unloaded'


def create_learning_router(service):
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field

    class TrainRequest(BaseModel):
        experience_ids: list[str] = Field(default_factory=list, max_length=8)
        max_steps: int = Field(default=8, ge=1, le=24)
        max_length: int = Field(default=1536, ge=256, le=2048)
        max_tokens: int = Field(default=384, ge=64, le=1024)
        learning_rate: float = Field(default=5e-5, ge=1e-6, le=2e-4)

    if not hasattr(service, 'learning'):
        service.learning = LearningService(service.root, service)
    learning = service.learning
    router = APIRouter(prefix='/api/workbench/learning', tags=['workbench learning'])

    @router.get('/status')
    def status():
        return learning.status()

    # FastAPI resolves local types at registration when the annotation is an
    # actual class, avoiding unresolved forward references with local schemas.
    def train(request):
        try:
            return learning.submit(request.model_dump())
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
    train.__annotations__['request'] = TrainRequest
    router.post('/train', status_code=202)(train)

    @router.get('/jobs/{identifier}')
    def job(identifier: str):
        with service.lock:
            if identifier not in learning.jobs:
                raise HTTPException(status_code=404, detail='unknown training job')
            return deepcopy(learning.jobs[identifier])

    @router.post('/activate/{identifier}')
    def activate(identifier: str):
        try:
            return learning.activate(identifier)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    return router
