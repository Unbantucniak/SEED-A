"""Public-feedback bridge for future sequential task runners.

This is an in-memory adapter, not an experiment runner or evidence of continual
learning gains. Each arm owns a deep copy of its seed graph. The caller must keep
hidden grading outside this API and supply only execution-visible feedback.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import math
import re
from typing import Any, Mapping, Optional
from uuid import uuid4

from src.experience_graph.model import ExperienceGraph
from src.experience_graph.operations import GraphOperations
from src.experience_manager.manager import ExperienceManager


class FeedbackSource(str, Enum):
    PUBLIC_EXECUTION = "public_execution"
    HIDDEN_HOLDOUT = "hidden_holdout"


@dataclass(frozen=True)
class PublicExecutionEvidence:
    """Immutable execution receipt supplied by a trusted public-test runner.

    Hashes bind the exact UTF-8 artifact, public test manifest, and executor.
    A receipt is an auditable assertion, not a cryptographic attestation that
    execution occurred. The integration must create it at the public runner
    boundary, never by converting a hidden grader result.
    """

    source: FeedbackSource
    task_id: str
    memory_scope: str
    memory_version: str
    code_sha256: str
    public_test_set_id: str
    public_test_set_sha256: str
    executor_id: str
    executor_sha256: str
    tests_passed: int
    tests_total: int
    execution_time: float
    is_success: bool

    def __post_init__(self):
        if FeedbackSource(self.source) is not FeedbackSource.PUBLIC_EXECUTION:
            raise ValueError("hidden_holdout cannot produce public execution evidence")
        object.__setattr__(self, "source", FeedbackSource.PUBLIC_EXECUTION)
        for key in ("task_id", "memory_scope", "memory_version", "public_test_set_id", "executor_id"):
            value = getattr(self, key)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError(f"evidence {key} must be a nonempty canonical string")
        for key in ("code_sha256", "public_test_set_sha256", "executor_sha256"):
            value = getattr(self, key)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError(f"evidence {key} must be a lowercase SHA-256 digest")
        if not (type(self.tests_passed) is int and type(self.tests_total) is int
                and self.tests_total > 0 and 0 <= self.tests_passed <= self.tests_total):
            raise ValueError("evidence public test counts must satisfy 0 <= passed <= total and total > 0")
        if (isinstance(self.execution_time, bool) or not isinstance(self.execution_time, (int, float))
                or not math.isfinite(self.execution_time) or self.execution_time < 0):
            raise ValueError("evidence execution_time must be finite and nonnegative")
        if type(self.is_success) is not bool:
            raise ValueError("evidence is_success must be boolean")


@dataclass(frozen=True)
class MemoryArm:
    require_validation: bool = True
    require_compatibility: bool = True
    filter_versions: bool = True
    require_execution_evidence: bool = False


@dataclass(frozen=True)
class TaskSession:
    session_id: str
    task_id: str
    memory_scope: str
    memory_version: str
    requirement: str
    user_instruction: str
    task_type: str
    public_test_set_id: Optional[str] = None
    public_test_set_sha256: Optional[str] = None
    executor_id: Optional[str] = None
    executor_sha256: Optional[str] = None


class VerifiedEpisodeMemory:
    """Keep reusable successful episodes isolated by arm, project and version.

    ``start_task`` accepts the public task projection and reads only named
    fields; tests, expected answers, hidden scores and arbitrary metadata are
    never forwarded to ExperienceManager. ``record_public_feedback`` has an
    explicit scalar interface instead of accepting an opaque grading dict.
    Version compatibility means exact declared version equality, including
    rollback; this adapter does not infer API compatibility from version order.
    """

    def __init__(self, arm_id: str, *, policy: Optional[MemoryArm] = None,
                 seed_graph: Optional[ExperienceGraph] = None):
        if not arm_id.strip():
            raise ValueError("arm_id must be nonempty")
        self.arm_id = arm_id
        self.policy = policy or MemoryArm()
        self.graph_ops = GraphOperations(
            graph=deepcopy(seed_graph) if seed_graph is not None else ExperienceGraph(),
            config={"use_hybrid_retrieval": False, "auto_add_similarity_edges": False},
        )
        self.manager = ExperienceManager(self.graph_ops)
        self._sessions: dict[str, TaskSession] = {}
        self._closed: set[str] = set()
        self.quarantine: list[dict[str, str]] = []
        self.last_retrieval_diagnostics: dict[str, Any] = {}

    def start_task(self, public_task: Mapping[str, Any]) -> TaskSession:
        """Create a session from public metadata.memory_scope/memory_version."""
        metadata = public_task.get("metadata") or {}
        if not isinstance(metadata, Mapping):
            raise ValueError("public task metadata must be a mapping")
        scope = metadata.get("memory_scope")
        version = metadata.get("memory_version")
        requirement = public_task.get("requirement") or public_task.get("original_requirement")
        task_id = public_task.get("task_id")
        for key, value in (("memory_scope", scope), ("memory_version", version),
                           ("requirement", requirement), ("task_id", task_id)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"public task {key} must be a nonempty string")
        for key in ("public_test_set_id", "public_test_set_sha256", "executor_id", "executor_sha256"):
            value = metadata.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()
                                      or value != value.strip()):
                raise ValueError(f"public task manifest {key} must be a canonical string")
            if value is not None and key.endswith("sha256") and not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError(f"public task manifest {key} must be a lowercase SHA-256 digest")
        session = TaskSession(
            session_id=str(uuid4()), task_id=task_id, memory_scope=scope.strip(),
            memory_version=version.strip(), requirement=requirement,
            user_instruction=str(public_task.get("user_instruction") or ""),
            task_type=str(public_task.get("task_type") or "code_generation"),
            **{key: metadata.get(key) for key in (
                "public_test_set_id", "public_test_set_sha256", "executor_id", "executor_sha256",
            )},
        )
        self._sessions[session.session_id] = session
        return session

    def _check_session(self, session: TaskSession) -> None:
        if self._sessions.get(session.session_id) != session:
            raise ValueError("task session does not belong to this memory arm")

    def record_public_feedback(
        self, session: TaskSession, *, source: FeedbackSource,
        final_output: str, is_success: bool, execution_time: float,
        tests_passed: Optional[int] = None, tests_total: Optional[int] = None,
    ) -> Optional[str]:
        """Legacy engineering-count entry point; no execution receipt binding.

        Failed executions are quarantined as IDs/reasons, without reusable
        content. Hidden feedback is rejected before any state mutation, even
        in the validation ablation. Missing tests can only enter an arm with
        require_validation=False and remain explicitly unvalidated there.
        """
        if FeedbackSource(source) is not FeedbackSource.PUBLIC_EXECUTION:
            raise ValueError("hidden_holdout feedback must never enter episode memory")
        self._check_session(session)
        if session.session_id in self._closed:
            raise ValueError("task session already has terminal feedback")
        if type(is_success) is not bool:
            raise ValueError("is_success must be boolean public execution feedback")
        if (isinstance(execution_time, bool) or not isinstance(execution_time, (int, float))
                or not math.isfinite(execution_time) or execution_time < 0):
            raise ValueError("execution_time must be finite and nonnegative")
        if not isinstance(final_output, str) or (is_success and not final_output.strip()):
            raise ValueError("successful final_output must be a nonempty public execution artifact")
        has_counts = tests_passed is not None or tests_total is not None
        if has_counts and not (type(tests_passed) is int and type(tests_total) is int
                               and tests_total > 0 and 0 <= tests_passed <= tests_total):
            raise ValueError("public test counts must satisfy 0 <= passed <= total and total > 0")
        self._closed.add(session.session_id)
        if not is_success or (has_counts and tests_passed != tests_total):
            self.quarantine.append({"task_id": session.task_id, "reason": "public_execution_failed"})
            return None
        raw = {
            "original_requirement": session.requirement,
            "user_instruction": session.user_instruction,
            "task_type": session.task_type,
            "final_output": final_output,
            "is_success": True,
            "execution_time": execution_time,
            "source_credibility": 0.9,
            "environment_config": {
                "memory_scope": session.memory_scope,
                "memory_version": session.memory_version,
                "source_task_id": session.task_id,
                "feedback_source": FeedbackSource.PUBLIC_EXECUTION.value,
                "memory_arm": self.arm_id,
                "verification_kind": "legacy_public_counts",
                "credential_verified": False,
            },
        }
        if has_counts:
            raw.update(tests_passed=tests_passed, tests_total=tests_total,
                       test_pass_rate=tests_passed / tests_total)
        identifier = self.manager.add_candidate_experience(
            raw, auto_verify=self.policy.require_validation,
        )
        if identifier is None:
            self.quarantine.append({"task_id": session.task_id, "reason": "admission_rejected"})
        else:
            result = self.graph_ops.get_experience(identifier).execution_result
            result.validation_notes = "legacy_public_counts; no bound execution receipt; " + (result.validation_notes or "")
        return identifier

    def record_execution_evidence(
        self, session: TaskSession, evidence: PublicExecutionEvidence, final_output: str,
    ) -> Optional[str]:
        """Admit a receipt only for its exact task/context/artifact.

        Declared public runner manifests in task metadata must match too. An
        integration should provide those declarations so the adapter can check
        identities independently of the receipt. Rejected bindings do not close
        the task session or change the graph.
        """
        if not isinstance(evidence, PublicExecutionEvidence):
            raise TypeError("evidence must be PublicExecutionEvidence")
        evidence.__post_init__()  # defense against illicit mutation/deserialization
        self._check_session(session)
        for key in ("task_id", "memory_scope", "memory_version"):
            if getattr(evidence, key) != getattr(session, key):
                raise ValueError(f"execution evidence {key} does not match task session")
        if not isinstance(final_output, str):
            raise ValueError("final_output must be the exact tested code string")
        if hashlib.sha256(final_output.encode("utf-8")).hexdigest() != evidence.code_sha256:
            raise ValueError("execution evidence code_sha256 does not match final_output")
        for key in ("public_test_set_id", "public_test_set_sha256", "executor_id", "executor_sha256"):
            expected = getattr(session, key)
            if expected is not None and expected != getattr(evidence, key):
                raise ValueError(f"execution evidence {key} does not match public task manifest")
        identifier = self.record_public_feedback(
            session, source=evidence.source, final_output=final_output,
            is_success=evidence.is_success, execution_time=evidence.execution_time,
            tests_passed=evidence.tests_passed, tests_total=evidence.tests_total,
        )
        if identifier is not None:
            exp = self.graph_ops.get_experience(identifier)
            env = exp.context_state.environment_config
            env["public_execution_evidence"] = asdict(evidence)
            env["public_execution_evidence"]["source"] = evidence.source.value
            env["verification_kind"] = "bound_public_execution_receipt"
            env["credential_verified"] = True
            result = exp.execution_result
            result.validation_notes = (
                "bound_public_execution_receipt; code/test-set/executor SHA-256 recorded; "
                + (result.validation_notes or "").replace(
                    "legacy_public_counts; no bound execution receipt; ", "", 1,
                )
            )
        return identifier

    def compatible_search(self, session: TaskSession, top_k: int = 5) -> list[dict[str, Any]]:
        """Apply compatibility before truncating semantic candidates.

        Compatibility (scope plus version) and objective-verification gates
        are independently switchable for explicit research arms. A narrower
        version-only ablation is also available. Returned records are
        copies, so consumer annotations cannot modify this arm's graph.
        """
        self._check_session(session)
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        candidates = self.graph_ops.semantic_search(
            f"{session.requirement} {session.user_instruction}",
            top_k=max(top_k, len(self.graph_ops.graph.experience_nodes)),
        )
        accepted = []
        dropped = {"unknown_context": 0, "scope_mismatch": 0,
                   "version_mismatch": 0, "failed": 0, "unvalidated": 0,
                   "missing_execution_evidence": 0}
        for item in candidates:
            exp = item["experience"]
            env = exp.context_state.environment_config
            result = exp.execution_result
            if self.policy.require_compatibility and (
                not env.get("memory_scope")
                or (self.policy.filter_versions and not env.get("memory_version"))
            ):
                dropped["unknown_context"] += 1
                continue
            if self.policy.require_compatibility and env.get("memory_scope") != session.memory_scope:
                dropped["scope_mismatch"] += 1
                continue
            if (self.policy.require_compatibility and self.policy.filter_versions
                    and env.get("memory_version") != session.memory_version):
                dropped["version_mismatch"] += 1
                continue
            if not result.is_success or result.error_info:
                dropped["failed"] += 1
                continue
            if self.policy.require_execution_evidence:
                try:
                    bound = PublicExecutionEvidence(**env.get("public_execution_evidence", {}))
                    receipt_valid = (
                        env.get("credential_verified") is True
                        and bound.task_id == env.get("source_task_id")
                        and bound.memory_scope == env.get("memory_scope")
                        and bound.memory_version == env.get("memory_version")
                        and bound.code_sha256 == hashlib.sha256(result.final_output.encode("utf-8")).hexdigest()
                        and bound.is_success and bound.tests_passed == bound.tests_total
                    )
                except (TypeError, ValueError):
                    receipt_valid = False
                if not receipt_valid:
                    dropped["missing_execution_evidence"] += 1
                    continue
            if self.policy.require_validation and (
                not result.solution_validated or result.test_pass_rate != 1.0
                or "human_reported" in (result.validation_notes or "")
                or "verification_mode:human_reported" in exp.static_meta.domain_tags
                or "[verification_mode:human_reported]" in exp.task_intent.user_instruction
            ):
                dropped["unvalidated"] += 1
                continue
            accepted.append(deepcopy(item))
        self.last_retrieval_diagnostics = {
            "arm_id": self.arm_id, "candidate_count": len(candidates),
            "accepted_count": min(top_k, len(accepted)), "dropped": dropped,
            "require_compatibility": self.policy.require_compatibility,
            "filter_versions": self.policy.filter_versions,
            "require_validation": self.policy.require_validation,
            "require_execution_evidence": self.policy.require_execution_evidence,
            "target_scope": session.memory_scope, "target_version": session.memory_version,
        }
        return accepted[:top_k]
