from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from mortgage_risk import __version__
from mortgage_risk.ingestion import ingest_historical_file, ingest_sample_file, select_deterministic_loan_ids
from mortgage_risk.monthly_summary import build_monthly_portfolio_summary, read_selected_ingest_run

SCHEMA_VERSION = 1
REQUIRED_FIELDS = {"schema_version", "project_name", "data_dir", "output_dir"}


class ConfigValidationError(ValueError):
    """Raised when the project config is missing required fields or invalid."""


def project_root_from_package() -> Path:
    return Path(__file__).resolve().parents[2]


def _to_str(value: Any) -> str:
    if value is None:
        raise ConfigValidationError("Field value cannot be null.")
    return str(value)


def _resolve_path(raw_path: str, root_dir: Path) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve(strict=False)
    return (root_dir / candidate).resolve(strict=False)


def load_config(config_path: str | os.PathLike[str], project_root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    config_location = Path(config_path)
    if not config_location.is_absolute():
        base_root = Path(project_root) if project_root is not None else project_root_from_package()
        config_location = (base_root / config_location).resolve(strict=False)

    if not config_location.exists():
        raise ConfigValidationError(f"Configuration file does not exist: {config_location}")

    with config_location.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}

    if not isinstance(loaded, dict):
        raise ConfigValidationError("Configuration root must be a mapping.")

    missing = sorted(REQUIRED_FIELDS - set(loaded.keys()))
    if missing:
        raise ConfigValidationError(f"Missing required configuration fields: {', '.join(missing)}")

    schema_version = loaded.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ConfigValidationError(
            f"Unsupported configuration schema version '{schema_version}'. Supported version: {SCHEMA_VERSION}."
        )

    project_name = loaded.get("project_name")
    if not isinstance(project_name, str) or not project_name.strip():
        raise ConfigValidationError("The project_name value must be a non-empty string.")

    for key in ("data_dir", "output_dir"):
        value = loaded.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConfigValidationError(f"The {key} value must be a non-empty string.")

    root_dir = Path(project_root) if project_root is not None else project_root_from_package()
    resolved_data_dir = _resolve_path(_to_str(loaded["data_dir"]), root_dir)
    if not resolved_data_dir.exists() or not resolved_data_dir.is_dir():
        raise ConfigValidationError(f"Configured data directory does not exist or is not a directory: {resolved_data_dir}")

    resolved_output_dir = _resolve_path(_to_str(loaded["output_dir"]), root_dir)
    resolved = {
        "schema_version": int(schema_version),
        "project_name": project_name.strip(),
        "data_dir": str(resolved_data_dir),
        "output_dir": str(resolved_output_dir),
    }
    return resolved


