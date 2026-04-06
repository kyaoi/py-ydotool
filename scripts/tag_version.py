#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from py_ydotool._version_tools import get_worktree_status, read_version_file, sync_release_tag

VERSION_FILES = ("pyproject.toml", "uv.lock", "src/py_ydotool/VERSION")


def main() -> int:
    version = read_version_file()
    tag = f"v{version}"
    dirty = get_worktree_status()
    dirty_version_files = get_worktree_status(*VERSION_FILES)

    if dirty:
        if dirty_version_files:
            print(
                f"Working tree is dirty. Commit version files before tagging {tag}:",
                file=sys.stderr,
            )
            for line in dirty_version_files:
                print(line, file=sys.stderr)
        else:
            print(
                f"Working tree is dirty. Commit or stash changes before tagging {tag}.",
                file=sys.stderr,
            )
        return 1

    result = sync_release_tag(version)
    print(result.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
