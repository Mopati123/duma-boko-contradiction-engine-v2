#!/usr/bin/env python3
"""
Run deterministic Real Evidence Population v1 input validation.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.real_evidence_inputs import validate_real_evidence_inputs_dry_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate human-entry real evidence input templates."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate deterministic real-evidence input templates only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run:
        print("ERROR: Real Evidence Population v1 supports --dry-run only.")
        return 1

    summary = validate_real_evidence_inputs_dry_run()
    print("== Real Evidence Population v1 input summary ==")
    print("Mode: dry-run")
    print(f"total_input_records: {summary['total_input_records']}")
    print(f"pending_human_entry: {summary['pending_human_entry']}")
    print(f"entered_pending_review: {summary['entered_pending_review']}")
    print(f"rejected_do_not_use: {summary['rejected_do_not_use']}")
    print(f"verified_for_approval_review: {summary['verified_for_approval_review']}")
    print(
        "records_ready_for_approval_review: "
        f"{summary['records_ready_for_approval_review']}"
    )
    print(f"status_output: {summary['status_output']}")
    print(f"summary_output: {summary['summary_output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
