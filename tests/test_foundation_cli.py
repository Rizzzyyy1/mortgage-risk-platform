import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from mortgage_risk import cli


def write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=True)


def test_valid_config(tmp_path):
    project_root = tmp_path
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = project_root / "configs" / "project.yaml"
    write_yaml(
        config_path,
        {
            "schema_version": 1,
            "project_name": "Demo project",
            "data_dir": "data",
            "output_dir": "artifacts/runs",
        },
    )

    result = cli.run_check(config_path, project_root=project_root)

    assert result["overall_status"] == "pass"
    assert result["resolved_config"]["project_name"] == "Demo project"
    assert result["run_id"]
    assert (project_root / "artifacts" / "runs" / result["run_id"] / "check_result.json").exists()


def test_load_invalid_missing_required_field(tmp_path):
    project_root = tmp_path
    config_path = project_root / "configs" / "project.yaml"
    write_yaml(
        config_path,
        {
            "schema_version": 1,
            "project_name": "Demo project",
            "data_dir": "data",
        },
    )

    with pytest.raises(cli.ConfigValidationError):
        cli.load_config(config_path, project_root=project_root)


def test_relative_path_resolution(tmp_path):
    project_root = tmp_path
    data_dir = project_root / "input" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = project_root / "configs" / "project.yaml"
    write_yaml(
        config_path,
        {
            "schema_version": 1,
            "project_name": "Demo project",
            "data_dir": "input/data",
            "output_dir": "output/checks",
        },
    )

    resolved = cli.load_config(config_path, project_root=project_root)

    assert Path(resolved["data_dir"]) == (project_root / "input" / "data").resolve()
    assert Path(resolved["output_dir"]) == (project_root / "output" / "checks").resolve()


def test_cli_invalid_config_exits_nonzero(tmp_path):
    project_root = tmp_path
    bad_config = project_root / "configs" / "bad.yaml"
    write_yaml(
        bad_config,
        {
            "schema_version": 1,
            "project_name": "Demo project",
            "data_dir": "missing-data",
            "output_dir": "artifacts/runs",
        },
    )

    result = subprocess.run(
        [sys.executable, "-m", "mortgage_risk.cli", "check", "--config", str(bad_config)],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )

    assert result.returncode != 0
    assert "Configuration error" in result.stderr


def test_unique_runs_do_not_overwrite(tmp_path):
    project_root = tmp_path
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = project_root / "configs" / "project.yaml"
    write_yaml(
        config_path,
        {
            "schema_version": 1,
            "project_name": "Demo project",
            "data_dir": "data",
            "output_dir": "artifacts/runs",
        },
    )

    first = cli.run_check(config_path, project_root=project_root)
    second = cli.run_check(config_path, project_root=project_root)

    assert first["run_id"] != second["run_id"]
    assert (project_root / "artifacts" / "runs" / first["run_id"] / "check_result.json").exists()
    assert (project_root / "artifacts" / "runs" / second["run_id"] / "check_result.json").exists()


def test_saved_check_result_contains_expected_fields(tmp_path):
    project_root = tmp_path
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = project_root / "configs" / "project.yaml"
    write_yaml(
        config_path,
        {
            "schema_version": 1,
            "project_name": "Demo project",
            "data_dir": "data",
            "output_dir": "artifacts/runs",
        },
    )

    result = cli.run_check(config_path, project_root=project_root)
    result_path = project_root / "artifacts" / "runs" / result["run_id"] / "check_result.json"

    assert result_path.exists()
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "pass"
    assert payload["python_version"]
    assert payload["package_version"]
    assert payload["git_revision"]
