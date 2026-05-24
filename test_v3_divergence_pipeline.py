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

from docx import Document

from analysis.target_search import run_divergence_engine
from evidence.evidence_ingestion import (
    load_or_build_evidence_index,
    load_transcript_artifact,
    upgrade_evidence_status,
)
from evidence.transcript_acquisition import (
    acquire_transcripts,
    extract_youtube_video_id,
    failure_artifact,
    transcript_found_artifact,
    upgrade_evidence_from_transcript_artifact,
    validate_transcript_artifact,
)
from evidence.timestamp_verification import (
    DEFAULT_TIMESTAMP_OUTPUT,
    TimestampCandidate,
    validate_timestamp_candidate,
    verify_timestamps_fixture_only,
)
from evidence.quote_verification import (
    DEFAULT_QUOTE_OUTPUT,
    QuoteCandidate,
    validate_quote_candidate,
    verify_quotes_fixture_only,
)
from evidence.case_evidence_linking import (
    DEFAULT_CASE_LINK_OUTPUT,
    CaseEvidenceLink,
    link_case_evidence_fixture_only,
    validate_case_evidence_link,
    validate_report_sections_resolve,
)
from evidence.report_section_assembly import (
    DEFAULT_REPORT_SECTION_OUTPUT,
    AssembledReportSection,
    assemble_report_sections_fixture_only,
    validate_assembled_report_section,
    validate_assembled_section_resolves,
)
from evidence.final_report_v1 import (
    DEFAULT_FINAL_REPORT_DOCX,
    DEFAULT_FINAL_REPORT_PAYLOAD,
    FinalReportPayload,
    generate_final_report_fixture_only,
    validate_final_report_payload,
)
from evidence.evidence_loader import DEFAULT_INDEX_PATH, build_evidence_index, load_seed_evidence
from evidence.evidence_gate import validate_case_evidence_links
from evidence.evidence_schema import (
    CaseObject,
    ClaimObject,
    EvidenceObject,
    ReportSection,
    TranscriptObject,
    validate_case_object,
    validate_claim_object,
    validate_evidence_object,
    validate_transcript_object,
)
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


def extract_docx_text(path: Path) -> str:
    document = Document(path)
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


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
        "source_type": "video",
        "platform": "youtube",
        "title": "Known Source",
        "url": url,
        "evidence_role": "promise",
        "verification_status": verification_status,
        "evidence_strength": "medium",
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
        "source_type",
        "platform",
        "title",
        "url",
        "evidence_role",
        "verification_status",
        "evidence_strength",
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
        "EvidenceObject.url must be a non-empty string",
    )

    token = "example"
    placeholder_url = "https://www.youtube.com/watch?v=" + token + str(1)
    assert_value_error(
        lambda: validate_case_evidence_links(make_reportable_case(placeholder_url)),
        "EvidenceObject.url appears to be a placeholder",
    )

    assert_value_error(
        lambda: validate_case_evidence_links(
            make_reportable_case(
                "https://sources.local/evidence",
                verification_status="timestamp_verified",
            )
        ),
        "requires timestamp_start and timestamp_end",
    )


