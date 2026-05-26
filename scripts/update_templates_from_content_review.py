#!/usr/bin/env python3
"""
Update real-evidence templates from candidate content-review sources.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.template_update_from_content_review import (
    update_templates_from_content_review,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update real-evidence templates from content-review candidates."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Show proposed template updates without writing templates. Default.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Write guarded entered_pending_review updates to templates.",
    )
    parser.add_argument(
        "--evidence-id",
        choices=("VID_JOBS_001", "VID_HEALTH_001"),
        help="Limit the update proposal to one evidence ID.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = update_templates_from_content_review(
        evidence_id=args.evidence_id or "",
        write=args.write,
    )

    print("== Template Update From Content Review v1 summary ==")
    print(f"Mode: {summary['mode']}")
    if args.evidence_id:
        print(f"evidence_id: {args.evidence_id}")
    print(f"selected_template_count: {summary['selected_template_count']}")
    print(f"entered_pending_review_count: {summary['entered_pending_review_count']}")
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
        print(f"update_status: {record.update_status}")
        print(f"source_url: {record.proposed_source_url}")
        print(f"verification_status: {record.verification_status}")
        print(
            "changed_fields: "
            + (", ".join(record.changed_fields) if record.changed_fields else "none")
        )
        if record.backup_path:
            print(f"backup_path: {record.backup_path}")
        print(f"diagnostic_notes: {record.diagnostic_notes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
