#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.shadow_operations_telemetry import build_shadow_operations_telemetry


def parse_args():
    parser = argparse.ArgumentParser(description="Build shadow operations telemetry records.")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run only.")
    return parser.parse_args()


def main() -> int:
    parse_args()
    result = build_shadow_operations_telemetry()
    print("== Shadow Operations Telemetry Engine v1 summary ==")
    print("Mode: dry-run")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
