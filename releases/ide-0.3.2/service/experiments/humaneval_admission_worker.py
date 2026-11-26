"""Credential-free CPU evaluator for admission experiments.

This is an accident guard, not an OS security boundary. The entire suite has a
wall-clock timeout. JSONL progress preserves completed observations on timeout;
an interrupted invocation is explicitly unobserved, never an executed result.
``actual`` values use ``encode_value``; use ``decode_value`` for reference values.

Comparison follows EvalPlus's ordinary oracle (not its task-specific oracles):
https://github.com/evalplus/evalplus/blob/master/evalplus/eval/__init__.py
Exact Python equality first, default float atol=1e-6, then same-top-level-type
numeric allclose with rtol=1e-7. No NumPy/third-party imports are needed.
"""
from __future__ import annotations

import ast
import builtins
import contextlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


POLICY_VERSION = "humaneval-admission-cpu-v1"
ALLOWED_IMPORTS = frozenset({
    "typing", "math", "collections", "itertools", "functools", "re",
    "statistics", "heapq", "bisect", "string", "operator", "copy",
    "fractions", "decimal", "random", "json", "hashlib",
})
_BANNED_NAMES = frozenset({
    "open", "eval", "exec", "compile", "getattr", "setattr", "delattr",
    "globals", "locals", "vars", "__import__", "__builtins__", "breakpoint",
    "input", "help", "exit", "quit",
})
_BANNED_ATTRIBUTES = frozenset({
    "open", "read_text", "read_bytes", "write_text", "write_bytes", "system",
    "popen", "spawn", "fork", "kill", "connect", "send", "unlink",
    "rename", "rmdir", "rmtree", "chmod", "walk", "getattr", "setattr",
    "attrgetter", "methodcaller", "setstate", "load", "dump", "file_digest",
    "os", "sys", "io", "builtins", "importlib", "subprocess", "socket",
    "pathlib", "shutil", "ctypes", "inspect", "pickle", "marshal", "modules",
    "environ", "codecs",
})
_MAX_VALUE_NODES = 100_000
_MAX_VALUE_BYTES = 1_048_576


def encode_value(value):
    """Encode supported Python values unambiguously, including non-string keys.

    Every value is tagged, so user dictionaries cannot collide with tag markers.
    Sets are sorted by their wire encoding for reproducible receipts. Unsupported
    values, cycles and oversized/deep outputs fail explicitly rather than str().
    """
    remaining = [_MAX_VALUE_NODES]
    ancestors = set()

    def visit(item, depth=0):
        remaining[0] -= 1
        if remaining[0] < 0 or depth > 100:
            raise ValueError("value exceeds encoding node/depth limit")
        kind = type(item)
        if item is None:
            return ["none", None]
        if kind is bool:
            return ["bool", item]
        if kind is int:
            return ["int", item]
        if kind is float:
            return ["float", item.hex()]
        if kind is str:
            return ["str", item]
        if kind not in (list, tuple, set, frozenset, dict):
            raise TypeError("unsupported output type: " + kind.__name__)
        identity = id(item)
        if identity in ancestors:
            raise ValueError("cyclic output is not supported")
        ancestors.add(identity)
        try:
            if kind is dict:
                data = [[visit(k, depth + 1), visit(v, depth + 1)] for k, v in item.items()]
                return ["dict", data]
            data = [visit(child, depth + 1) for child in item]
            if kind in (set, frozenset):
                data.sort(key=lambda row: json.dumps(row, ensure_ascii=True, separators=(",", ":")))
            return [{list: "list", tuple: "tuple", set: "set", frozenset: "frozenset"}[kind], data]
        finally:
            ancestors.remove(identity)

    encoded = visit(value)
    if len(json.dumps(encoded, ensure_ascii=True).encode("utf-8")) > _MAX_VALUE_BYTES:
        raise ValueError("value exceeds encoding byte limit")
    return encoded


def decode_value(encoded):
    """Invert ``encode_value``. Only use with evaluator-produced wire values."""
    kind, value = encoded
    if kind == "none":
        return None
    if kind in ("bool", "int", "str"):
        return value
    if kind == "float":
        return float.fromhex(value)
    if kind == "dict":
        return {decode_value(k): decode_value(v) for k, v in value}
    constructors = {"list": list, "tuple": tuple, "set": set, "frozenset": frozenset}
    if kind not in constructors:
        raise ValueError("unknown value encoding: " + str(kind))
    return constructors[kind](decode_value(child) for child in value)


