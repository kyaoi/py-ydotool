import subprocess

import pytest

from py_ydotool import PyYDoTool
from py_ydotool.clipboard import (
    ClipboardBackend,
    available_clipboard_backends,
    detect_clipboard_backend,
    supported_clipboard_backend_names,
)
from py_ydotool.exceptions import ClipboardUnavailableError


def test_detect_clipboard_backend_prefers_wl_clipboard(monkeypatch) -> None:
    mapping = {
        "wl-copy": "/usr/bin/wl-copy",
        "wl-paste": "/usr/bin/wl-paste",
        "xclip": "/usr/bin/xclip",
        "xsel": "/usr/bin/xsel",
    }

    monkeypatch.setattr(
        "py_ydotool.clipboard.shutil.which",
        lambda name: mapping.get(name),
    )

    backend = detect_clipboard_backend()

    assert backend.name == "wl-clipboard"
    assert backend.copy_command == ("wl-copy",)
    assert backend.paste_command == ("wl-paste", "--no-newline")


def test_available_clipboard_backends_returns_detectable_backends_in_priority_order(
    monkeypatch,
) -> None:
    mapping = {
        "wl-copy": "/usr/bin/wl-copy",
        "wl-paste": "/usr/bin/wl-paste",
        "xclip": "/usr/bin/xclip",
    }

    monkeypatch.setattr(
        "py_ydotool.clipboard.shutil.which",
        lambda name: mapping.get(name),
    )

    backends = available_clipboard_backends()

    assert [backend.name for backend in backends] == ["wl-clipboard", "xclip"]


def test_detect_clipboard_backend_falls_back_to_xclip(monkeypatch) -> None:
    mapping = {
        "xclip": "/usr/bin/xclip",
    }

    monkeypatch.setattr(
        "py_ydotool.clipboard.shutil.which",
        lambda name: mapping.get(name),
    )

    backend = detect_clipboard_backend()

    assert backend.name == "xclip"


def test_detect_clipboard_backend_falls_back_to_xsel(monkeypatch) -> None:
    mapping = {
        "xsel": "/usr/bin/xsel",
    }

    monkeypatch.setattr(
        "py_ydotool.clipboard.shutil.which",
        lambda name: mapping.get(name),
    )

    backend = detect_clipboard_backend()

    assert backend.name == "xsel"


def test_detect_clipboard_backend_with_preferred(monkeypatch) -> None:
    mapping = {
        "xclip": "/usr/bin/xclip",
    }

    monkeypatch.setattr(
        "py_ydotool.clipboard.shutil.which",
        lambda name: mapping.get(name),
    )

    backend = detect_clipboard_backend("xclip")

    assert backend.name == "xclip"


def test_detect_clipboard_backend_raises_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "py_ydotool.clipboard.shutil.which",
        lambda name: None,
    )

    try:
        detect_clipboard_backend()
    except ClipboardUnavailableError:
        pass
    else:
        raise AssertionError("ClipboardUnavailableError was not raised")


def test_detect_clipboard_backend_reports_missing_commands_for_unavailable_preference(
    monkeypatch,
) -> None:
    mapping = {
        "xclip": "/usr/bin/xclip",
    }

    monkeypatch.setattr(
        "py_ydotool.clipboard.shutil.which",
        lambda name: mapping.get(name),
    )

    with pytest.raises(ClipboardUnavailableError) as exc_info:
        detect_clipboard_backend("wl-clipboard")

    message = str(exc_info.value)
    assert "Missing commands: wl-copy, wl-paste" in message
    assert "Available backends: xclip" in message


def test_detect_clipboard_backend_rejects_unknown_preference(monkeypatch) -> None:
    monkeypatch.setattr(
        "py_ydotool.clipboard.shutil.which",
        lambda name: None,
    )

    with pytest.raises(
        ClipboardUnavailableError,
        match="Supported backends: wl-clipboard, xclip, xsel",
    ):
        detect_clipboard_backend("unknown")


def test_detect_clipboard_backend_rejects_empty_preference() -> None:
    with pytest.raises(ValueError, match="preferred must not be empty"):
        detect_clipboard_backend("")


def test_supported_clipboard_backend_names_lists_all_supported_backends() -> None:
    assert supported_clipboard_backend_names() == ("wl-clipboard", "xclip", "xsel")


def test_copy_path_discards_subprocess_output(monkeypatch) -> None:
    seen_capture_output: list[bool | None] = []
    seen_stdout: list[object | None] = []
    seen_stderr: list[object | None] = []

    def fake_run(*args, **kwargs):
        seen_capture_output.append(kwargs.get("capture_output"))
        seen_stdout.append(kwargs.get("stdout"))
        seen_stderr.append(kwargs.get("stderr"))
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr("py_ydotool.client.subprocess.run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False)
    tool._clipboard = ClipboardBackend(
        name="test",
        copy_command=("copy-cmd",),
        paste_command=("paste-cmd",),
    )

    tool.copy("hello")

    assert seen_capture_output == [None]
    assert seen_stdout == [subprocess.DEVNULL]
    assert seen_stderr == [subprocess.DEVNULL]


def test_get_clipboard_path_captures_subprocess_output(monkeypatch) -> None:
    seen_capture_output: list[bool | None] = []
    seen_stdout: list[object | None] = []
    seen_stderr: list[object | None] = []

    def fake_run(*args, **kwargs):
        seen_capture_output.append(kwargs.get("capture_output"))
        seen_stdout.append(kwargs.get("stdout"))
        seen_stderr.append(kwargs.get("stderr"))
        return subprocess.CompletedProcess(args[0], 0, "hello", "")

    monkeypatch.setattr("py_ydotool.client.subprocess.run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False)
    tool._clipboard = ClipboardBackend(
        name="test",
        copy_command=("copy-cmd",),
        paste_command=("paste-cmd",),
    )

    assert tool.get_clipboard() == "hello"

    assert seen_capture_output == [True]
    assert seen_stdout == [None]
    assert seen_stderr == [None]
