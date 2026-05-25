#!/usr/bin/env python3
"""
Interactive helper for human-entered real evidence input templates.

This script never fetches transcripts, invents evidence, approves evidence, or
changes release readiness. It only helps a human edit local template JSON files.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


TEMPLATE_DIR = Path("data/real_evidence_inputs")
TEMPLATE_GLOB = "*.template.json"

DISPLAY_FIELDS = ("evidence_id", "case_id", "source_url")
HUMAN_FIELDS = (
    "transcript_text",
    "timestamp_start",
    "timestamp_end",
    "quote_text",
    "speaker",
    "context_summary",
    "case_relevance_note",
    "reviewer",
    "reviewer_notes",
)
ALL_FIELDS = (*DISPLAY_FIELDS, *HUMAN_FIELDS, "verification_status")
TIMESTAMP_FIELDS = {"timestamp_start", "timestamp_end"}
TIMESTAMP_RE = re.compile(r"^(?:\d{2}:\d{2}|\d{2}:\d{2}:\d{2})$")
ALLOWED_WRITE_STATUSES = ("entered_pending_review", "verified_for_approval_review")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely fill human-entered real evidence input templates."
    )
    parser.add_argument(
        "--evidence-id",
        help="Fill or inspect only one evidence item, for example VID_JOBS_001.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show template status without prompting, writing files, or creating backups.",
    )
    return parser.parse_args()


def load_templates(evidence_id: str = "") -> List[Tuple[Path, Dict[str, str]]]:
    paths = sorted(TEMPLATE_DIR.glob(TEMPLATE_GLOB))
    if not paths:
        raise ValueError(f"No template files found in {TEMPLATE_DIR}")

    selected: List[Tuple[Path, Dict[str, str]]] = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Template must contain a JSON object: {path}")
        record = normalize_record(data)
        if evidence_id and record["evidence_id"] != evidence_id:
            continue
        selected.append((path, record))

    if evidence_id and not selected:
        raise ValueError(f"No template found for evidence_id={evidence_id}")
    return selected


def normalize_record(data: Dict[str, object]) -> Dict[str, str]:
    return {field: stringify(data.get(field, "")) for field in ALL_FIELDS}


def stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def validate_timestamp(value: str, field_name: str) -> None:
    if value and not TIMESTAMP_RE.match(value):
        raise ValueError(
            f"{field_name} must use HH:MM:SS or MM:SS format, got: {value}"
        )


def validate_record_timestamps(record: Dict[str, str]) -> None:
    for field in TIMESTAMP_FIELDS:
        validate_timestamp(record[field], field)


def missing_human_fields(record: Dict[str, str]) -> List[str]:
    return [field for field in HUMAN_FIELDS if not record[field].strip()]


def has_any_changes(original: Dict[str, str], updated: Dict[str, str]) -> bool:
    return any(original[field] != updated[field] for field in ALL_FIELDS)


def ordered_record(record: Dict[str, str]) -> Dict[str, str]:
    return {field: record[field] for field in ALL_FIELDS}


def print_template_header(path: Path, record: Dict[str, str]) -> None:
    print()
    print(f"== {path} ==")
    for field in DISPLAY_FIELDS:
        print(f"{field}: {record[field]}")
    print(f"verification_status: {record['verification_status']}")


def prompt_field(field: str, current_value: str) -> str:
    print()
    print(f"{field}")
    if current_value:
        print(f"Current value: {current_value}")
    else:
        print("Current value: <empty>")
    entered = input("New value, or press Enter to keep current: ")
    if not entered:
        return current_value
    return entered


def choose_verification_status(record: Dict[str, str]) -> str:
    missing = missing_human_fields(record)
    current_status = record["verification_status"]
    print()
    if missing:
        print("Missing human fields:")
        for field in missing:
            print(f"- {field}")
        print("verified_for_approval_review is refused until all fields are non-empty.")
        while True:
            choice = input(
                "verification_status "
                f"[Enter keeps {current_status}; type entered_pending_review to mark partial entry]: "
            ).strip()
            if not choice:
                if current_status == "verified_for_approval_review":
                    print(
                        "verified_for_approval_review cannot be kept while required "
                        "fields are missing."
                    )
                    continue
                return current_status
            if choice == "entered_pending_review":
                return choice
            if choice == "verified_for_approval_review":
                print(
                    "ERROR: verified_for_approval_review is refused while required "
                    "fields are missing."
                )
                continue
            print("ERROR: choose entered_pending_review or press Enter to keep current.")

    print("All required human fields are non-empty.")
    print("Choose verification_status:")
    print("1. verified_for_approval_review")
    print("2. entered_pending_review")
    choice = input(f"Selection [1/2, Enter keeps {current_status}]: ").strip()
    if not choice:
        return current_status
    if choice == "1":
        return "verified_for_approval_review"
    return "entered_pending_review"


def confirm_save(path: Path, original: Dict[str, str], updated: Dict[str, str]) -> bool:
    if not has_any_changes(original, updated):
        print("No changes detected; nothing to save.")
        return False

    print()
    print(f"Updated verification_status: {updated['verification_status']}")
    print("Fields with changes:")
    for field in ALL_FIELDS:
        if original[field] != updated[field]:
            old_value = "<empty>" if not original[field] else original[field]
            new_value = "<empty>" if not updated[field] else updated[field]
            print(f"- {field}: {old_value} -> {new_value}")

    answer = input(f"Save changes to {path}? [y/N]: ").strip().lower()
    return answer == "y"


def write_record(path: Path, record: Dict[str, str]) -> Path:
    backup_path = path.with_name(f"{path.name}.bak")
    shutil.copy2(path, backup_path)
    path.write_text(
        json.dumps(ordered_record(record), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return backup_path


def dry_run(records: Iterable[Tuple[Path, Dict[str, str]]]) -> int:
    total = 0
    ready = 0
    pending = 0
    for path, record in records:
        validate_record_timestamps(record)
        total += 1
        print_template_header(path, record)
        missing = missing_human_fields(record)
        if missing:
            pending += 1
            print("Missing human fields:")
            for field in missing:
                print(f"- {field}")
            print("eligible_status: entered_pending_review")
        else:
            ready += 1
            print("Missing human fields: none")
            print("eligible_status: verified_for_approval_review")
            print("alternate_status: entered_pending_review")

    print()
    print("== Manual real evidence input helper dry-run summary ==")
    print(f"templates_loaded: {total}")
    print(f"ready_for_approval_review: {ready}")
    print(f"still_pending_human_entry: {pending}")
    print("files_written: 0")
    print("backups_created: 0")
    return 0


def interactive_fill(records: Iterable[Tuple[Path, Dict[str, str]]]) -> int:
    processed = 0
    saved = 0
    skipped = 0
    backups: List[str] = []

    for path, original in records:
        processed += 1
        updated = dict(original)
        print_template_header(path, updated)

        for field in HUMAN_FIELDS:
            while True:
                candidate = prompt_field(field, updated[field])
                try:
                    if field in TIMESTAMP_FIELDS:
                        validate_timestamp(candidate, field)
                except ValueError as exc:
                    print(f"ERROR: {exc}")
                    continue
                updated[field] = candidate
                break

        updated["verification_status"] = choose_verification_status(updated)
        validate_record_timestamps(updated)

        if confirm_save(path, original, updated):
            backup_path = write_record(path, updated)
            saved += 1
            backups.append(str(backup_path))
            print(f"Saved {path}")
            print(f"Backup written: {backup_path}")
        else:
            skipped += 1
            print(f"Skipped {path}")

    print()
    print("== Manual real evidence input helper summary ==")
    print(f"templates_processed: {processed}")
    print(f"templates_saved: {saved}")
    print(f"templates_skipped: {skipped}")
    print("public_ready: False")
    print("institutional_ready: False")
    print("report_ready: False")
    if backups:
        print("backups_created:")
        for backup in backups:
            print(f"- {backup}")
    print()
    print("Next validation commands:")
    print("python scripts/validate_real_evidence_inputs.py --dry-run")
    print("./scripts/local_ci_v3.sh")
    return 0


def main() -> int:
    args = parse_args()
    try:
        records = load_templates(args.evidence_id or "")
        if args.dry_run:
            return dry_run(records)
        return interactive_fill(records)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
