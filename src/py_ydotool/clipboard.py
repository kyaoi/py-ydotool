from __future__ import annotations

import shutil
from dataclasses import dataclass

from .exceptions import ClipboardUnavailableError


@dataclass(frozen=True, slots=True)
class ClipboardBackend:
    name: str
    copy_command: tuple[str, ...]
    paste_command: tuple[str, ...]


def _require_commands(*names: str) -> bool:
    return all(shutil.which(name) is not None for name in names)


def detect_clipboard_backend(preferred: str | None = None) -> ClipboardBackend:
    backends: list[ClipboardBackend] = []

    if _require_commands("wl-copy", "wl-paste"):
        backends.append(
            ClipboardBackend(
                name="wl-clipboard",
                copy_command=("wl-copy",),
                paste_command=("wl-paste", "--no-newline"),
            )
        )

    if _require_commands("xclip"):
        backends.append(
            ClipboardBackend(
                name="xclip",
                copy_command=("xclip", "-selection", "clipboard"),
                paste_command=("xclip", "-selection", "clipboard", "-o"),
            )
        )

    if _require_commands("xsel"):
        backends.append(
            ClipboardBackend(
                name="xsel",
                copy_command=("xsel", "--clipboard", "--input"),
                paste_command=("xsel", "--clipboard", "--output"),
            )
        )

    if preferred is not None:
        for backend in backends:
            if backend.name == preferred:
                return backend
        raise ClipboardUnavailableError(
            f"Requested clipboard backend is not available: {preferred}"
        )

    if backends:
        return backends[0]

    raise ClipboardUnavailableError(
        "No supported clipboard backend found. Install wl-clipboard, xclip, or xsel."
    )
