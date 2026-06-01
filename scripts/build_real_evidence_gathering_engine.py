#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.real_evidence_gathering_engine import (
    DEFAULT_SEED_FILE,
    build_real_evidence_gathering_engine,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Build v2 real evidence gathering records.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Use deterministic demo seeds.")
    mode.add_argument("--from-seeds", action="store_true", help="Read real seed sources.")
    parser.add_argument(
        "--seed-file",
        default=str(DEFAULT_SEED_FILE),
        help="Seed JSON path for --from-seeds mode.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "from-seeds" if args.from_seeds else "dry-run"
    result = build_real_evidence_gathering_engine(
        mode=selected_mode,
        seed_file=Path(args.seed_file),
    )
    print("== Real Evidence Gathering Engine v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
