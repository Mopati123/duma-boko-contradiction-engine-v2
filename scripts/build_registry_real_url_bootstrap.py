#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.registry_real_url_bootstrap import (
    apply_verified_registry_urls,
    build_registry_real_url_bootstrap,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 registry real URL bootstrap records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Refuse unresolved registry base URLs without network access.",
    )
    mode.add_argument(
        "--verify-public-urls",
        action="store_true",
        help="Verify only existing public HTTP(S) registry base URLs.",
    )
    mode.add_argument(
        "--apply-verified-registry",
        action="store_true",
        help="Apply previously verified registry URLs back to the tracked registry input.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.apply_verified_registry:
        result = apply_verified_registry_urls()
        selected_mode = "apply-verified-registry"
    else:
        selected_mode = "verify-public-urls" if args.verify_public_urls else "dry-run"
        result = build_registry_real_url_bootstrap(mode=selected_mode)

    print("== Registry Real URL Bootstrap Engine v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
