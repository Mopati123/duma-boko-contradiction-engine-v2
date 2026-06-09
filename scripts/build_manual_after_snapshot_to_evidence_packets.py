#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.manual_after_snapshot_to_evidence_packets import (
    build_manual_after_snapshot_to_evidence_packets,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 manual AFTER snapshot evidence packets."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate manual AFTER snapshots without packet generation.",
    )
    mode.add_argument(
        "--from-snapshots",
        action="store_true",
        help="Create evidence packets from validated manual AFTER snapshots.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "from-snapshots" if args.from_snapshots else "dry-run"
    result = build_manual_after_snapshot_to_evidence_packets(mode=selected_mode)
    print("== Manual AFTER Snapshot To Evidence Packets v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
