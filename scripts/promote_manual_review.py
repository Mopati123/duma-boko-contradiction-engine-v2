#!/usr/bin/env python3
"""
Run guarded Manual Review Promotion v1 diagnostics.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.manual_review_promotion import promote_manual_review


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect real-evidence templates for manual-review promotion."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect templates without writing. Default.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Promote only records that pass all required-field checks.",
    )
    parser.add_argument(
        "--evidence-id",
        choices=("VID_JOBS_001", "VID_HEALTH_001"),
        help="Limit promotion inspection to one evidence ID.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = promote_manual_review(
        evidence_id=args.evidence_id or "",
        write=args.write,
    )

    print("== Manual Review Promotion v1 summary ==")
    print(f"Mode: {summary['mode']}")
    if args.evidence_id:
        print(f"evidence_id: {args.evidence_id}")
    print(f"selected_template_count: {summary['selected_template_count']}")
    print(f"promotion_ready_count: {summary['promotion_ready_count']}")
    print(
        "blocked_missing_required_fields_count: "
        f"{summary['blocked_missing_required_fields_count']}"
    )
    print(f"blocked_invalid_status_count: {summary['blocked_invalid_status_count']}")
    print(f"promoted_template_count: {summary['promoted_template_count']}")
    print(f"write_count: {summary['write_count']}")
    print(f"backup_count: {summary['backup_count']}")
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

    for record in summary["records"]:
        print()
        print(f"evidence_id: {record.evidence_id}")
        print(f"promotion_status: {record.promotion_status}")
        print(f"current_verification_status: {record.current_verification_status}")
        print(f"proposed_verification_status: {record.proposed_verification_status}")
        print(
            "missing_required_fields: "
            + (
                ", ".join(record.missing_required_fields)
                if record.missing_required_fields
                else "none"
            )
        )
        print(
            "blocker_reasons: "
            + (
                "; ".join(record.blocker_reasons)
                if record.blocker_reasons
                else "none"
            )
        )
        if record.backup_path:
            print(f"backup_path: {record.backup_path}")
        print(f"notes: {record.notes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