def validate_schema_objects() -> None:
    evidence = EvidenceObject(
        evidence_id="VID_TEST_001",
        case_id="CASE_TEST",
        source_type="video",
        platform="youtube",
        title="Known Source",
        url="https://www.youtube.com/watch?v=abc123",
        evidence_role="promise_video",
        verification_status="source_found",
        evidence_strength="medium",
    )
    validate_evidence_object(evidence)

    assert_value_error(
        lambda: validate_evidence_object({**evidence.to_dict(), "url": ""}),
        "EvidenceObject.url must be a non-empty string",
    )

    token = "example"
    placeholder_url = "https://www.youtube.com/watch?v=" + token + str(1)
    assert_value_error(
        lambda: validate_evidence_object({**evidence.to_dict(), "url": placeholder_url}),
        "EvidenceObject.url appears to be a placeholder",
    )

    assert_value_error(
        lambda: validate_evidence_object(
            {**evidence.to_dict(), "verification_status": "timestamp_verified"}
        ),
        "requires timestamp_start and timestamp_end",
    )

    assert_value_error(
        lambda: validate_evidence_object(
            {
                **evidence.to_dict(),
                "verification_status": "quote_verified",
                "timestamp_start": "00:01",
                "timestamp_end": "00:10",
                "raw_quote": None,
            }
        ),
        "requires raw_quote",
    )

    claim = ClaimObject(
        claim_id="CLAIM_TEST_001",
        case_id="CASE_TEST",
        claim_type="promise",
        text="A sourced claim.",
        evidence_ids=[evidence.evidence_id],
        verification_status="source_found",
    )
    validate_claim_object(claim)

    assert_value_error(
        lambda: validate_claim_object({**claim.to_dict(), "evidence_ids": []}),
        "ClaimObject.evidence_ids must be a non-empty list",
    )

    case = CaseObject(
        case_id="CASE_TEST",
        title="Test Case",
        domain="governance",
        divergence_type="promise_vs_outcome",
        claims=[claim],
        evidence=[evidence],
        evidence_strength="medium",
        verification_status="source_found",
    )
    validate_case_object(case)

    unresolved_claim = ClaimObject(
        claim_id="CLAIM_TEST_002",
        case_id="CASE_TEST",
        claim_type="promise",
        text="An unresolved claim.",
        evidence_ids=["MISSING_EVIDENCE"],
        verification_status="source_found",
    )
    assert_value_error(
        lambda: validate_case_object({**case.to_dict(), "claims": [unresolved_claim]}),
        "references unknown evidence_id",
    )

    print("✓ EvidenceObject v1 schema validation OK")


def validate_ingestion_lane() -> None:
    index = load_or_build_evidence_index()
    if index["metadata"]["total_evidence_records"] != 2:
        raise AssertionError("Evidence ingestion index must contain 2 records")

    seed_evidence = load_seed_evidence()[0]
    validate_evidence_object(seed_evidence)

    pending_transcript = load_transcript_artifact(seed_evidence.evidence_id)
    if pending_transcript is None:
        raise AssertionError(f"Missing transcript artifact: {seed_evidence.evidence_id}")

    validate_transcript_object(pending_transcript)
    if pending_transcript.transcript_status != "pending":
        raise AssertionError("Seed transcript artifact must remain pending")

    assert_value_error(
        lambda: upgrade_evidence_status(seed_evidence, "timestamp_verified"),
        "Invalid evidence status transition",
    )

    assert_value_error(
        lambda: upgrade_evidence_status(seed_evidence, "transcript_found"),
        "requires a transcript artifact",
    )

    assert_value_error(
        lambda: upgrade_evidence_status(
            seed_evidence,
            "transcript_found",
            pending_transcript,
        ),
        "transcript_status=transcribed",
    )

    transcribed = TranscriptObject(
        evidence_id=seed_evidence.evidence_id,
        transcript_status="transcribed",
        transcript_text="Unit test transcript text.",
        source="unit-test",
        generated_by="unit-test",
        verification_notes="Unit test transcript fixture only.",
    )
    validate_transcript_object(transcribed)

    transcript_found = upgrade_evidence_status(
        seed_evidence,
        "transcript_found",
        transcribed,
    )
    if transcript_found.verification_status != "transcript_found":
        raise AssertionError("Evidence did not move to transcript_found")

    for immutable_field in ("evidence_id", "case_id", "url", "title"):
        if getattr(seed_evidence, immutable_field) != getattr(transcript_found, immutable_field):
            raise AssertionError(f"Evidence ingestion changed {immutable_field}")

    assert_value_error(
        lambda: upgrade_evidence_status(transcript_found, "timestamp_verified"),
        "requires timestamp_start and timestamp_end",
    )

    timestamped = upgrade_evidence_status(
        transcript_found,
        "timestamp_verified",
        timestamp_start="00:01",
        timestamp_end="00:05",
    )
    validate_evidence_object(timestamped)

    assert_value_error(
        lambda: upgrade_evidence_status(timestamped, "quote_verified"),
        "requires raw_quote",
    )

    quoted = upgrade_evidence_status(
        timestamped,
        "quote_verified",
        raw_quote="Unit test quote.",
    )
    validate_evidence_object(quoted)

    report_ready = upgrade_evidence_status(quoted, "report_ready")
    validate_evidence_object(report_ready)

    print("✓ Evidence Ingestion v1 lane validation OK")


