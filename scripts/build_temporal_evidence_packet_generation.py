#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.temporal_evidence_packet_generation import (
    build_temporal_evidence_packet_generation,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 temporal evidence packets from localized temporal segments."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate localized temporal segments without packet generation.",
    )
    mode.add_argument(
        "--from-segments",
        action="store_true",
        help="Create temporal evidence packets from localized temporal segments.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "from-segments" if args.from_segments else "dry-run"
    result = build_temporal_evidence_packet_generation(mode=selected_mode)
    print("== Temporal Evidence Packet Generation v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
