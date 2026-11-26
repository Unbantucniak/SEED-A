"""Typed literal anti-unification for auditable Python template candidates.

The algorithm abstracts only differing scalar literals at matching AST paths.
It never infers that a new binding is correct, equivalent, or safe to execute.
Callers must validate every instantiated program against its current contract.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping, Sequence


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _literal_type(value: Any) -> str:
    kind = type(value)
    if kind not in (str, int, float, bool, type(None)):
        raise ValueError("Only finite JSON-compatible scalar literals are supported")
    if kind is float and not math.isfinite(value):
        raise ValueError("Non-finite literals are not supported")
    return kind.__name__


@dataclass(frozen=True)
class TemplateSource:
    source_id: str
    code: str
    scope: str
    version: str


@dataclass(frozen=True)
class LiteralSlot:
    name: str
    path: tuple[str | int, ...]
    python_type: str
    observed_values: tuple[Any, ...]


@dataclass(frozen=True)
class LiteralTemplate:
    scope: str
    version: str
    base_code: str
    slots: tuple[LiteralSlot, ...]
    sources: tuple[tuple[str, str], ...]
    fingerprint: str

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": "python-literal-template-v1",
            "method": "matching_ast_with_typed_literal_slots",
            "scope": self.scope, "version": self.version,
            "base_code": self.base_code,
            "slots": [{"name": s.name, "path": list(s.path), "python_type": s.python_type,
                       "observed_values": list(s.observed_values)} for s in self.slots],
            "sources": [{"source_id": sid, "code_sha256": digest} for sid, digest in self.sources],
            "validation_status": "pending_each_instantiation",
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "fingerprint": self.fingerprint}

    def bindings_for_source(self, source_id: str) -> dict[str, Any]:
        ids = [sid for sid, _ in self.sources]
        if source_id not in ids:
            raise KeyError(source_id)
        position = ids.index(source_id)
        return {slot.name: slot.observed_values[position] for slot in self.slots}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LiteralTemplate":
        expected = {"schema_version", "method", "scope", "version", "base_code", "slots",
                    "sources", "validation_status", "fingerprint"}
        if set(value) != expected or value["schema_version"] != "python-literal-template-v1":
            raise ValueError("Unsupported template schema")
        if value["method"] != "matching_ast_with_typed_literal_slots" or value["validation_status"] != "pending_each_instantiation":
            raise ValueError("Unsupported template method or validation claim")
        slots = tuple(LiteralSlot(s["name"], tuple(s["path"]), s["python_type"], tuple(s["observed_values"]))
                      for s in value["slots"])
        sources = tuple((s["source_id"], s["code_sha256"]) for s in value["sources"])
        result = cls(value["scope"], value["version"], value["base_code"], slots, sources, value["fingerprint"])
        _validate_template(result)
        return result


def _parse(code: str) -> ast.Module:
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Python source is required")
    tree = ast.parse(code, mode="exec")
    compile(tree, "<template-candidate>", "exec")
    return tree


def induce_literal_template(sources: Sequence[TemplateSource], *, max_slots: int = 32) -> LiteralTemplate:
    """Produce an unvalidated template; different syntax/identifiers are rejected.

    Source IDs and parameter order are deterministic under input reordering.
    Scope/version describe the declared application boundary, not correctness.
    """
    members = sorted(sources, key=lambda source: source.source_id)
    if len(members) < 2 or len({s.source_id for s in members}) != len(members):
        raise ValueError("At least two uniquely identified source programs are required")
    if any(not s.source_id or not s.scope or not s.version for s in members):
        raise ValueError("Explicit source IDs, scope, and version are required")
    if len({(s.scope, s.version) for s in members}) != 1:
        raise ValueError("Cannot abstract across declared scope/version boundaries")
    if type(max_slots) is not int or max_slots < 1:
        raise ValueError("max_slots must be positive")
    trees = [_parse(source.code) for source in members]
    slots: list[LiteralSlot] = []

    def visit(nodes: Sequence[Any], path: tuple[str | int, ...]) -> None:
        first = nodes[0]
        if any(type(node) is not type(first) for node in nodes):
            raise ValueError(f"Incompatible AST shape at {path}")
        if isinstance(first, ast.Constant):
            values = [node.value for node in nodes]
            kinds = [_literal_type(value) for value in values]
            if len(set(kinds)) != 1:
                raise ValueError(f"Literal type differs at {path}")
            if any(node.kind != first.kind for node in nodes):
                raise ValueError(f"Literal kind differs at {path}")
            # JSON encoding distinguishes -0.0 from 0.0; bool and int were checked above.
            if len({_digest(value) for value in values}) > 1:
                slots.append(LiteralSlot(f"literal_{len(slots)}", path, kinds[0], tuple(values)))
                if len(slots) > max_slots:
                    raise ValueError("Template exceeds the declared slot bound")
        elif isinstance(first, ast.AST):
            for name in first._fields:
                visit([getattr(node, name) for node in nodes], path + (name,))
        elif isinstance(first, list):
            if any(len(node) != len(first) for node in nodes):
                raise ValueError(f"Incompatible statement/list shape at {path}")
            for index in range(len(first)):
                visit([node[index] for node in nodes], path + (index,))
        elif any(node != first for node in nodes):
            raise ValueError(f"Nonliteral syntax or identifier differs at {path}")

    visit(trees, ())
    if not slots:
        raise ValueError("Identical syntax has no differing literals to abstract")
    # Unparsing may change AST representation (notably negative literals), so retain
    # original source as the path anchor, not a reformatted surrogate.
    source_hashes = tuple((s.source_id, hashlib.sha256(s.code.encode("utf-8")).hexdigest()) for s in members)
    draft = LiteralTemplate(members[0].scope, members[0].version, members[0].code,
                            tuple(slots), source_hashes, "")
    result = LiteralTemplate(draft.scope, draft.version, draft.base_code, draft.slots,
                             draft.sources, _digest(draft.payload()))
    _validate_template(result)
    return result


def _node_at(tree: ast.AST, path: tuple[str | int, ...]) -> ast.AST:
    node: Any = tree
    for part in path:
        if type(part) is str and isinstance(node, ast.AST) and part in node._fields:
            node = getattr(node, part)
        elif type(part) is int and isinstance(node, list) and 0 <= part < len(node):
            node = node[part]
        else:
            raise ValueError("Invalid AST slot path")
    if not isinstance(node, ast.Constant):
        raise ValueError("A slot must address a literal node")
    return node


def _validate_template(template: LiteralTemplate) -> None:
    if _digest(template.payload()) != template.fingerprint:
        raise ValueError("Template fingerprint mismatch")
    if not template.scope or not template.version or len(template.sources) < 2 or not template.slots:
        raise ValueError("Template identity is incomplete")
    if len({sid for sid, _ in template.sources}) != len(template.sources):
        raise ValueError("Duplicate template source IDs")
    if len({slot.path for slot in template.slots}) != len(template.slots):
        raise ValueError("Duplicate slot paths")
    tree = _parse(template.base_code)
    if hashlib.sha256(template.base_code.encode("utf-8")).hexdigest() != template.sources[0][1]:
        raise ValueError("Base source digest mismatch")
    for index, slot in enumerate(template.slots):
        if slot.name != f"literal_{index}" or len(slot.observed_values) != len(template.sources):
            raise ValueError("Invalid slot identity or observation coverage")
        literal = _node_at(tree, slot.path)
        if any(_literal_type(value) != slot.python_type for value in slot.observed_values):
            raise ValueError("Observed literal types differ")
        if _digest(literal.value) != _digest(slot.observed_values[0]):
            raise ValueError("Slot observations do not match the base source")


def instantiate_literal_template(template: LiteralTemplate, bindings: Mapping[str, Any], *,
                                 scope: str, version: str) -> str:
    """Render a candidate for explicit bindings; never execute or mark it valid."""
    _validate_template(template)
    if (scope, version) != (template.scope, template.version):
        raise ValueError("Template scope/version mismatch")
    if set(bindings) != {slot.name for slot in template.slots}:
        raise ValueError("Bindings must cover exactly the declared slots")
    tree = deepcopy(_parse(template.base_code))
    for slot in template.slots:
        value = bindings[slot.name]
        if _literal_type(value) != slot.python_type:
            raise ValueError(f"Literal type mismatch for {slot.name}")
        literal = _node_at(tree, slot.path)
        literal.value = value
    ast.fix_missing_locations(tree)
    compile(tree, "<instantiated-template-candidate>", "exec")
    return ast.unparse(tree) + "\n"