def validate_transcript_acquisition_lane() -> None:
    seed_evidence = load_seed_evidence()[0]

    if extract_youtube_video_id(seed_evidence.url) != "e0MLzB5nGDc":
        raise AssertionError("YouTube watch URL video_id extraction failed")
    if extract_youtube_video_id("https://youtu.be/e0MLzB5nGDc") != "e0MLzB5nGDc":
        raise AssertionError("youtu.be URL video_id extraction failed")

    success_artifact = transcript_found_artifact(
        seed_evidence,
        [{"text": "Fixture transcript text for validation only."}],
        "fixture-test",
        "en",
    )
    validate_transcript_artifact(success_artifact)

    assert_value_error(
        lambda: validate_transcript_artifact(
            {**success_artifact.to_dict(), "transcript_text": ""}
        ),
        "transcript_text must be non-empty",
    )

    unavailable_artifact = failure_artifact(
        seed_evidence,
        "transcript_unavailable",
        "fixture-test",
        "No transcript available in fixture.",
    )
    validate_transcript_artifact(unavailable_artifact)

    failed_artifact = failure_artifact(
        seed_evidence,
        "acquisition_failed",
        "fixture-test",
        "Fixture provider failure.",
    )
    validate_transcript_artifact(failed_artifact)

    assert_value_error(
        lambda: validate_transcript_artifact(
            {**unavailable_artifact.to_dict(), "error": ""}
        ),
        "error must be non-empty",
    )

    assert_value_error(
        lambda: validate_transcript_artifact(
            {**failed_artifact.to_dict(), "transcript_text": "not allowed"}
        ),
        "transcript_text must be empty",
    )

    assert_value_error(
        lambda: validate_transcript_artifact(
            {**success_artifact.to_dict(), "verification_status": "timestamp_verified"}
        ),
        "cannot mark evidence as timestamp_verified",
    )

    upgraded = upgrade_evidence_from_transcript_artifact(seed_evidence, success_artifact)
    if upgraded.verification_status != "transcript_found":
        raise AssertionError("Transcript acquisition must only upgrade to transcript_found")
    if upgraded.timestamp_start or upgraded.timestamp_end or upgraded.raw_quote:
        raise AssertionError("Transcript acquisition must not set timestamps or raw_quote")

    assert_value_error(
        lambda: upgrade_evidence_from_transcript_artifact(
            seed_evidence,
            unavailable_artifact,
        ),
        "transcript_found is required",
    )

    summary = acquire_transcripts(fixtures_only=True)
    if summary["processed"] != 2:
        raise AssertionError("Fixture transcript acquisition must process 2 records")
    if summary["transcript_found"] != 0:
        raise AssertionError("Fixture acquisition must not invent transcript text")
    if summary["transcript_unavailable"] != 1 or summary["acquisition_failed"] != 1:
        raise AssertionError("Fixture acquisition counts are not deterministic")

    print("✓ Transcript Acquisition v1 lane validation OK")


