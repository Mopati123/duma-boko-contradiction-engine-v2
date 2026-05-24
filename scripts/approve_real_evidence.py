#!/usr/bin/env python3
"""
Run deterministic Real Evidence Approval v1 dry-run records.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.real_evidence_approval import approve_real_evidence_dry_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate conservative real-evidence approval records."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate deterministic real-evidence approval records only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run:
        print("ERROR: Real Evidence Approval v1 supports --dry-run only.")
        return 1

    summary = approve_real_evidence_dry_run()
    print("== Real Evidence Approval v1 summary ==")
    print("Mode: dry-run")
    print(
        "total_evidence_items_evaluated: "
        f"{summary['total_evidence_items_evaluated']}"
    )
    print(f"approved_evidence_candidate: {summary['approved_evidence_candidate']}")
    print(
        "blocked_missing_real_evidence: "
        f"{summary['blocked_missing_real_evidence']}"
    )
    print(
        "blocked_manual_review_required: "
        f"{summary['blocked_manual_review_required']}"
    )
    print(
        "blocked_context_review_required: "
        f"{summary['blocked_context_review_required']}"
    )
    print(f"rejected_evidence: {summary['rejected_evidence']}")
    print(f"public_ready: {summary['public_ready']}")
    print(f"institutional_ready: {summary['institutional_ready']}")
    print(f"report_ready: {summary['report_ready']}")
    print(f"records_output: {summary['records_output']}")
    print(f"summary_output: {summary['summary_output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
