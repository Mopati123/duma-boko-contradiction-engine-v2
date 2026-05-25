#!/usr/bin/env python3
"""
Inspect selected recovery sources for later content review.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.selected_recovery_source import (
    group_selected_recovery_sources,
    load_selected_recovery_sources,
    summarize_selected_recovery_sources,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect selected recovery sources for content review."
    )
    parser.add_argument(
        "--evidence-id",
        help="Inspect selected source for a single original evidence ID.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = load_selected_recovery_sources(evidence_id=args.evidence_id)
    summary = summarize_selected_recovery_sources(records)
    grouped = group_selected_recovery_sources(records)

    print("== Selected Recovery Source v1 summary ==")
    if args.evidence_id:
        print(f"evidence_id: {args.evidence_id}")
    print(f"selected_count: {summary['selected_count']}")
    print(f"pending_selection_count: {summary['pending_selection_count']}")
    print(f"approved_evidence: {summary['approved_evidence']}")
    print(f"public_ready: {summary['public_ready']}")
    print(f"institutional_ready: {summary['institutional_ready']}")
    print(f"report_ready: {summary['report_ready']}")

    for original_evidence_id in sorted(grouped):
        print()
        print(f"original_evidence_id: {original_evidence_id}")
        for record in sorted(
            grouped[original_evidence_id],
            key=lambda item: item.selected_recovery_candidate_id,
        ):
            print(
                f"- selected_recovery_candidate_id: "
                f"{record.selected_recovery_candidate_id}"
            )
            print(f"  selected_source_type: {record.selected_source_type}")
            print(f"  selected_source_url: {record.selected_source_url}")
            print(f"  selection_status: {record.selection_status}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