def validate_timestamp_verification_lane() -> None:
    candidate = TimestampCandidate(
        evidence_id="VID_JOBS_001",
        case_id="CASE_002",
        phrase="500 000 new jobs",
        timestamp_start="00:00:10",
        timestamp_end="00:00:18",
        matched_text="We promised to create 500 000 new jobs in five years.",
        match_confidence=1.0,
        verification_status="timestamp_verified",
        verification_notes="Unit test timestamp fixture only.",
    )
    validate_timestamp_candidate(candidate)

    assert_value_error(
        lambda: validate_timestamp_candidate(
            {**candidate.to_dict(), "timestamp_start": ""}
        ),
        "timestamp_start must be a non-empty string",
    )

    assert_value_error(
        lambda: validate_timestamp_candidate(
            {**candidate.to_dict(), "timestamp_end": ""}
        ),
        "timestamp_end must be a non-empty string",
    )

    assert_value_error(
        lambda: validate_timestamp_candidate(
            {
                **candidate.to_dict(),
                "timestamp_start": "00:00:20",
                "timestamp_end": "00:00:10",
            }
        ),
        "timestamp_end must not be before start",
    )

    assert_value_error(
        lambda: validate_timestamp_candidate(
            {**candidate.to_dict(), "matched_text": ""}
        ),
        "matched_text must be a non-empty string",
    )

    assert_value_error(
        lambda: validate_timestamp_candidate(
            {
                **candidate.to_dict(),
                "phrase": "not in transcript",
            }
        ),
        "phrase must appear in matched_text",
    )

    assert_value_error(
        lambda: validate_timestamp_candidate(
            {
                **candidate.to_dict(),
                "evidence_verification_status": "quote_verified",
            }
        ),
        "cannot mark evidence as quote_verified",
    )

    summary = verify_timestamps_fixture_only()
    if summary["processed"] != 2:
        raise AssertionError("Timestamp fixture verification must process 2 records")
    if summary["candidates_found"] != 4:
        raise AssertionError("Timestamp fixture verification must produce 4 candidates")
    if summary["timestamp_verified"] != 4:
        raise AssertionError("Timestamp fixtures must verify 4 timestamp candidates")
    if summary["timestamp_rejected"] != 0 or summary["timestamp_unavailable"] != 0:
        raise AssertionError("Timestamp fixtures should not reject or miss candidates")

    for produced in summary["candidates"]:
        if produced.verification_status != "timestamp_verified":
            raise AssertionError("Fixture candidates must be timestamp_verified only")
        produced_data = produced.to_dict()
        if produced_data.get("raw_quote"):
            raise AssertionError("Timestamp verification must not set raw_quote")
        if produced_data.get("evidence_verification_status") == "quote_verified":
            raise AssertionError("Timestamp verification must not imply quote_verified")

    assert_nonempty_file(str(DEFAULT_TIMESTAMP_OUTPUT))
    print("✓ Timestamp Verification v1 lane validation OK")


def validate_quote_verification_lane() -> None:
    candidate = QuoteCandidate(
        evidence_id="VID_JOBS_001",
        case_id="CASE_002",
        phrase="500 000 new jobs",
        timestamp_start="00:00:10",
        timestamp_end="00:00:18",
        matched_text="We promised to create 500 000 new jobs in five years.",
        raw_quote="500 000 new jobs",
        quote_confidence=1.0,
        verification_status="quote_verified",
        verification_notes="Unit test quote fixture only. Report readiness pending.",
    )
    validate_quote_candidate(candidate)

    assert_value_error(
        lambda: validate_quote_candidate({**candidate.to_dict(), "raw_quote": ""}),
        "raw_quote must be a non-empty string",
    )

    assert_value_error(
        lambda: validate_quote_candidate(
            {**candidate.to_dict(), "timestamp_start": ""}
        ),
        "timestamp_start must be a non-empty string",
    )

    assert_value_error(
        lambda: validate_quote_candidate(
            {**candidate.to_dict(), "timestamp_end": ""}
        ),
        "timestamp_end must be a non-empty string",
    )

    assert_value_error(
        lambda: validate_quote_candidate({**candidate.to_dict(), "matched_text": ""}),
        "matched_text must be a non-empty string",
    )

    assert_value_error(
        lambda: validate_quote_candidate(
            {**candidate.to_dict(), "raw_quote": "not in transcript"}
        ),
        "raw_quote must be contained in matched_text",
    )

    assert_value_error(
        lambda: validate_quote_candidate(
            {
                **candidate.to_dict(),
                "verification_status": "quote_unavailable",
                "raw_quote": "",
                "verification_notes": "",
            }
        ),
        "verification_notes must be a non-empty string",
    )

    assert_value_error(
        lambda: validate_quote_candidate(
            {
                **candidate.to_dict(),
                "verification_status": "quote_rejected",
                "raw_quote": "",
                "verification_notes": "",
            }
        ),
        "verification_notes must be a non-empty string",
    )

    assert_value_error(
        lambda: validate_quote_candidate(
            {**candidate.to_dict(), "evidence_verification_status": "report_ready"}
        ),
        "cannot mark evidence as report_ready",
    )

    summary = verify_quotes_fixture_only()
    if summary["processed"] != 4:
        raise AssertionError("Quote fixture verification must process 4 timestamps")
    if summary["quote_verified"] != 4:
        raise AssertionError("Quote fixtures must verify 4 quote candidates")
    if (
        summary["quote_candidate_found"] != 0
        or summary["quote_rejected"] != 0
        or summary["quote_unavailable"] != 0
    ):
        raise AssertionError("Quote fixtures should not be pending, rejected, or missed")

    for produced in summary["candidates"]:
        if produced.verification_status != "quote_verified":
            raise AssertionError("Fixture quote candidates must be quote_verified only")
        produced_data = produced.to_dict()
        if produced_data.get("evidence_verification_status") == "report_ready":
            raise AssertionError("Quote verification must not imply report_ready")
        if "TEST FIXTURE ONLY" not in produced.verification_notes:
            raise AssertionError("Fixture quote candidates must be clearly labeled")

    assert_nonempty_file(str(DEFAULT_QUOTE_OUTPUT))
    print("✓ Quote Verification v1 lane validation OK")


