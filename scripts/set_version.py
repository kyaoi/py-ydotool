#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.version_tools import normalize_release_tag, parse_version, write_version


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Set the project version in VERSION and pyproject.toml.",
    )
    parser.add_argument("version", help="New semantic version, e.g. 0.1.1")
    args = parser.parse_args()

    parse_version(args.version)
    write_version(args.version)
    next_tag = normalize_release_tag(args.version)
    print(f"Updated version to {args.version}. Next release tag: {next_tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
