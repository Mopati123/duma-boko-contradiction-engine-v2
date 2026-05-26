#!/usr/bin/env python3
"""
Apply human-supplied exact quote manual-entry records.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.exact_quote_manual_entry import apply_exact_quote_manual_entry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate or apply exact quote manual-entry JSON."
    )
    parser.add_argument("--entry-file", required=True, help="Manual entry JSON file.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validate without writing.")
    mode.add_argument("--write", action="store_true", help="Apply validated entry.")
    parser.add_argument(
        "--expect-rejected",
        action="store_true",
        help="Exit 0 only when the entry is rejected.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = apply_exact_quote_manual_entry(
        Path(args.entry_file),
        write=args.write,
    )
    record = summary["records"][0]

    print("== Exact Quote Manual Entry v1 summary ==")
    print(f"Mode: {summary['mode']}")
    print(f"entry_file: {args.entry_file}")
    print(f"entry_count: {summary['entry_count']}")
    print(f"accepted_count: {summary['accepted_count']}")
    print(f"rejected_count: {summary['rejected_count']}")
    print(f"write_blocked_count: {summary['write_blocked_count']}")
    print(f"applied_count: {summary['applied_count']}")
    print(f"write_count: {summary['write_count']}")
    print(f"backup_count: {summary['backup_count']}")
    print(f"quote_text_filled_count: {summary['quote_text_filled_count']}")
    print(
        "transcript_or_excerpt_filled_count: "
        f"{summary['transcript_or_excerpt_filled_count']}"
    )
    print(f"location_fields_filled_count: {summary['location_fields_filled_count']}")
    print(
        "verified_for_approval_review: "
        f"{summary['verified_for_approval_review']}"
    )
    print(f"approved_evidence: {summary['approved_evidence']}")
    print(f"public_ready: {summary['public_ready']}")
    print(f"institutional_ready: {summary['institutional_ready']}")
    print(f"report_ready: {summary['report_ready']}")
    print(f"status_output: {summary['status_output']}")
    print(f"summary_output: {summary['summary_output']}")
    print()
    print(f"evidence_id: {record.evidence_id}")
    print(f"entry_status: {record.entry_status}")
    print(f"evidence_location_type: {record.evidence_location_type}")
    print(
        "changed_fields: "
        + (", ".join(record.changed_fields) if record.changed_fields else "none")
    )
    print(
        "validation_errors: "
        + (
            "; ".join(record.validation_errors)
            if record.validation_errors
            else "none"
        )
    )
    print(
        "write_blockers: "
        + ("; ".join(record.write_blockers) if record.write_blockers else "none")
    )
    if record.backup_path:
        print(f"backup_path: {record.backup_path}")

    if args.expect_rejected:
        return 0 if record.entry_status == "rejected" else 1
    return 0 if record.entry_status != "rejected" else 1


if __name__ == "__main__":
    raise SystemExit(main())
