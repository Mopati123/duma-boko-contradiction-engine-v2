#!/usr/bin/env python3
"""
Inspect candidate-only evidence source recovery records.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.source_recovery import (
    group_source_recovery_candidates,
    load_source_recovery_candidates,
    summarize_source_recovery_candidates,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect unverified source recovery candidates."
    )
    parser.add_argument(
        "--evidence-id",
        help="Inspect candidates for a single original evidence ID.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = load_source_recovery_candidates(evidence_id=args.evidence_id)
    summary = summarize_source_recovery_candidates(records)
    grouped = group_source_recovery_candidates(records)

    print("== Evidence Source Recovery v1 summary ==")
    if args.evidence_id:
        print(f"evidence_id: {args.evidence_id}")
    print(f"total_candidates: {summary['total_candidates']}")
    print(f"jobs_candidates: {summary['jobs_candidates']}")
    print(f"health_candidates: {summary['health_candidates']}")
    print(f"approved_candidates: {summary['approved_candidates']}")
    print(f"public_ready: {summary['public_ready']}")
    print(f"institutional_ready: {summary['institutional_ready']}")
    print(f"report_ready: {summary['report_ready']}")

    for original_evidence_id in sorted(grouped):
        print()
        print(f"original_evidence_id: {original_evidence_id}")
        for record in sorted(
            grouped[original_evidence_id],
            key=lambda item: item.recovery_source_rank,
        ):
            print(f"- recovery_candidate_id: {record.recovery_candidate_id}")
            print(f"  recovery_source_rank: {record.recovery_source_rank}")
            print(f"  recovery_source_type: {record.recovery_source_type}")
            print(f"  recovery_source_url: {record.recovery_source_url}")
            print(f"  verification_status: {record.verification_status}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
