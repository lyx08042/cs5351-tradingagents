#!/usr/bin/env python3
"""Course scaffold checker (documentation/governance only).

Validates the requirements registry, requirement id uniqueness, trace-matrix
coverage, and presence of bootstrap-required files. This is an initial
scaffolding check for the course fork; it does NOT implement or verify any of
the runtime features F1-F5, and it is NOT a full six-gate course compliance
check.

Placeholder policy: a requirement statement may contain declared placeholder
tokens (TODO/TBD/{{...}}) only while its status is ``proposed``. Requirements
that are ``approved``, ``implemented`` or ``superseded`` must state concrete,
non-placeholder requirements.

Exit code is non-zero on any error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import jsonschema
    import yaml
except ImportError as exc:  # pragma: no cover - dependency guidance
    sys.stderr.write(
        "check_course.py requires jsonschema, PyYAML "
        f"(pip install -r requirements-course.txt): {exc}\n"
    )
    raise SystemExit(2) from exc

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_FILES = [
    "README.md",
    "README.upstream.md",
    "START-HERE.md",
    "AGENTS.md",
    "Prompt.md",
    "architecture-blueprint.md",
    "opencode.json",
    "requirements-course.txt",
    "src/README.md",
    "test/README.md",
    "test/offline/README.md",
    "test/live/README.md",
    "docs/req/requirements.yaml",
    "docs/req/req-schema.json",
    "docs/req/README.md",
    "docs/architecture/invariants.md",
    "docs/architecture/trace-matrix.md",
    "docs/architecture/adr/001-course-extension.md",
    "docs/code-governance/structural-constraints.md",
    "docs/code-governance/verification-constraints.md",
    "docs/code-governance/mcp-tool-manifest.md",
    "docs/evaluation/cases.yaml",
    "docs/approvals/README.md",
    "docs/ai-use-log.yaml",
]
REQUIRED_SCHEMA_VERSION = "1.0"
PLACEHOLDER_TOKENS = ("{{", "}}", "TODO", "TBD", "FIXME", "XXX")

COURSE_YAML_ARTIFACTS = [
    "docs/ai-use-log.yaml",
    "prompts/prompt_v1.0.yaml",
    "prompts/prompt_v1.1.yaml",
    "docs/evaluation/cases.yaml",
]
AI_USE_LOG_REQUIRED_KEYS = ("model", "tool", "session_id", "summary")


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level document must be a mapping")
    return data


def _requirements(registry: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Return requirement entries, or None when the list is malformed."""
    entries = registry.get("requirements")
    if not isinstance(entries, list):
        return None
    if not all(isinstance(entry, dict) for entry in entries):
        return None
    return entries


def _schema_errors(registry: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(registry), key=lambda e: list(e.path)):
        location = "/".join(str(part) for part in error.path) or "<root>"
        errors.append(f"schema: {location}: {error.message}")
    return errors


def _duplicate_ids(entries: list[dict[str, Any]]) -> list[str]:
    seen: dict[Any, int] = {}
    for req in entries:
        req_id = req.get("id")
        seen[req_id] = seen.get(req_id, 0) + 1
    return [
        f"duplicate requirement id: {req_id} (x{count})"
        for req_id, count in seen.items()
        if count > 1
    ]


def _trace_coverage(entries: list[dict[str, Any]], trace_path: Path) -> list[str]:
    if not trace_path.exists():
        return [f"missing trace matrix: {trace_path}"]
    text = trace_path.read_text(encoding="utf-8")
    errors = []
    for req in entries:
        req_id = req.get("id")
        if not req_id:
            continue
        if not re.search(rf"(?<![A-Z0-9-]){re.escape(str(req_id))}(?![A-Z0-9-])", text):
            errors.append(f"trace matrix does not reference requirement {req_id}")
    return errors


def _placeholder_errors(entries: list[dict[str, Any]]) -> list[str]:
    """Placeholders are tolerated only for status == 'proposed'."""
    errors = []
    for req in entries:
        statement = req.get("statement")
        if not isinstance(statement, str):
            continue
        if req.get("status") == "proposed":
            continue
        if any(token in statement for token in PLACEHOLDER_TOKENS):
            errors.append(
                f"placeholder text in non-proposed requirement {req.get('id')} "
                f"(status={req.get('status')})"
            )
    return errors


def _required_files_errors(root: Path) -> list[str]:
    return [f"missing required file: {rel}" for rel in REQUIRED_FILES if not (root / rel).exists()]


def _load_course_yaml(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Parse a course YAML artifact; return (mapping, errors)."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (yaml.YAMLError, OSError) as exc:
        return None, [f"{path}: invalid YAML: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{path}: top-level document must be a mapping"]
    return data, []


def _ai_use_log_errors(path: Path, data: dict[str, Any]) -> list[str]:
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        return [f"{path}: 'entries' must be a non-empty list"]
    errors = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"{path}: entries[{index}] must be a mapping")
            continue
        for key in AI_USE_LOG_REQUIRED_KEYS:
            value = entry.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{path}: entries[{index}].{key} must be a non-empty string")
    return errors


def _course_artifact_errors(root: Path) -> list[str]:
    errors = []
    for rel in COURSE_YAML_ARTIFACTS:
        path = root / rel
        if not path.exists():
            errors.append(f"missing course YAML artifact: {rel}")
            continue
        data, parse_errors = _load_course_yaml(path)
        errors.extend(parse_errors)
        if data is None:
            continue
        if rel == "docs/ai-use-log.yaml":
            errors.extend(_ai_use_log_errors(path, data))
    return errors


def run_checks(root: Path, requirements: Path | None = None) -> list[str]:
    registry_path = (
        requirements if requirements is not None else root / "docs/req/requirements.yaml"
    )
    schema_path = root / "docs/req/req-schema.json"
    trace_path = root / "docs/architecture/trace-matrix.md"

    if not registry_path.exists():
        return [f"missing requirements registry: {registry_path}"]
    if not schema_path.exists():
        return [f"missing schema: {schema_path}"]

    try:
        registry = _load_yaml(registry_path)
    except (ValueError, yaml.YAMLError) as exc:
        return [f"cannot parse requirements registry: {exc}"]

    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)

    errors: list[str] = []
    errors.extend(_schema_errors(registry, schema))

    entries = _requirements(registry)
    if entries is None:
        errors.append("requirements: entries must be a list of mappings")
        return errors

    errors.extend(_duplicate_ids(entries))

    if registry.get("schema_version") != REQUIRED_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {REQUIRED_SCHEMA_VERSION!r}, "
            f"got {registry.get('schema_version')!r}"
        )

    # Trace coverage and required bootstrap files are always checked against
    # --root, even when an alternate registry is supplied via --requirements,
    # so coverage cannot be bypassed by pointing at a different YAML.
    errors.extend(_trace_coverage(entries, trace_path))
    errors.extend(_required_files_errors(root))
    errors.extend(_course_artifact_errors(root))

    errors.extend(_placeholder_errors(entries))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(REPO_ROOT), help="repository root")
    parser.add_argument(
        "--requirements",
        default=None,
        help="alternative requirements YAML path (default: <root>/docs/req/requirements.yaml)",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    requirements = Path(args.requirements).resolve() if args.requirements else None

    errors = run_checks(root, requirements)
    if errors:
        for error in errors:
            sys.stderr.write(f"ERROR: {error}\n")
        return 1

    sys.stdout.write("course scaffold check: OK\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
