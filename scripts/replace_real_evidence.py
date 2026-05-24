#!/usr/bin/env python3
"""
Run conservative real evidence replacement checks.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.real_evidence_replacement import replace_real_evidence
from evidence.transcript_acquisition import TARGET_EVIDENCE_IDS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect or acquire real evidence replacement artifacts."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect existing real transcript artifacts and write ignored outputs.",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help="Attempt live transcript acquisition for the selected evidence.",
    )
    parser.add_argument(
        "--evidence-id",
        choices=TARGET_EVIDENCE_IDS,
        help="Limit processing to one seed evidence ID.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = replace_real_evidence(
        dry_run=args.dry_run,
        live=args.live,
        evidence_id=args.evidence_id,
    )

    print("== Real Evidence Replacement v1 summary ==")
    print(f"Mode: {'live' if args.live else 'dry-run'}")
    print(f"Total evidence records processed: {summary['processed']}")
    print(f"transcript_found_real: {summary['transcript_found_real']}")
    print(f"timestamp_candidate_real: {summary['timestamp_candidate_real']}")
    print(f"quote_candidate_real: {summary['quote_candidate_real']}")
    print(f"manual_review_required: {summary['manual_review_required']}")
    print(f"unavailable: {summary['unavailable']}")
    print(f"acquisition_failed: {summary['acquisition_failed']}")
    print(f"status_output: {summary['status_output']}")
    print(f"timestamp_output: {summary['timestamp_output']}")
    print(f"quote_output: {summary['quote_output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
