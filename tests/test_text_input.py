from __future__ import annotations

import pytest

from py_ydotool import TextInputUnavailableError
from py_ydotool.text_input import (
    available_text_backends,
    detect_text_backend,
    direct_text_backends,
    supported_text_backend_names,
)


def test_supported_text_backend_names() -> None:
    assert supported_text_backend_names() == ("ydotool", "wtype", "eitype", "paste")


def test_detect_text_backend_prefers_requested_backend(monkeypatch) -> None:
    monkeypatch.setattr("py_ydotool.text_input.shutil.which", lambda name: f"/usr/bin/{name}")

    backend = detect_text_backend("wtype", clipboard_available=False)

    assert backend.name == "wtype"
    assert backend.supports_direct_text is True
    assert backend.supports_unicode is True


def test_detect_text_backend_rejects_paste_without_clipboard(monkeypatch) -> None:
    monkeypatch.setattr("py_ydotool.text_input.shutil.which", lambda name: f"/usr/bin/{name}")

    with pytest.raises(TextInputUnavailableError, match="Clipboard access is unavailable"):
        detect_text_backend("paste", clipboard_available=False)


def test_available_text_backends_requires_clipboard_for_paste(monkeypatch) -> None:
    monkeypatch.setattr("py_ydotool.text_input.shutil.which", lambda name: f"/usr/bin/{name}")

    without_clipboard = available_text_backends(clipboard_available=False)
    with_clipboard = available_text_backends(clipboard_available=True)

    assert [backend.name for backend in without_clipboard] == ["ydotool", "wtype", "eitype"]
    assert [backend.name for backend in with_clipboard] == ["ydotool", "wtype", "eitype", "paste"]


def test_direct_text_backends_can_be_filtered_to_unicode() -> None:
    assert [backend.name for backend in direct_text_backends(supports_unicode=True)] == [
        "wtype",
        "eitype",
    ]
