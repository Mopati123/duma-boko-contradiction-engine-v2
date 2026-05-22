#!/usr/bin/env python3
"""
Validate the active v3.0 Governance Promise-Delivery Divergence Engine.

This test validates the current divergence reconstruction artifact contract.
It does not validate the legacy semantic pipeline.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_command(command: str) -> int:
    result = subprocess.run(
        command,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(result.stdout)
    return result.returncode


def assert_nonempty_file(path: str) -> Path:
    p = Path(path)
    if not p.exists():
        raise AssertionError(f"Missing expected file: {path}")
    if p.stat().st_size <= 0:
        raise AssertionError(f"Expected non-empty file: {path}")
    return p


def validate_divergence_cases(path: Path) -> None:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise AssertionError("divergence_cases.json must contain a JSON object")

    if "metadata" not in data:
        raise AssertionError("divergence_cases.json missing root key: metadata")

    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise AssertionError("divergence_cases.json must contain a non-empty cases list")

    required_case_keys = {
        "case_id",
        "topic",
        "promise",
        "outcome_or_position",
        "divergence_type",
        "analysis",
        "evidence_strength",
        "verification_status",
        "description",
        "raw_urls",
        "created_at",
        "pipeline_version",
    }

    required_source_keys = {
        "quote",
        "source",
        "url",
        "date",
        "evidence_type",
        "platform",
        "confidence",
    }

    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            raise AssertionError(f"Case {idx} must be an object")

        missing = required_case_keys - set(case.keys())
        if missing:
            raise AssertionError(f"Case {idx} missing keys: {sorted(missing)}")

        if case["pipeline_version"] != "divergence_engine_v3.0":
            raise AssertionError(
                f"Case {idx} has wrong pipeline_version: {case['pipeline_version']}"
            )

        for nested_key in ("promise", "outcome_or_position"):
            nested = case[nested_key]
            if not isinstance(nested, dict):
                raise AssertionError(f"Case {idx}.{nested_key} must be an object")

            missing_nested = required_source_keys - set(nested.keys())
            if missing_nested:
                raise AssertionError(
                    f"Case {idx}.{nested_key} missing keys: {sorted(missing_nested)}"
                )

        if not isinstance(case["raw_urls"], list):
            raise AssertionError(f"Case {idx}.raw_urls must be a list")

    print(f"✓ divergence_cases.json OK: {len(cases)} cases")


def main() -> int:
    rc = run_command("python run_engine.py")
    if rc != 0:
        print(f"run_engine.py failed with exit code {rc}")
        return 1

    divergence_json = assert_nonempty_file("outputs/cases/divergence_cases.json")
    validate_divergence_cases(divergence_json)

    today = datetime.now().strftime("%Y%m%d")
    assert_nonempty_file(
        f"outputs/reports/DUMA_BOKO_DIVERGENCE_REPORT_{today}.docx"
    )

    rc = run_command("python run_final_report.py")
    if rc != 0:
        print(f"run_final_report.py failed with exit code {rc}")
        return 1

    assert_nonempty_file("outputs/reports/DUMA_BOKO_FINAL_FORENSIC_REPORT.docx")

    print("=" * 70)
    print("ALL v3.0 DIVERGENCE PIPELINE TESTS PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
