from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Literal

from .exceptions import TextInputUnavailableError

TextInputMode = Literal["direct", "paste"]


@dataclass(frozen=True, slots=True)
class TextInputBackend:
    name: str
    mode: TextInputMode
    required_commands: tuple[str, ...] = ()
    supports_unicode: bool = False
    supports_direct_text: bool = True
    supports_timing_per_char: bool = True

    def is_available(self, *, clipboard_available: bool = False) -> bool:
        if self.mode == "paste" and not clipboard_available:
            return False
        return all(shutil.which(name) is not None for name in self.required_commands)

    def command_for_text(self, text: str, *, delay_ms: int = 0) -> list[str]:
        if self.mode != "direct":
            raise TextInputUnavailableError(
                f"Text backend {self.name} does not support direct text commands"
            )
        if self.name == "ydotool":
            command = ["ydotool", "type"]
            if delay_ms > 0:
                command.extend(["--key-delay", str(delay_ms)])
            command.append(text)
            return command
        if self.name == "wtype":
            command = ["wtype"]
            if delay_ms > 0:
                command.extend(["-d", str(delay_ms)])
            command.append(text)
            return command
        if self.name == "eitype":
            command = ["eitype"]
            if delay_ms > 0:
                command.extend(["-d", str(delay_ms)])
            command.append(text)
            return command
        raise TextInputUnavailableError(f"Unsupported direct text backend: {self.name}")


_SUPPORTED_BACKENDS: tuple[TextInputBackend, ...] = (
    TextInputBackend(
        name="ydotool",
        mode="direct",
        required_commands=("ydotool",),
        supports_unicode=False,
        supports_direct_text=True,
        supports_timing_per_char=True,
    ),
    TextInputBackend(
        name="wtype",
        mode="direct",
        required_commands=("wtype",),
        supports_unicode=True,
        supports_direct_text=True,
        supports_timing_per_char=True,
    ),
    TextInputBackend(
        name="eitype",
        mode="direct",
        required_commands=("eitype",),
        supports_unicode=True,
        supports_direct_text=True,
        supports_timing_per_char=True,
    ),
    TextInputBackend(
        name="paste",
        mode="paste",
        supports_unicode=True,
        supports_direct_text=False,
        supports_timing_per_char=False,
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


def _join_backend_names(backends: tuple[TextInputBackend, ...]) -> str:
    if not backends:
        return "none"
    return ", ".join(backend.name for backend in backends)


def _missing_backend_commands(backend: TextInputBackend) -> str:
    missing = [name for name in backend.required_commands if shutil.which(name) is None]
    return ", ".join(missing)


def get_text_backend(name: str) -> TextInputBackend:
    normalized = _normalize_preferred_backend(name)
    backend = next((item for item in _SUPPORTED_BACKENDS if item.name == normalized), None)
    if backend is None:
        raise TextInputUnavailableError(
            "Unsupported text backend: "
            f"{name}. Supported backends: {_join_backend_names(_SUPPORTED_BACKENDS)}"
        )
    return backend


def supported_text_backend_names() -> tuple[str, ...]:
    return tuple(backend.name for backend in _SUPPORTED_BACKENDS)


def available_text_backends(*, clipboard_available: bool = False) -> tuple[TextInputBackend, ...]:
    return tuple(
        backend
        for backend in _SUPPORTED_BACKENDS
        if backend.is_available(clipboard_available=clipboard_available)
    )


def direct_text_backends(*, supports_unicode: bool = False) -> tuple[TextInputBackend, ...]:
    return tuple(
        backend
        for backend in _SUPPORTED_BACKENDS
        if backend.mode == "direct" and (backend.supports_unicode or not supports_unicode)
    )


def detect_text_backend(
    preferred: str | None = None,
    *,
    clipboard_available: bool = False,
) -> TextInputBackend:
    preferred = _normalize_preferred_backend(preferred)
    available = available_text_backends(clipboard_available=clipboard_available)

    if preferred is not None:
        backend = next((item for item in _SUPPORTED_BACKENDS if item.name == preferred), None)
        if backend is None:
            raise TextInputUnavailableError(
                "Unsupported text backend: "
                f"{preferred}. Supported backends: {_join_backend_names(_SUPPORTED_BACKENDS)}"
            )
        if backend.is_available(clipboard_available=clipboard_available):
            return backend
        missing_commands = _missing_backend_commands(backend)
        missing_help = f" Missing commands: {missing_commands}." if missing_commands else ""
        clipboard_help = (
            " Clipboard access is unavailable for the paste backend."
            if backend.mode == "paste" and not clipboard_available
            else ""
        )
        raise TextInputUnavailableError(
            f"Requested text backend is not available: {preferred}."
            f"{missing_help}{clipboard_help}"
            f" Available backends: {_join_backend_names(available)}."
        )

    if available:
        return available[0]

    raise TextInputUnavailableError(
        "No supported text backend found. Install ydotool, wtype, or eitype, or enable "
        "a clipboard backend for paste fallback."
    )