def inspect_policy(code, entry_point):
    """Return syntax/interface/policy violations without executing candidate code."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError) as error:
        return ["syntax_error: " + str(error)]
    violations = []
    if not any(isinstance(node, ast.FunctionDef) and node.name == entry_point for node in tree.body):
        violations.append("missing exact synchronous entry_point")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    violations.append("disallowed import: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                violations.append("disallowed import from: " + str(node.module))
            for alias in node.names:
                if alias.name.startswith("_") or alias.name in _BANNED_ATTRIBUTES or alias.name in _BANNED_NAMES:
                    violations.append("disallowed imported name: " + alias.name)
        elif isinstance(node, ast.Name) and node.id in _BANNED_NAMES:
            violations.append("disallowed name: " + node.id)
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("_") or node.attr in _BANNED_ATTRIBUTES:
                violations.append("disallowed attribute: " + node.attr)
    return sorted(set(violations))


def _is_floats(value):
    return isinstance(value, float) or (
        isinstance(value, (list, tuple)) and bool(value)
        and all(isinstance(child, float) for child in value)
    )


def _numeric_shape(value):
    if isinstance(value, (bool, int, float)):
        return ()
    if isinstance(value, (list, tuple)):
        if not value:
            return (0,)
        shapes = [_numeric_shape(child) for child in value]
        if any(shape != shapes[0] for shape in shapes):
            raise TypeError("ragged/non-numeric comparison")
        return (len(value),) + shapes[0]
    raise TypeError("non-numeric comparison")


def _allclose(actual, expected, atol):
    # Standard task values are scalars or rectangular sequences; no broadcasting.
    if _numeric_shape(actual) != _numeric_shape(expected):
        return False
    if isinstance(expected, (list, tuple)):
        return all(_allclose(a, e, atol) for a, e in zip(actual, expected))
    if actual == expected:
        return True
    if not math.isfinite(actual) or not math.isfinite(expected):
        return False
    return abs(actual - expected) <= atol + 1e-7 * abs(expected)


def values_equal(actual, expected, atol=0.0):
    """EvalPlus ordinary comparison, without task-specific special oracles."""
    if actual == expected:
        return True
    effective_atol = 1e-6 if atol == 0 and _is_floats(expected) else atol
    if effective_atol == 0 or type(actual) is not type(expected):
        return False
    try:
        return _allclose(actual, expected, effective_atol)
    except (ValueError, TypeError, OverflowError):
        return False


class _DiscardOutput:
    """Drop candidate print output without growing a StringIO or pipe buffer."""
    def write(self, text):
        return len(text)

    def flush(self):
        return None


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level or name.split(".")[0] not in ALLOWED_IMPORTS:
        raise ImportError("candidate import is not allowed: " + name)
    return builtins.__import__(name, globals, locals, fromlist, level)


def _error(error):
    # Candidate-defined exception __str__ methods must not pollute JSONL either.
    with contextlib.redirect_stdout(_DiscardOutput()), contextlib.redirect_stderr(_DiscardOutput()):
        try:
            description = str(error)[:2000]
        except BaseException:
            description = "<exception message unavailable>"
    return type(error).__name__ + ": " + description


def _worker_main():
    """Private CLI; run_suite is the supported public entry point."""
    payload = json.load(sys.stdin)
    protocol_stdout = sys.stdout
    import random
    random.seed(0)

    def emit(message):
        protocol_stdout.write(json.dumps(message, ensure_ascii=True, allow_nan=False) + "\n")
        protocol_stdout.flush()

    code, entry_point = payload["code"], payload["entry_point"]
    violations = inspect_policy(code, entry_point)
    if violations:
        emit({"event": "policy_rejected", "violations": violations})
        return
    safe_builtins = {name: value for name, value in vars(builtins).items() if name not in _BANNED_NAMES}
    safe_builtins["__import__"] = _safe_import
    namespace = {"__builtins__": safe_builtins, "__name__": "admission_candidate"}
    try:
        with contextlib.redirect_stdout(_DiscardOutput()), contextlib.redirect_stderr(_DiscardOutput()):
            exec(compile(code, "<candidate>", "exec"), namespace)
            fn = namespace[entry_point]
            if not callable(fn):
                raise TypeError("entry_point is not callable")
    except BaseException as error:
        emit({"event": "setup_error", "error": _error(error)})
        return
    for index, encoded_args in enumerate(payload["inputs"]):
        emit({"event": "started", "index": index})
        started = time.monotonic()
        try:
            args = decode_value(encoded_args)
            with contextlib.redirect_stdout(_DiscardOutput()), contextlib.redirect_stderr(_DiscardOutput()):
                actual = fn(*args)
                encoded_actual = encode_value(actual)
                passed = None if payload["expected"] is None else values_equal(
                    actual, decode_value(payload["expected"][index]), payload["atol"],
                )
            row = {"actual": encoded_actual, "passed": passed, "error": None}
        except BaseException as error:
            row = {"actual": None, "passed": False, "error": _error(error)}
        emit({"event": "result", "index": index, "seconds": time.monotonic() - started, **row})
    emit({"event": "complete"})


def run_suite(code, entry_point, inputs, expected=None, atol=0.0, timeout=10.0):
    """Execute explicit positional-argument lists, retaining every observation.

    ``expected=None`` collects reference outputs (successful observations have
    ``passed=None``). ``success`` then means all reference calls were observed
    without error. Otherwise every expected value must pass. Empty suites cannot
    succeed. ``cases_executed`` counts completed invocations, including errors;
    ``cases_started`` also counts an invocation interrupted by the suite timeout.
    ``results`` always has one row per input, marking unfinished rows unobserved.
    The receipt is JSON-safe; decode each observed row's ``actual`` to recover it.
    """
    if not isinstance(code, str) or not isinstance(entry_point, str) or not entry_point.isidentifier():
        raise ValueError("code and exact entry_point must be strings")
    if not isinstance(inputs, (list, tuple)) or any(not isinstance(args, (list, tuple)) for args in inputs):
        raise ValueError("inputs must contain explicit positional-argument lists")
    if expected is not None and (not isinstance(expected, (list, tuple)) or len(expected) != len(inputs)):
        raise ValueError("expected must have exactly one value per input")
    if not math.isfinite(timeout) or timeout <= 0 or not math.isfinite(atol) or atol < 0:
        raise ValueError("timeout must be positive and atol finite/nonnegative")
    started = time.monotonic()
    receipt = {
        "policy_version": POLICY_VERSION, "success": False, "reference_mode": expected is None,
        "policy_rejected": False, "policy_violations": [], "timeout": False,
        "setup_error": None, "execution_error": None, "return_code": None,
        "cases_total": len(inputs), "cases_started": 0, "cases_executed": 0,
        "cases_passed": 0, "suite_complete": False,
        "results": [{"index": index, "started": False, "observed": False,
                     "passed": None, "actual": None, "error": "unobserved"}
                    for index in range(len(inputs))],
    }
    violations = inspect_policy(code, entry_point)
    if violations:
        receipt.update(policy_rejected=True, policy_violations=violations)
        receipt["wall_seconds"] = time.monotonic() - started
        return receipt
    payload = {"code": code, "entry_point": entry_point,
               "inputs": [encode_value(args) for args in inputs],
               "expected": None if expected is None else [encode_value(v) for v in expected],
               "atol": atol}
    safe_env = {name: os.environ[name] for name in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP") if name in os.environ}
    safe_env.update(PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8")
    stdout = ""
    with tempfile.TemporaryDirectory(prefix="humaneval-admission-") as work:
        try:
            process = subprocess.run(
                [sys.executable, "-I", "-S", "-X", "utf8", str(Path(__file__).resolve()), "--worker"],
                input=json.dumps(payload, ensure_ascii=True, allow_nan=False), text=True,
                encoding="utf-8", capture_output=True, timeout=timeout, cwd=work, env=safe_env,
            )
            stdout = process.stdout
            receipt["return_code"] = process.returncode
            if process.returncode:
                receipt["execution_error"] = "worker_exit: " + process.stderr[-2000:]
        except subprocess.TimeoutExpired as error:
            receipt["timeout"] = True
            stdout = error.stdout or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
        except OSError as error:
            receipt["execution_error"] = _error(error)
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            receipt["execution_error"] = "incomplete_or_invalid_worker_protocol"
            continue
        kind = event.get("event")
        if kind in ("started", "result"):
            index = event.get("index")
            if not isinstance(index, int) or not 0 <= index < len(inputs):
                receipt["execution_error"] = "invalid_worker_case_index"
                continue
            row = receipt["results"][index]
            row["started"] = True
            if kind == "result":
                row.update({key: event[key] for key in ("passed", "actual", "error", "seconds")})
                row["observed"] = True
        elif kind == "complete":
            receipt["suite_complete"] = True
        elif kind == "setup_error":
            receipt["setup_error"] = event["error"]
        elif kind == "policy_rejected":
            receipt.update(policy_rejected=True, policy_violations=event["violations"])
        else:
            receipt["execution_error"] = "unknown_worker_protocol_event"
    receipt["cases_started"] = sum(row["started"] for row in receipt["results"])
    receipt["cases_executed"] = sum(row["observed"] for row in receipt["results"])
    receipt["cases_passed"] = sum(row["passed"] is True for row in receipt["results"])
    if receipt["return_code"] == 0 and not receipt["suite_complete"] and not receipt["setup_error"] and not receipt["policy_rejected"]:
        receipt["execution_error"] = receipt["execution_error"] or "worker_did_not_complete_suite"
    receipt["success"] = bool(inputs) and (
        receipt["suite_complete"] and not receipt["timeout"] and not receipt["setup_error"]
        and not receipt["policy_rejected"] and not receipt["execution_error"]
        and receipt["return_code"] == 0 and receipt["cases_executed"] == len(inputs)
        and all(row["error"] is None and (expected is None or row["passed"] is True) for row in receipt["results"])
    )
    receipt["wall_seconds"] = time.monotonic() - started
    return receipt


if __name__ == "__main__":
    if sys.argv[1:] != ["--worker"]:
        raise SystemExit("Use run_suite(); --worker is a private subprocess entry point")
    _worker_main()
