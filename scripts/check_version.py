#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.version_tools import check_repository_version, read_version_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check package version sync against pyproject and git tags.",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        dest="print_only",
        help="Print the current package version and exit.",
    )
    args = parser.parse_args()

    if args.print_only:
        print(read_version_file())
        return 0

    result = check_repository_version()
    stream = sys.stdout if result.ok else sys.stderr
    print(result.message, file=stream)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