def git_revision(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "unavailable (git not installed)"

    stderr = (result.stderr or "").lower()
    stdout = (result.stdout or "").strip()
    if result.returncode == 0 and stdout:
        return stdout
    if "not a git repository" in stderr:
        return "unavailable (not a git repository)"
    if "does not have any commits yet" in stderr or "unknown revision" in stderr or "ambiguous argument 'head'" in stderr:
        return "unavailable (no git commits yet)"
    return "unavailable (git metadata not available)"


def _check_directory_writable(path: Path) -> tuple[bool, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.touch(exist_ok=True)
        probe.unlink(missing_ok=True)
        return True, f"Writable: {path}"
    except OSError as exc:
        return False, f"Not writable: {path} ({exc})"


def run_check(config_path: str | os.PathLike[str], project_root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    run_root = Path(project_root) if project_root is not None else project_root_from_package()
    default_output_root = (run_root / "artifacts" / "runs").resolve(strict=False)

    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = (run_root / config_file).resolve(strict=False)

    try:
        config = load_config(config_file, project_root=run_root)
        configured_root = run_root
    except ConfigValidationError as exc:
        run_id = uuid.uuid4().hex
        run_dir = default_output_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        result = {
            "run_id": run_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "package_version": __version__,
            "python_version": platform.python_version(),
            "config_path": str(config_file),
            "resolved_config": {},
            "outcomes": [{"name": "configuration_validation", "passed": False, "details": str(exc)}],
            "overall_status": "failed",
            "git_revision": git_revision(run_root),
            "notes": ["Configuration validation failed."]
        }
        with (run_dir / "check_result.json").open("w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
        raise

    data_dir = Path(config["data_dir"])
    output_dir = Path(config["output_dir"])
    outcomes: list[dict[str, Any]] = []

    outcomes.append({
        "name": "required_fields",
        "passed": True,
        "details": "Required fields present and schema version supported.",
    })
    outcomes.append({
        "name": "data_directory",
        "passed": data_dir.exists() and data_dir.is_dir(),
        "details": f"Resolved data directory: {data_dir}",
    })

    output_dir.mkdir(parents=True, exist_ok=True)
    writable_ok, writable_message = _check_directory_writable(output_dir)
    outcomes.append({
        "name": "output_directory_writable",
        "passed": writable_ok,
        "details": writable_message,
    })

    run_id = uuid.uuid4().hex
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "package_version": __version__,
        "python_version": platform.python_version(),
        "config_path": str(config_file),
        "resolved_config": config,
        "outcomes": outcomes,
        "overall_status": "pass" if all(item["passed"] for item in outcomes) else "failed",
        "git_revision": git_revision(run_root),
        "notes": [
            "Foundation check validates configuration, environment, and path accessibility.",
            "No mortgage data, model, or scenario versions were generated in this phase.",
        ],
    }

    if result["overall_status"] == "failed":
        result["notes"].append("One or more required checks failed.")

    with (run_dir / "check_result.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)

    return result


def run_sample_ingest(input_path: str | os.PathLike[str], project_root: str | os.PathLike[str] | None = None,
                     output_dir: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    root_dir = Path(project_root) if project_root is not None else project_root_from_package()
    base_output_dir = Path(output_dir) if output_dir is not None else root_dir / "artifacts" / "runs" / "sample_ingest"
    if not base_output_dir.is_absolute():
        base_output_dir = (root_dir / base_output_dir).resolve(strict=False)

    run_id = uuid.uuid4().hex
    run_dir = base_output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    sample_input = Path(input_path)
    if not sample_input.is_absolute():
        sample_input = (root_dir / sample_input).resolve(strict=False)

    db_path = run_dir / "sample_monthly.db"
    parquet_path = run_dir / "sample_monthly.parquet"

    result = ingest_sample_file(sample_input, db_path=db_path, parquet_path=parquet_path)
    result["run_id"] = run_id
    result["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    result["output_dir"] = str(run_dir)
    result["dataset_path"] = str(parquet_path)
    result["database_path"] = str(db_path)

    with (run_dir / "sample_ingest_result.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)

    return result


def run_historical_ingest(input_path: str | os.PathLike[str], project_root: str | os.PathLike[str] | None = None,
                        output_dir: str | os.PathLike[str] | None = None,
                        max_loans: int = 1000,
                        all_records: bool = False) -> dict[str, Any]:
    root_dir = Path(project_root) if project_root is not None else project_root_from_package()
    base_output_dir = Path(output_dir) if output_dir is not None else root_dir / "artifacts" / "runs" / "historical_ingest"
    if not base_output_dir.is_absolute():
        base_output_dir = (root_dir / base_output_dir).resolve(strict=False)

    run_id = uuid.uuid4().hex
    run_dir = base_output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    source_input = Path(input_path)
    if not source_input.is_absolute():
        source_input = (root_dir / source_input).resolve(strict=False)

    selected_loan_ids = None if all_records else select_deterministic_loan_ids(source_input, max_loans=max_loans)
    if all_records:
        selected_loan_ids = None
    db_path = run_dir / "historical_monthly.db"
    parquet_path = run_dir / "historical_monthly.parquet"

    result = ingest_historical_file(
        source_input,
        selected_loan_ids=selected_loan_ids,
        db_path=db_path,
        parquet_path=parquet_path,
        max_loans=max_loans if not all_records else None,
    )
    result["run_id"] = run_id
    result["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    result["output_dir"] = str(run_dir)
    result["dataset_path"] = str(parquet_path)
    result["database_path"] = str(db_path)
    result["all_records_mode"] = all_records
    result["max_loans_applied"] = None if all_records else max_loans

    with (run_dir / "historical_ingest_result.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)

    return result


def run_monthly_summary(project_root: str | os.PathLike[str] | None = None,
                       input_db: str | os.PathLike[str] | None = None,
                       input_run: str | None = None,
                       output_dir: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    root_dir = Path(project_root) if project_root is not None else project_root_from_package()
    if input_db is not None:
        db_path = Path(input_db)
        if not db_path.is_absolute():
            db_path = (root_dir / db_path).resolve(strict=False)
        selected_run_id = db_path.parent.name
    else:
        _, db_path, _ = read_selected_ingest_run(root_dir / "artifacts" / "runs" / "sample_ingest", input_run)
        selected_run_id = db_path.parent.name

    target_dir = Path(output_dir) if output_dir is not None else root_dir / "artifacts" / "runs" / "monthly_summary"
    if not target_dir.is_absolute():
        target_dir = (root_dir / target_dir).resolve(strict=False)

    result = build_monthly_portfolio_summary(db_path, output_dir=target_dir)
    result["run_id"] = selected_run_id
    result["input_run_id"] = selected_run_id
    result["input_db_path"] = str(db_path)
    result["python_version"] = platform.python_version()
    result["git_revision"] = git_revision(root_dir)
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the mortgage risk project foundation configuration.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Validate the project configuration and write a run record.")
    check_parser.add_argument("--config", required=True, help="Path to the project YAML config file.")

    ingest_parser = subparsers.add_parser("sample-ingest", help="Ingest the sample file into a validated monthly DuckDB and Parquet dataset.")
    ingest_parser.add_argument("--input", default="data/raw/fannie_mae_loan_performance/sf-loan-performance-data-sample.csv",
                              help="Path to the pipeline input sample file.")
    ingest_parser.add_argument("--output-dir", default=None,
                              help="Directory for the run artifact output. Defaults to artifacts/runs/sample_ingest/.")

    historical_parser = subparsers.add_parser(
        "historical-ingest",
        help="Ingest a bounded historical Fannie Mae quarter using a deterministic loan subset.",
    )
    historical_parser.add_argument("--input", default="data/raw/fannie_mae_loan_performance/2010Q1.csv",
                                  help="Path to the historical quarter CSV to inspect and ingest.")
    historical_parser.add_argument("--output-dir", default=None,
                                  help="Directory for the historical ingestion run artifacts.")
    historical_parser.add_argument("--max-loans", type=int, default=1000,
                                  help="Maximum count of loans to retain in the deterministic pilot subset. Ignored when --all-records is set.")
    historical_parser.add_argument("--all-records", action="store_true",
                                  help="Process every eligible row in the historical file and disable the pilot loan cap.")

    summary_parser = subparsers.add_parser("monthly-summary", help="Summarize the monthly sample dataset and record exposure diagnostics.")
    summary_parser.add_argument("--db", default=None, help="Path to the ingestion database output. If omitted, the selected sample_ingest run is used.")
    summary_parser.add_argument("--input-run", default=None, help="Explicit run ID under artifacts/runs/sample_ingest to use as the source of truth.")
    summary_parser.add_argument("--output-dir", default=None,
                               help="Directory for the monthly summary artifacts. Defaults to artifacts/runs/monthly_summary/.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            result = run_check(args.config, project_root=project_root_from_package())
        elif args.command == "sample-ingest":
            result = run_sample_ingest(args.input, project_root=project_root_from_package(), output_dir=args.output_dir)
        elif args.command == "historical-ingest":
            result = run_historical_ingest(
                args.input,
                project_root=project_root_from_package(),
                output_dir=args.output_dir,
                max_loans=args.max_loans,
                all_records=args.all_records,
            )
        elif args.command == "monthly-summary":
            result = run_monthly_summary(
                project_root=project_root_from_package(),
                input_db=args.db,
                input_run=args.input_run,
                output_dir=args.output_dir,
            )
        else:
            raise ValueError(f"Unsupported command: {args.command}")
    except (ConfigValidationError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps({
            "status": result["overall_status"],
            "run_id": result.get("run_id", "n/a"),
            "input_run_id": result.get("input_run_id", "n/a"),
            "package_version": result.get("package_version", __version__),
            "python_version": result.get("python_version", platform.python_version()),
            "git_revision": result.get("git_revision", "n/a"),
        }, sort_keys=True)
    )
    return 0 if result.get("overall_status") in {"pass", "ok"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
