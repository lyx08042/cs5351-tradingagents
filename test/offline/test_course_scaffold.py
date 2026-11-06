"""Tests for the course scaffold checker (offline, deterministic, no network)."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_course.py"
REGISTRY = REPO_ROOT / "docs" / "req" / "requirements.yaml"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_course", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def checker():
    return _load_checker()


@pytest.fixture()
def registry() -> dict:
    with REGISTRY.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _write(tmp_path: Path, suffix: str, data: Any) -> Path:
    path = tmp_path / suffix
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def _errors_for(checker, tmp_path: Path, data: Any) -> list[str]:
    path = _write(tmp_path, "mutated.yaml", data)
    return checker.run_checks(REPO_ROOT, path)


@pytest.mark.unit
def test_real_registry_passes(checker):
    assert checker.run_checks(REPO_ROOT) == []


@pytest.mark.unit
def test_script_cli_returns_zero_on_real_registry(checker):
    assert checker.main(["--root", str(REPO_ROOT)]) == 0


@pytest.mark.unit
def test_duplicate_requirement_id_fails(checker, tmp_path, registry):
    data = copy.deepcopy(registry)
    data["requirements"].append(copy.deepcopy(data["requirements"][0]))
    errors = _errors_for(checker, tmp_path, data)
    assert any("duplicate requirement id" in e for e in errors)


@pytest.mark.unit
def test_missing_fit_fails(checker, tmp_path, registry):
    data = copy.deepcopy(registry)
    data["requirements"][0].pop("fit")
    errors = _errors_for(checker, tmp_path, data)
    assert any(e.startswith("schema:") for e in errors)


@pytest.mark.unit
def test_missing_required_field_fails(checker, tmp_path, registry):
    data = copy.deepcopy(registry)
    data["requirements"][0].pop("statement")
    errors = _errors_for(checker, tmp_path, data)
    assert any(e.startswith("schema:") for e in errors)


@pytest.mark.unit
def test_invalid_priority_fails(checker, tmp_path, registry):
    data = copy.deepcopy(registry)
    data["requirements"][0]["priority"] = "highest"
    errors = _errors_for(checker, tmp_path, data)
    assert any(e.startswith("schema:") for e in errors)


@pytest.mark.unit
def test_trace_coverage_fails_for_unreferenced_id(checker, tmp_path, registry):
    data = copy.deepcopy(registry)
    new_req = copy.deepcopy(data["requirements"][0])
    new_req["id"] = "FR-999"
    data["requirements"].append(new_req)
    errors = checker.run_checks(REPO_ROOT, _write(tmp_path, "coverage.yaml", data))
    assert any("FR-999" in e and "trace matrix" in e for e in errors)


@pytest.mark.unit
def test_schema_version_mismatch_fails(checker, tmp_path, registry):
    data = copy.deepcopy(registry)
    data["schema_version"] = "9.9"
    errors = _errors_for(checker, tmp_path, data)
    assert any("schema_version" in e for e in errors)


@pytest.mark.unit
def test_placeholder_in_non_proposed_statement_fails(checker, tmp_path, registry):
    data = copy.deepcopy(registry)
    data["requirements"][0]["statement"] = "TBD"
    data["requirements"][0]["status"] = "approved"
    errors = _errors_for(checker, tmp_path, data)
    assert any("placeholder" in e for e in errors)


@pytest.mark.unit
def test_placeholder_in_proposed_statement_allowed(checker, tmp_path, registry):
    data = copy.deepcopy(registry)
    data["requirements"][0]["statement"] = "TODO: refine later"
    assert _errors_for(checker, tmp_path, data) == []


@pytest.mark.unit
def test_malformed_requirement_entry_fails_cleanly(checker, tmp_path, registry):
    data = copy.deepcopy(registry)
    data["requirements"].append("not-a-mapping")
    path = tmp_path / "malformed.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    errors = checker.run_checks(REPO_ROOT, path)
    # Must report cleanly (no traceback) and include the malformed-entry error.
    assert checker.main(["--root", str(REPO_ROOT), "--requirements", str(path)]) == 1
    assert errors


@pytest.mark.unit
def test_numeric_and_integer_thresholds_pass_schema(checker, tmp_path, registry):
    data = copy.deepcopy(registry)
    data["requirements"][0]["fit"]["threshold"] = 7
    data["requirements"][1]["fit"]["threshold"] = 0.25
    data["requirements"][2]["fit"]["threshold"] = "ordinal-high"
    assert _errors_for(checker, tmp_path, data) == []


@pytest.mark.unit
def test_missing_registry_fails(checker, tmp_path):
    errors = checker.run_checks(REPO_ROOT, tmp_path / "nope.yaml")
    assert any("missing requirements registry" in e for e in errors)


@pytest.mark.unit
def test_missing_schema_fails(checker, tmp_path, registry):
    fake_root = tmp_path / "repo"
    (fake_root / "docs/req").mkdir(parents=True)
    (fake_root / "docs/req/requirements.yaml").write_text(
        REGISTRY.read_text(encoding="utf-8"), encoding="utf-8"
    )
    errors = checker.run_checks(fake_root)
    assert any("missing schema" in e for e in errors)


@pytest.mark.unit
def test_missing_trace_matrix_fails(checker, tmp_path, registry):
    data = copy.deepcopy(registry)
    requirements = _write(tmp_path, "registry.yaml", data)
    fake_root = tmp_path / "repo"
    (fake_root / "docs/req").mkdir(parents=True)
    (fake_root / "docs/req/req-schema.json").write_text(
        (REPO_ROOT / "docs/req/req-schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    errors = checker.run_checks(fake_root, requirements)
    assert any("missing trace matrix" in e for e in errors)


@pytest.mark.unit
def test_script_cli_returns_nonzero_on_missing_registry(checker, tmp_path):
    missing = tmp_path / "nope.yaml"
    assert checker.main(["--root", str(REPO_ROOT), "--requirements", str(missing)]) == 1


@pytest.mark.unit
def test_missing_required_file_fails(checker, tmp_path):
    fake_root = tmp_path / "repo"
    fake_root.mkdir()
    for rel in ("docs/req", "docs/architecture"):
        (fake_root / rel).mkdir(parents=True)
    (fake_root / "docs/req/requirements.yaml").write_text(
        REGISTRY.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (fake_root / "docs/req/req-schema.json").write_text(
        (REPO_ROOT / "docs/req/req-schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (fake_root / "docs/architecture/trace-matrix.md").write_text(
        (REPO_ROOT / "docs/architecture/trace-matrix.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    errors = checker.run_checks(fake_root)
    assert any("missing required file" in e for e in errors)


def _minimal_scaffold_root(root: Path) -> None:
    for rel in ("docs/req", "docs/architecture", "docs/evaluation", "prompts"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    copies = {
        "docs/req/requirements.yaml": REGISTRY,
        "docs/req/req-schema.json": REPO_ROOT / "docs/req/req-schema.json",
        "docs/architecture/trace-matrix.md": REPO_ROOT / "docs/architecture/trace-matrix.md",
        "docs/ai-use-log.yaml": REPO_ROOT / "docs/ai-use-log.yaml",
        "docs/evaluation/cases.yaml": REPO_ROOT / "docs/evaluation/cases.yaml",
        "prompts/prompt_v1.0.yaml": REPO_ROOT / "prompts/prompt_v1.0.yaml",
        "prompts/prompt_v1.1.yaml": REPO_ROOT / "prompts/prompt_v1.1.yaml",
    }
    for rel, source in copies.items():
        (root / rel).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


@pytest.mark.unit
def test_corrupted_ai_use_log_yaml_fails(checker, tmp_path):
    root = tmp_path / "repo"
    _minimal_scaffold_root(root)
    (root / "docs/ai-use-log.yaml").write_text(
        "entries: [unclosed\nschema_version: '1.0'\n", encoding="utf-8"
    )
    errors = checker.run_checks(root)
    assert any("ai-use-log.yaml" in e and "invalid YAML" in e for e in errors)


@pytest.mark.unit
def test_ai_use_log_missing_session_id_fails(checker, tmp_path):
    root = tmp_path / "repo"
    _minimal_scaffold_root(root)
    (root / "docs/ai-use-log.yaml").write_text(
        "schema_version: '1.0'\nentries:\n  - model: m\ntool: t\n", encoding="utf-8"
    )
    errors = checker.run_checks(root)
    assert any("entries[0].session_id" in e for e in errors)


@pytest.mark.unit
def test_ai_use_log_empty_entries_fails(checker, tmp_path):
    root = tmp_path / "repo"
    _minimal_scaffold_root(root)
    (root / "docs/ai-use-log.yaml").write_text(
        "schema_version: '1.0'\nentries: []\n", encoding="utf-8"
    )
    errors = checker.run_checks(root)
    assert any("non-empty list" in e for e in errors)
