#!/usr/bin/env python3
"""
Run deterministic Final Approved Evidence Packet v1 dry-run.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.final_approved_packet import generate_final_approved_packet_dry_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate conservative final approved evidence packet metadata."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate deterministic final-approved-packet metadata only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run:
        print("ERROR: Final Approved Evidence Packet v1 supports --dry-run only.")
        return 1

    summary = generate_final_approved_packet_dry_run()
    print("== Final Approved Evidence Packet v1 summary ==")
    print("Mode: dry-run")
    print(f"packet_id: {summary['packet_id']}")
    print(f"report_id: {summary['report_id']}")
    print(f"packet_status: {summary['packet_status']}")
    print(f"approved_evidence_count: {summary['approved_evidence_count']}")
    print(f"blocked_evidence_count: {summary['blocked_evidence_count']}")
    print(f"packet_ready: {summary['packet_ready']}")
    print(f"public_ready: {summary['public_ready']}")
    print(f"institutional_ready: {summary['institutional_ready']}")
    print(f"report_ready: {summary['report_ready']}")
    print(f"record_output: {summary['record_output']}")
    print(f"summary_output: {summary['summary_output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
