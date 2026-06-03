#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.temporal_discovery_strategy_upgrade import (
    build_temporal_discovery_strategy_upgrade,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 temporal discovery strategy upgrade records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate deterministic targeted temporal probes without internet access.",
    )
    mode.add_argument(
        "--probe-web",
        action="store_true",
        help="Attempt public discovery using targeted source-specific probes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "probe-web" if args.probe_web else "dry-run"
    result = build_temporal_discovery_strategy_upgrade(mode=selected_mode)
    print("== Temporal Discovery Strategy Upgrade v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
