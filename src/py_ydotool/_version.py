from __future__ import annotations

from importlib import resources


def read_version() -> str:
    return resources.files("py_ydotool").joinpath("VERSION").read_text(encoding="utf-8").strip()


__version__ = read_version()