def validate_case_evidence_linking_lane() -> None:
    link = CaseEvidenceLink(
        case_id="CASE_002",
        claim_id="CLAIM_JOBS_001",
        evidence_id="VID_JOBS_001",
        quote_id="QUOTE_VID_JOBS_001_500_000_NEW_JOBS",
        phrase="500 000 new jobs",
        timestamp_start="00:00:10",
        timestamp_end="00:00:18",
        raw_quote="500 000 new jobs",
        link_status="link_verified",
        link_notes="Unit test link fixture only. Report readiness pending.",
    )
    validate_case_evidence_link(link)

    for field_name in ("case_id", "claim_id", "evidence_id", "quote_id", "raw_quote"):
        assert_value_error(
            lambda field_name=field_name: validate_case_evidence_link(
                {**link.to_dict(), field_name: ""}
            ),
            f"{field_name} must be a non-empty string",
        )

    assert_value_error(
        lambda: validate_case_evidence_link(
            {
                **link.to_dict(),
                "link_status": "link_rejected",
                "link_notes": "",
            }
        ),
        "link_notes must be a non-empty string",
    )

    assert_value_error(
        lambda: validate_case_evidence_link(
            {
                **link.to_dict(),
                "link_status": "link_unavailable",
                "link_notes": "",
            }
        ),
        "link_notes must be a non-empty string",
    )

    assert_value_error(
        lambda: validate_case_evidence_link(
            {**link.to_dict(), "evidence_verification_status": "report_ready"}
        ),
        "cannot mark evidence as report_ready",
    )

    seed_evidence = load_seed_evidence()[0]
    unresolved_claim = ClaimObject(
        claim_id="CLAIM_UNRESOLVED",
        case_id=seed_evidence.case_id,
        claim_type="unit_test",
        text="Unit test unresolved evidence claim.",
        evidence_ids=["MISSING_EVIDENCE"],
        verification_status="quote_linked_fixture",
    )
    unresolved_case = CaseObject(
        case_id=seed_evidence.case_id,
        title="Unit test unresolved evidence case",
        domain="unit_test",
        divergence_type="unit_test",
        claims=[unresolved_claim],
        evidence=[seed_evidence],
        evidence_strength=seed_evidence.evidence_strength,
        verification_status="quote_linked_fixture",
    )
    assert_value_error(
        lambda: validate_case_object(unresolved_case),
        "references unknown evidence_id: MISSING_EVIDENCE",
    )

    resolved_claim = ClaimObject(
        claim_id="CLAIM_RESOLVED",
        case_id=seed_evidence.case_id,
        claim_type="unit_test",
        text="Unit test resolved evidence claim.",
        evidence_ids=[seed_evidence.evidence_id],
        verification_status="quote_linked_fixture",
    )
    resolved_case = CaseObject(
        case_id=seed_evidence.case_id,
        title="Unit test resolved evidence case",
        domain="unit_test",
        divergence_type="unit_test",
        claims=[resolved_claim],
        evidence=[seed_evidence],
        evidence_strength=seed_evidence.evidence_strength,
        verification_status="quote_linked_fixture",
    )
    validate_case_object(resolved_case)
    unresolved_section = ReportSection(
        section_id="SECTION_UNRESOLVED",
        case_id=seed_evidence.case_id,
        heading="Unit test unresolved section",
        body="Unit test section body.",
        evidence_ids=["MISSING_EVIDENCE"],
    )
    assert_value_error(
        lambda: validate_report_sections_resolve(
            resolved_case,
            [unresolved_section],
        ),
        "references unknown evidence_id: MISSING_EVIDENCE",
    )

    summary = link_case_evidence_fixture_only()
    if summary["processed"] != 4:
        raise AssertionError("Case linking fixture must process 4 quote candidates")
    if summary["link_verified"] != 2:
        raise AssertionError("Case linking fixtures must verify 2 links")
    if summary["link_unavailable"] != 2:
        raise AssertionError("Case linking fixtures must leave 2 quotes unavailable")
    if summary["link_candidate"] != 0 or summary["link_rejected"] != 0:
        raise AssertionError("Case linking fixtures should not be pending or rejected")
    if summary["cases_built"] != 2:
        raise AssertionError("Case linking fixtures must build 2 cases")
    if summary["claims_built"] != 2:
        raise AssertionError("Case linking fixtures must build 2 claims")
    if summary["report_sections_built"] != 2:
        raise AssertionError("Case linking fixtures must build 2 report sections")

    for produced in summary["links"]:
        produced_data = produced.to_dict()
        if produced_data.get("evidence_verification_status") == "report_ready":
            raise AssertionError("Case evidence linking must not imply report_ready")
        if "TEST FIXTURE ONLY" not in produced.link_notes:
            raise AssertionError("Fixture case links must be clearly labeled")

    assert_nonempty_file(str(DEFAULT_CASE_LINK_OUTPUT))
    print("✓ Case Evidence Linking v1 lane validation OK")


