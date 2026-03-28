from py_ydotool.clipboard import detect_clipboard_backend
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
