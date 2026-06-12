#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.temporal_same_object_pairing import build_temporal_same_object_pairing


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build neutral BEFORE/AFTER temporal comparison pairs by domain token overlap."
    )
    parser.add_argument(
        "--pair",
        action="store_true",
        help="Build deterministic same-object temporal comparison pairs.",
    )
    return parser.parse_args()


def main() -> int:
    parse_args()
    result = build_temporal_same_object_pairing()
    print("== Temporal Same-Object Pairing summary ==")
    print("Mode: pair")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