def validate_report_section_assembly_lane() -> None:
    section = AssembledReportSection(
        section_id="SECTION_CASE_002_JOBS",
        case_id="CASE_002",
        claim_ids=["CLAIM_JOBS_001"],
        evidence_ids=["VID_JOBS_001"],
        heading="Jobs Creation Promise Evidence",
        body="TEST FIXTURE ONLY. Unit test assembled section.",
        raw_quotes=["500 000 new jobs"],
        timestamp_refs=[
            {
                "evidence_id": "VID_JOBS_001",
                "timestamp_start": "00:00:10",
                "timestamp_end": "00:00:18",
            }
        ],
        assembly_status="assembly_verified",
        assembly_notes="TEST FIXTURE ONLY. Report readiness pending.",
    )
    validate_assembled_report_section(section)

    for field_name in ("section_id", "case_id", "heading", "body"):
        assert_value_error(
            lambda field_name=field_name: validate_assembled_report_section(
                {**section.to_dict(), field_name: ""}
            ),
            f"{field_name} must be a non-empty string",
        )

    for field_name in ("claim_ids", "evidence_ids"):
        assert_value_error(
            lambda field_name=field_name: validate_assembled_report_section(
                {**section.to_dict(), field_name: []}
            ),
            f"{field_name} must be a non-empty list",
        )

    assert_value_error(
        lambda: validate_assembled_report_section(
            {**section.to_dict(), "raw_quotes": []}
        ),
        "raw_quotes must be a non-empty list",
    )

    assert_value_error(
        lambda: validate_assembled_report_section(
            {**section.to_dict(), "timestamp_refs": []}
        ),
        "timestamp_refs must be a non-empty list",
    )

    assert_value_error(
        lambda: validate_assembled_report_section(
            {
                **section.to_dict(),
                "assembly_status": "assembly_rejected",
                "raw_quotes": [],
                "timestamp_refs": [],
                "assembly_notes": "",
            }
        ),
        "assembly_notes must be a non-empty string",
    )

    assert_value_error(
        lambda: validate_assembled_report_section(
            {
                **section.to_dict(),
                "assembly_status": "assembly_unavailable",
                "raw_quotes": [],
                "timestamp_refs": [],
                "assembly_notes": "",
            }
        ),
        "assembly_notes must be a non-empty string",
    )

    assert_value_error(
        lambda: validate_assembled_report_section(
            {**section.to_dict(), "evidence_verification_status": "report_ready"}
        ),
        "cannot mark evidence as report_ready",
    )

    seed_evidence = load_seed_evidence()[0]
    claim = ClaimObject(
        claim_id="CLAIM_RESOLVED",
        case_id=seed_evidence.case_id,
        claim_type="unit_test",
        text="Unit test resolved evidence claim.",
        evidence_ids=[seed_evidence.evidence_id],
        verification_status="quote_linked_fixture",
    )
    case = CaseObject(
        case_id=seed_evidence.case_id,
        title="Unit test resolved evidence case",
        domain="unit_test",
        divergence_type="unit_test",
        claims=[claim],
        evidence=[seed_evidence],
        evidence_strength=seed_evidence.evidence_strength,
        verification_status="quote_linked_fixture",
    )
    validate_case_object(case)
    unresolved_section = AssembledReportSection(
        section_id="SECTION_UNRESOLVED",
        case_id=seed_evidence.case_id,
        claim_ids=[claim.claim_id],
        evidence_ids=["MISSING_EVIDENCE"],
        heading="Unit test unresolved assembled section",
        body="TEST FIXTURE ONLY. Unit test assembled section.",
        raw_quotes=["500 000 new jobs"],
        timestamp_refs=[
            {
                "evidence_id": "MISSING_EVIDENCE",
                "timestamp_start": "00:00:10",
                "timestamp_end": "00:00:18",
            }
        ],
        assembly_status="assembly_verified",
        assembly_notes="TEST FIXTURE ONLY. Report readiness pending.",
    )
    assert_value_error(
        lambda: validate_assembled_section_resolves(unresolved_section, case),
        "references unknown evidence_id: MISSING_EVIDENCE",
    )

    summary = assemble_report_sections_fixture_only()
    if summary["processed"] != 4:
        raise AssertionError("Report section assembly must process 4 case links")
    if summary["sections_verified"] != 2:
        raise AssertionError("Report section fixtures must verify 2 sections")
    if summary["sections_unavailable"] != 2:
        raise AssertionError("Report section fixtures must leave 2 sections unavailable")
    if summary["sections_candidate"] != 0 or summary["sections_rejected"] != 0:
        raise AssertionError("Report section fixtures should not be pending or rejected")
    if summary["cases_represented"] != 2:
        raise AssertionError("Report section fixtures must represent 2 cases")
    if summary["evidence_ids_represented"] != 2:
        raise AssertionError("Report section fixtures must represent 2 evidence IDs")

    for produced in summary["sections"]:
        produced_data = produced.to_dict()
        if produced_data.get("evidence_verification_status") == "report_ready":
            raise AssertionError("Report section assembly must not imply report_ready")
        if "TEST FIXTURE ONLY" not in produced.assembly_notes:
            raise AssertionError("Fixture report sections must be clearly labeled")

    assert_nonempty_file(str(DEFAULT_REPORT_SECTION_OUTPUT))
    print("✓ Report Section Assembly v1 lane validation OK")


