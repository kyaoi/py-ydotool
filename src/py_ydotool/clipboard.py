from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Literal

from .exceptions import ClipboardUnavailableError

ClipboardOperation = Literal["copy", "paste"]


@dataclass(frozen=True, slots=True)
class ClipboardBackend:
    name: str
    copy_command: tuple[str, ...]
    paste_command: tuple[str, ...]
    required_commands: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.required_commands:
            return
        object.__setattr__(
            self,
            "required_commands",
            tuple(dict.fromkeys((self.copy_command[0], self.paste_command[0]))),
        )

    def is_available(self) -> bool:
        return all(shutil.which(name) is not None for name in self.required_commands)

    def command_for(self, operation: ClipboardOperation) -> list[str]:
        if operation == "copy":
            return list(self.copy_command)
        if operation == "paste":
            return list(self.paste_command)
        raise ValueError("operation must be 'copy' or 'paste'")


_SUPPORTED_BACKENDS: tuple[ClipboardBackend, ...] = (
    ClipboardBackend(
        name="wl-clipboard",
        copy_command=("wl-copy",),
        paste_command=("wl-paste", "--no-newline"),
        required_commands=("wl-copy", "wl-paste"),
    ),
    ClipboardBackend(
        name="xclip",
        copy_command=("xclip", "-selection", "clipboard"),
        paste_command=("xclip", "-selection", "clipboard", "-o"),
        required_commands=("xclip",),
    ),
    ClipboardBackend(
        name="xsel",
        copy_command=("xsel", "--clipboard", "--input"),
        paste_command=("xsel", "--clipboard", "--output"),
        required_commands=("xsel",),
    ),
)


def _normalize_preferred_backend(preferred: str | None) -> str | None:
    if preferred is None:
        return None
    if not isinstance(preferred, str):
        raise TypeError("preferred must be a str")
    if not preferred:
        raise ValueError("preferred must not be empty")
    return preferred


def _join_backend_names(backends: tuple[ClipboardBackend, ...]) -> str:
    if not backends:
        return "none"
    return ", ".join(backend.name for backend in backends)


def _missing_backend_commands(backend: ClipboardBackend) -> str:
    missing = [name for name in backend.required_commands if shutil.which(name) is None]
    return ", ".join(missing)


def supported_clipboard_backend_names() -> tuple[str, ...]:
    return tuple(backend.name for backend in _SUPPORTED_BACKENDS)


def available_clipboard_backends() -> tuple[ClipboardBackend, ...]:
    return tuple(backend for backend in _SUPPORTED_BACKENDS if backend.is_available())


def detect_clipboard_backend(preferred: str | None = None) -> ClipboardBackend:
    preferred = _normalize_preferred_backend(preferred)
    available = available_clipboard_backends()

    if preferred is not None:
        backend = next((item for item in _SUPPORTED_BACKENDS if item.name == preferred), None)
        if backend is None:
            raise ClipboardUnavailableError(
                "Unsupported clipboard backend: "
                f"{preferred}. Supported backends: {_join_backend_names(_SUPPORTED_BACKENDS)}"
            )
        if backend.is_available():
            return backend
        missing_commands = _missing_backend_commands(backend)
        missing_help = f" Missing commands: {missing_commands}." if missing_commands else ""
        raise ClipboardUnavailableError(
            f"Requested clipboard backend is not available: {preferred}."
            f"{missing_help} Available backends: {_join_backend_names(available)}."
        )

    if available:
        return available[0]

    raise ClipboardUnavailableError(
        "No supported clipboard backend found. Install wl-clipboard, xclip, or xsel."
    )
