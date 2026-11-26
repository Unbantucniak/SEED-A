"""Shared conservative lifecycle state and applicability rules.

Statuses preserve source nodes; they do not constitute proof of correctness.
Public receipts are trusted-runner assertions, not authenticated attestations.
"""
from __future__ import annotations
import hashlib
import json
from typing import Any
from src.experience_graph.model import ExperienceUnit


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def lifecycle(exp: ExperienceUnit) -> dict:
    value = exp.context_state.environment_config.get("lifecycle", {})
    return value if isinstance(value, dict) else {"state": "pending"}


def state(exp: ExperienceUnit) -> str:
    attributes=lifecycle(exp)
    value=attributes.get("state")
    if isinstance(value,str) and value in {"active","pending","archived"}: return value
    # Old synthesized templates did not have a status and carried unearned
    # success flags. Absence of a lifecycle record cannot make them eligible.
    if "template" in exp.constraints or "state" in attributes: return "pending"
    return "active"


def public_manifest_projection(value: dict) -> dict:
    """Read/store named public contract fields, discarding arbitrary grader data."""
    metadata=value.get("metadata",{})
    allowed=("memory_scope","memory_version","public_test_set_id","public_test_set_sha256",
             "executor_id","executor_sha256","applicability_conditions","dependency_versions")
    return {"task_id":value.get("task_id"),"requirement":value.get("requirement",value.get("issue")),
            "user_instruction":value.get("user_instruction",""),"task_type":value.get("task_type"),
            "metadata":{key:metadata[key] for key in allowed if key in metadata}}


def is_active(exp: ExperienceUnit) -> bool:
    return state(exp) == "active"


def counts(graph) -> dict[str, int]:
    nodes = list(graph.experience_nodes.values())
    return {"physical_nodes": len(nodes), "active_nodes": sum(is_active(n) for n in nodes),
            "pending_nodes": sum(state(n) == "pending" for n in nodes),
            "archived_nodes": sum(state(n) == "archived" for n in nodes)}


def applicability(exp: ExperienceUnit) -> dict:
    env = exp.context_state.environment_config
    return {"memory_scope": env.get("memory_scope"), "memory_version": env.get("memory_version"),
            "dependency_versions": exp.context_state.dependency_versions,
            "conditions": env.get("applicability_conditions", {}),
            "constraints": sorted(c for c in exp.constraints if c not in {"template", "auto_generalized"})}


def same_applicability(a: ExperienceUnit, b: ExperienceUnit) -> bool:
    return applicability(a) == applicability(b)


def explicit_applicability(exp: ExperienceUnit) -> bool:
    value = applicability(exp)
    return all(isinstance(value[k], str) and value[k].strip() == value[k] and value[k] for k in ("memory_scope", "memory_version"))


def contract_key(exp: ExperienceUnit) -> str:
    # Do not infer equivalence of different requirements or instructions.
    return canonical({"requirement": " ".join(exp.task_intent.original_requirement.split()),
        "instruction": " ".join(exp.task_intent.user_instruction.split()), "type": exp.task_intent.task_type,
        "applicability": applicability(exp)})


def source_fingerprint(exp: ExperienceUnit) -> str:
    return hashlib.sha256(canonical({"contract": contract_key(exp), "output": exp.execution_result.final_output,
        "receipt": exp.context_state.environment_config.get("public_execution_evidence"),
        "validated": exp.execution_result.solution_validated, "success": exp.execution_result.is_success}).encode()).hexdigest()


def bound_receipt(exp: ExperienceUnit):
    """Validate an exact stored public receipt without executing any code."""
    from src.runtime.verified_episode_memory import PublicExecutionEvidence
    env = exp.context_state.environment_config
    if env.get("credential_verified") is not True:
        return None
    try:
        receipt = PublicExecutionEvidence(**env.get("public_execution_evidence", {}))
    except (TypeError, ValueError):
        return None
    if (receipt.task_id != env.get("source_task_id") or receipt.memory_scope != env.get("memory_scope")
            or receipt.memory_version != env.get("memory_version")
            or receipt.code_sha256 != hashlib.sha256(exp.execution_result.final_output.encode()).hexdigest()
            or receipt.is_success != exp.execution_result.is_success
            or receipt.is_success != (receipt.tests_passed == receipt.tests_total)):
        return None
    return receipt


def archive(exp: ExperienceUnit, *, reason: str, decision_id: str, superseded_by: str | None = None):
    previous = dict(lifecycle(exp))
    previous.update(state="archived", reason=reason, decision_id=decision_id, superseded_by=superseded_by)
    exp.context_state.environment_config["lifecycle"] = previous
