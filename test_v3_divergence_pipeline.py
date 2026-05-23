#!/usr/bin/env python3
"""
Validate the active v3.0 Governance Promise-Delivery Divergence Engine.

This test validates the current divergence reconstruction artifact contract.
It does not validate the legacy semantic pipeline.
"""

import json
import subprocess
import sys
from pathlib import Path

from analysis.target_search import run_divergence_engine
from evidence.evidence_gate import validate_case_evidence_links
from evidence.word_exporter import WordExporter


def placeholder_url_parts():
    token = "example"
    return (
        ".".join((token, "com")),
        token + str(1),
        token + str(2),
        "youtube.com/watch?v=" + token,
    )


def is_placeholder_url(url: str) -> bool:
    return any(part in url.lower() for part in placeholder_url_parts())


def run_command(command: str) -> tuple[int, str]:
    result = subprocess.run(
        command,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(result.stdout)
    return result.returncode, result.stdout


def assert_nonempty_file(path: str) -> Path:
    p = Path(path)
    if not p.exists():
        raise AssertionError(f"Missing expected file: {path}")
    if p.stat().st_size <= 0:
        raise AssertionError(f"Expected non-empty file: {path}")
    return p


def assert_value_error(func, expected_text: str) -> None:
    try:
        func()
    except ValueError as exc:
        message = str(exc)
        if expected_text not in message:
            raise AssertionError(
                f"Expected ValueError containing {expected_text!r}, got {message!r}"
            )
        print(f"✓ expected evidence gate failure: {message}")
        return

    raise AssertionError("Expected ValueError was not raised")


def make_reportable_case(url: str, verification_status: str = "source_linked"):
    evidence_id = "CASE_TEST-PROMISE-001"
    evidence = {
        "evidence_id": evidence_id,
        "case_id": "CASE_TEST",
        "claim_role": "promise",
        "quote": "A sourced quote.",
        "source": "Known Source",
        "url": url,
        "date": "2024-01-01",
        "evidence_type": "video",
        "platform": "youtube",
        "verification_status": verification_status,
        "timestamp_start": None,
        "timestamp_end": None,
    }
    return {
        "case_id": "CASE_TEST",
        "evidence_objects": [evidence],
        "claim_evidence_links": {
            "promise": [evidence_id],
            "outcome_or_position": [evidence_id],
            "analysis": [evidence_id],
        },
    }


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
        "evidence_objects",
        "claim_evidence_links",
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

    required_evidence_keys = {
        "evidence_id",
        "case_id",
        "claim_role",
        "quote",
        "source",
        "url",
        "date",
        "evidence_type",
        "platform",
        "verification_status",
    }

    required_claim_links = {
        "promise",
        "outcome_or_position",
        "analysis",
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

            nested_url = nested.get("url", "")
            if not isinstance(nested_url, str):
                raise AssertionError(f"Case {idx}.{nested_key}.url must be a string")
            if is_placeholder_url(nested_url):
                raise AssertionError(
                    f"Case {idx}.{nested_key}.url must not be a placeholder"
                )

        if not isinstance(case["raw_urls"], list):
            raise AssertionError(f"Case {idx}.raw_urls must be a list")

        for raw_url in case["raw_urls"]:
            if not isinstance(raw_url, str):
                raise AssertionError(f"Case {idx}.raw_urls entries must be strings")
            if is_placeholder_url(raw_url):
                raise AssertionError(f"Case {idx}.raw_urls contains a placeholder")

        evidence_objects = case["evidence_objects"]
        if not isinstance(evidence_objects, list) or not evidence_objects:
            raise AssertionError(f"Case {idx}.evidence_objects must be non-empty")

        evidence_ids = set()
        for evidence_idx, evidence in enumerate(evidence_objects):
            if not isinstance(evidence, dict):
                raise AssertionError(
                    f"Case {idx}.evidence_objects[{evidence_idx}] must be an object"
                )

            missing_evidence = required_evidence_keys - set(evidence.keys())
            if missing_evidence:
                raise AssertionError(
                    f"Case {idx}.evidence_objects[{evidence_idx}] missing keys: "
                    f"{sorted(missing_evidence)}"
                )

            for evidence_key in required_evidence_keys:
                value = evidence[evidence_key]
                if evidence_key == "url":
                    if not isinstance(value, str):
                        raise AssertionError(
                            f"Case {idx}.evidence_objects[{evidence_idx}]."
                            f"{evidence_key} must be a string"
                        )
                    if is_placeholder_url(value):
                        raise AssertionError(
                            f"Case {idx}.evidence_objects[{evidence_idx}]."
                            f"{evidence_key} must not be a placeholder"
                        )
                    continue

                if not isinstance(value, str) or not value.strip():
                    raise AssertionError(
                        f"Case {idx}.evidence_objects[{evidence_idx}]."
                        f"{evidence_key} must be a non-empty string"
                    )

            verification_status = evidence["verification_status"]
            has_timestamp = bool(
                evidence.get("timestamp_start") or evidence.get("timestamp_end")
            )
            if verification_status == "timestamp_verified" and not has_timestamp:
                raise AssertionError(
                    f"Case {idx}.evidence_objects[{evidence_idx}] "
                    "cannot be timestamp_verified without timestamp fields"
                )

            evidence_id = evidence["evidence_id"]
            if evidence_id in evidence_ids:
                raise AssertionError(f"Case {idx} duplicate evidence_id: {evidence_id}")
            evidence_ids.add(evidence_id)

        claim_links = case["claim_evidence_links"]
        if not isinstance(claim_links, dict):
            raise AssertionError(f"Case {idx}.claim_evidence_links must be an object")

        for claim_key in required_claim_links:
            linked_ids = claim_links.get(claim_key)
            if not isinstance(linked_ids, list) or not linked_ids:
                raise AssertionError(
                    f"Case {idx}.claim_evidence_links.{claim_key} must be non-empty"
                )

            for evidence_id in linked_ids:
                if evidence_id not in evidence_ids:
                    raise AssertionError(
                        f"Case {idx}.claim_evidence_links.{claim_key} references "
                        f"unknown evidence_id: {evidence_id}"
                    )

    print(f"✓ divergence_cases.json OK: {len(cases)} cases")


def validate_gate_rejections() -> None:
    assert_value_error(
        lambda: validate_case_evidence_links(make_reportable_case("")),
        "evidence field url must be non-empty",
    )

    token = "example"
    placeholder_url = "https://www.youtube.com/watch?v=" + token + str(1)
    assert_value_error(
        lambda: validate_case_evidence_links(make_reportable_case(placeholder_url)),
        "evidence URL appears to be a placeholder",
    )

    assert_value_error(
        lambda: validate_case_evidence_links(
            make_reportable_case(
                "https://sources.local/evidence",
                verification_status="timestamp_verified",
            )
        ),
        "timestamp_verified evidence requires timestamp fields",
    )


def validate_report_source_text() -> None:
    forbidden_text = " ".join(("VALIDATED", "VIDEO", "EVIDENCE", "ATTACHED"))
    for path in (
        Path("evidence/word_exporter.py"),
        Path("evidence/final_report_generator.py"),
        Path("run_final_report.py"),
    ):
        if forbidden_text in path.read_text(encoding="utf-8"):
            raise AssertionError(f"{path} contains overclaimed report text")

    print("✓ report source text avoids overclaimed validation wording")


def main() -> int:
    validate_gate_rejections()
    validate_report_source_text()

    run_divergence_engine(
        Path("config/contradiction_targets.yaml"),
        Path("outputs/cases/divergence_cases.json"),
    )

    divergence_json = assert_nonempty_file("outputs/cases/divergence_cases.json")
    validate_divergence_cases(divergence_json)

    exporter = WordExporter(Path("outputs/reports"))
    assert_value_error(
        lambda: exporter.generate_report(
            json.loads(divergence_json.read_text(encoding="utf-8")).get("cases", []),
            "DUMA_BOKO_DIVERGENCE_REPORT_BLOCKED.docx",
        ),
        "evidence field url must be non-empty",
    )

    rc, output = run_command("python run_final_report.py")
    if rc == 0:
        print("run_final_report.py unexpectedly succeeded")
        return 1
    if "evidence field url must be non-empty" not in output:
        print("run_final_report.py failed for an unexpected reason")
        return 1

    print("=" * 70)
    print("ALL v3.0 EVIDENCE GATE TESTS PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