def validate_final_report_generation_lane() -> None:
    assembly_summary = assemble_report_sections_fixture_only()
    verified_sections = [
        section.to_dict()
        for section in assembly_summary["sections"]
        if section.assembly_status == "assembly_verified"
    ]
    payload = FinalReportPayload(
        report_id="DUMA_BOKO_REVIEW_DRAFT_V1_FIXTURE",
        title="Duma Boko Evidence Pipeline Review Draft",
        report_status="review_draft",
        generated_from=str(DEFAULT_REPORT_SECTION_OUTPUT),
        sections=verified_sections,
        evidence_disclaimer=(
            "Review draft fixture-based validation artifact. Not for public release. "
            "Fixture sections are not public evidence and not a public evidentiary "
            "conclusion."
        ),
        methodology_note=(
            "Evidence pipeline demonstration using deterministic fixtures only. "
            "Requires real transcript/timestamp/quote replacement before publication."
        ),
        limitations_note=(
            "This review draft is non-public, non-final, and cannot be used as an "
            "evidentiary conclusion."
        ),
        generation_notes=(
            "Generated for local pipeline validation only. Publication readiness is "
            "not set and release remains gated."
        ),
    )
    validate_final_report_payload(payload)

    for field_name in (
        "report_id",
        "title",
        "evidence_disclaimer",
        "methodology_note",
        "limitations_note",
        "generation_notes",
    ):
        assert_value_error(
            lambda field_name=field_name: validate_final_report_payload(
                {**payload.to_dict(), field_name: ""}
            ),
            f"{field_name} must be a non-empty string",
        )

    assert_value_error(
        lambda: validate_final_report_payload({**payload.to_dict(), "sections": []}),
        "sections must be a non-empty list for review_draft",
    )

    assert_value_error(
        lambda: validate_final_report_payload(
            {
                **payload.to_dict(),
                "report_status": "blocked",
                "sections": [],
                "generation_notes": "Blocked pending review.",
            }
        ),
        "blocked requires a reason",
    )

    assert_value_error(
        lambda: validate_final_report_payload(
            {
                **payload.to_dict(),
                "report_status": "generation_failed",
                "sections": [],
                "generation_notes": "Generation failed during review.",
            }
        ),
        "generation_failed requires a reason",
    )

    assert_value_error(
        lambda: validate_final_report_payload({**payload.to_dict(), "report_ready": True}),
        "cannot mark evidence as report_ready",
    )

    summary = generate_final_report_fixture_only()
    if summary["report_status"] != "review_draft":
        raise AssertionError("Final Report Generation v1 must create review_draft only")
    if summary["sections_included"] != 2:
        raise AssertionError("Final Report Generation v1 must include 2 fixture sections")
    if summary["evidence_ids_represented"] != 2:
        raise AssertionError(
            "Final Report Generation v1 must represent 2 fixture evidence IDs"
        )

    payload_path = assert_nonempty_file(str(DEFAULT_FINAL_REPORT_PAYLOAD))
    docx_path = assert_nonempty_file(str(DEFAULT_FINAL_REPORT_DOCX))

    generated_payload = json.loads(payload_path.read_text(encoding="utf-8"))
    generated_text = json.dumps(generated_payload, sort_keys=True).lower()
    docx_text = extract_docx_text(docx_path)
    combined_text = f"{generated_text}\n{docx_text}".lower()

    for required_text in (
        "review draft",
        "not for public release",
        "fixture-based validation artifact",
        "not a public evidentiary conclusion",
        "requires real transcript/timestamp/quote replacement before publication",
    ):
        if required_text not in combined_text:
            raise AssertionError(
                f"Final Report Generation v1 missing required wording: {required_text}"
            )

    for forbidden_text in (
        "validated public evidence",
        "final forensic report",
        "institution-ready",
        "proven corruption",
        "proven failure",
        "report_ready",
    ):
        if forbidden_text in combined_text:
            raise AssertionError(
                f"Final Report Generation v1 overclaims with: {forbidden_text}"
            )

    print("✓ Final Report Generation v1 lane validation OK")


def validate_seed_evidence_index() -> None:
    seed_evidence = load_seed_evidence()
    if len(seed_evidence) != 2:
        raise AssertionError(f"Expected 2 seed evidence records, got {len(seed_evidence)}")

    index = build_evidence_index()
    if index["metadata"]["total_evidence_records"] != 2:
        raise AssertionError("evidence_index.json must contain 2 evidence records")

    assert_nonempty_file(str(DEFAULT_INDEX_PATH))
    print("✓ seed evidence index OK: 2 records")


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
    validate_schema_objects()
    validate_ingestion_lane()
    validate_transcript_acquisition_lane()
    validate_timestamp_verification_lane()
    validate_quote_verification_lane()
    validate_case_evidence_linking_lane()
    validate_report_section_assembly_lane()
    validate_final_report_generation_lane()
    validate_gate_rejections()
    validate_seed_evidence_index()
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
        "EvidenceObject.url must be a non-empty string",
    )

    rc, output = run_command("python run_final_report.py")
    if rc == 0:
        print("run_final_report.py unexpectedly succeeded")
        return 1
    if "EvidenceObject.url must be a non-empty string" not in output:
        print("run_final_report.py failed for an unexpected reason")
        return 1

    print("=" * 70)
    print("ALL v3.0 EVIDENCE GATE TESTS PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
